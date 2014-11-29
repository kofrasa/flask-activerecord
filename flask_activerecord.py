# -*- coding: utf-8 -*-
"""
    flaskext.activerecord
    ~~~~~~~~~~~~~~~~~~~~~
    Path and extend `flask_sqlalchemy.Model` with ActiveRecord support.
    :copyright: (c) 2014 by Francis Asante
    :license: BSD, see LICENSE for more details.
"""

import datetime as dt
import flask_sqlalchemy
from sqlalchemy.orm import ColumnProperty, RelationshipProperty, object_mapper, class_mapper, defer, lazyload


__slots__ = ('patch_model', 'json_serialize')


def patch_model():
    """Patches the `flask_sqlalchemy.Model` object to support active record flexible style queries
    """
    # monkey path the default Model with ActiveRecord
    flask_sqlalchemy.Model = ActiveRecord


def _get_mapper(obj):
    """Returns the primary mapper for the given instance or class"""
    its_a_model = isinstance(obj, type)
    mapper = class_mapper if its_a_model else object_mapper
    return mapper(obj)


def _get_primary_keys(obj):
    """Returns the name of the primary key of the specified model or instance
    of a model, as a string.

    If `model_or_instance` specifies multiple primary keys and `'id'` is one
    of them, `'id'` is returned. If `model_or_instance` specifies multiple
    primary keys and `'id'` is not one of them, only the name of the first
    one in the list of primary keys is returned.
    """
    return [key for key, val in _get_columns(obj).iteritems() if val.is_primary()]


def _get_columns(model):
    """Returns a dictionary-like object containing all the columns properties of the
    specified `model` class.
    """
    return {c.key: c for c in _get_mapper(model).iterate_properties
            if isinstance(c, ColumnProperty)}


def _get_relations(model):
    """Get relationship names and properties from model
    """
    return {c.key: c for c in _get_mapper(model).iterate_properties
            if isinstance(c, RelationshipProperty)}


def _model_to_dict(models, *fields, **props):
    """Serialize an ActiveRecord object to a JSON dict
    """
    result = []
    fields = list(fields)

    has_many = isinstance(models, list)

    # terminate early if there is nothing to work on
    if not models:
        return [] if has_many else {}

    if not has_many:
        models = [models]

    if fields and len(fields) == 1:
        fields = [s.strip() for s in fields[0].split(',')]

    # pop of meta information
    # _overwrite = props.pop('_overwrite', None)
    _exclude = props.pop('_exclude', [])
    if isinstance(_exclude, str):
        _exclude = [e.strip() for e in _exclude.split(',')]

    # select columns given or all if non was specified
    model_attr = set(_get_columns(models[0]))
    if not model_attr & set(fields):
        fields = model_attr | set(fields)

    # correctly filter relation attributes and column attributes
    related_attr = set(fields) - model_attr
    model_attr = set(fields) - (set(_exclude) | related_attr)

    # check if there are relationships
    related_fields = _get_relations(models[0]).keys()
    related_map = {}
    # check if remaining fields are valid related attributes
    for k in related_attr:
        if '.' in k:
            index = k.index('.')
            model, attr = k[:index], k[index + 1:]
            if model in related_fields:
                related_map[model] = related_map.get(model, [])
            related_map[model].append(attr)
        elif k in related_fields:
            related_map[k] = []

    # no fields to return
    if not model_attr and not related_map:
        return {}

    for key in _get_primary_keys(models[0]):
        model_attr.add(key)

    for model in models:
        data = {}
        # handle column attributes
        for k in model_attr:
            if k in getattr(model, '_attr_hidden', []):
                continue
            v = getattr(model, k)
            # change dates to human readable format
            data[k] = json_serialize(v)

        # handle relationships
        for k in related_map:
            val = getattr(model, k)
            fields = related_map[k]
            data[k] = _model_to_dict(val, *fields)

        # handle extra properties
        for k in props:
            data[k] = props[k]
            if callable(data[k]):
                data[k] = data[k](model)
        # add to results
        result.append(data)

    # get correct response
    result = result if has_many else result[0]
    return result


def json_serialize(value):
    """Returns a JSON serializable python type of the given value

    :param value: the object to return as JSON a json value
    """
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    elif isinstance(value, (list, tuple, set)):
        return [json_serialize(v) for v in value]
    elif isinstance(value, dict):
        for k, v in value.items():
            value[k] = json_serialize(v)
        return value
    elif isinstance(value, (dt.datetime, dt.date, dt.time)):
        if isinstance(value, (dt.datetime, dt.time)):
            value = value.replace(microsecond=0)
        return value.isoformat()
    elif hasattr(value, 'to_dict') and callable(getattr(value, 'to_dict')):
        return value.to_dict()
    else:
        return str(value)


def _select(model, *fields):
    """Projects given columns to be included in query output
    """
    pk_columns = _get_primary_keys(model)
    all_columns = _get_columns(model).keys()
    relations = _get_relations(model).keys()

    fields = list(set(fields)) if fields else all_columns

    # select all column properties if none is specified
    for attr in fields:
        if attr in all_columns:
            break
    else:
        fields.extend(all_columns)

    options = []

    # ensure PKs are included and defer unrequested attributes (including related)
    # NB: we intentionally allows fields like "related.attribute" to pass through
    for attr in (c.key for c in _get_mapper(model).iterate_properties):
        if attr not in fields:
            if attr in pk_columns:
                fields.append(attr)
            elif attr in all_columns:
                options.append(defer(attr))
            # relationships
            elif attr in relations:
                options.append(lazyload(attr))
    return options


def _where(model, *criteria, **filters):
    """Builds a list of where conditions for this applying the correct operators
    for representing the values.

    `=` expression is generated for single simple values (int, str, datetime, etc.)
    `IN` expression is generated for list/set of simple values
    `BETWEEN` expression is generated for 2-tuple of simple values
    """
    conditions = []
    conditions.extend(criteria)

    # build criteria from filter
    if filters:

        filter_keys = filters.keys()

        # select valid filters only
        columns = {c.name: c for c in _get_mapper(model).columns
                   if c.name in filter_keys}
        relations = {c.key: c for c in _get_mapper(model).iterate_properties
                     if isinstance(c, RelationshipProperty) and c.key in filter_keys}

        for attr, rel in relations.items():
            value = filters[attr]
            if not isinstance(value, list):
                value = [value]
                # validate type of object
            for v in value:
                assert not v or isinstance(v, rel.mapper.class_), "Type mismatch"

            if len(value) == 1:
                conditions.append(getattr(model, attr) == value[0])
            else:
                # Not implemented yet as of SQLAlchemy 0.7.9
                conditions.append(getattr(model, attr).in_(value))

        for attr, prop in columns.items():
            value = filters[attr]

            if isinstance(value, tuple):
                # ensure only two values in tuple
                if len(value) != 2:
                    raise ValueError(
                        "Expected tuple of size 2 generate BETWEEN expression for column '%s.%s'" % (
                            model.__name__, attr))
                lower, upper = min(value), max(value)
                value = (lower, upper)
            elif not isinstance(value, list):
                value = [value]
            elif not value:
                raise ValueError(
                    "Expected non-empty list to generate IN expression for column '%s.%s'" % (
                        model.__name__, attr))

            if len(value) == 1:
                # generate = statement
                value = getattr(model, attr) == value[0]
            elif isinstance(value, tuple):
                # generate BETWEEN statement
                lower = min(value)
                upper = max(value)
                value = getattr(model, attr).between(lower, upper)
            else:
                # generate IN statement
                value = getattr(model, attr).in_(value)

            conditions.append(value)

    return conditions


class _QueryHelper(object):
    def __init__(self, model):
        self._model_cls = model
        self._options = []
        self._filters = []
        self._order_by = []
        self._group_by = []
        self._having = None
        self._offset = None
        self._limit = None
        self._orm_query = None

    @property
    def _query(self):
        if not self._orm_query:
            sql = self._model_cls.query
            if not self._options:
                # force lazy loading of unselected relations
                self.select()
            sql = sql.options(*self._options)
            if self._filters:
                sql = sql.filter(*self._filters)
            if self._order_by:
                sql = sql.order_by(*self._order_by)
            if self._group_by:
                sql = sql.group_by(*self._group_by)
                if self._having:
                    sql = sql.having(self._having)
            if self._offset and self._offset > 0:
                sql = sql.offset(self._offset)
                if self._limit and self._limit > 0:
                    sql = sql.limit(self._limit)
            self._orm_query = sql
        return self._orm_query

    def all(self):
        return self._query.all()

    def first(self):
        return self._query.first()

    def one(self):
        return self._query.one()

    def count(self):
        return self._query.count()

    def delete(self):
        return self._query.delete()

    def join(self, *props, **kwargs):
        return self._query.join(*props, **kwargs)

    def where(self, *criteria, **filters):
        conditions = _where(self._model_cls, *criteria, **filters)
        self._filters.extend(conditions)
        return self

    def select(self, *fields):
        options = _select(self._model_cls, *fields)
        self._options.extend(options)
        return self

    def order_by(self, *fields):
        self._order_by.extend(list(fields))
        return self

    def group_by(self, *criteria):
        self._group_by.extend(criteria)
        return self

    def having(self, criterion):
        self._having = criterion
        return self

    def offset(self, offset):
        self._offset = offset
        return self

    def limit(self, limit):
        self._limit = limit
        return self

    def find_each(self, start=None, batch_size=None):
        for rows in self.find_in_batches(start, batch_size):
            for obj in rows:
                yield obj

    def find_in_batches(self, start=None, batch_size=None):
        """
        Retrieve records in batches returning a generator for efficient iteration
        :param start:
        :param batch_size:
        :return:
        """
        offset = batch_size and start or 0
        batch_size = batch_size or start or 1000

        if offset < 0:
            offset = 0
        if batch_size < 1:
            raise Exception("batch_size must be positive")

        while True:
            rows = self._query.offset(offset).limit(batch_size).all()
            if rows:
                yield rows
            if len(rows) < batch_size:
                raise StopIteration()
            else:
                offset += batch_size


class ActiveRecord(object):
    """A implementation of the `ActiveRecord` pattern

    Example:

    class User(db.Model):
        _attr_protected = ('id', 'email', 'username', 'password')
        _attr_accessible = tuple('first_name', 'last_name')
        _attr_hidden = ('password',)

        username = db.Column(db.String(80), unique=True)
        password = db.Column(db.String(80), unique=True)
        email = db.Column(db.String(120), unique=True)
        first_name = db.Column(db.String(80), unique=True)
        last_name = db.Column(db.String(80), unique=True)

    user = User.create(username='kofrasa', password='kofrasa', email='kofrasa@gmail.com')
    user_from_db = User.find(user.id)
    # user == user_from_db
    user.first_name = 'Francis'
    user.save() # changes have been reflected to db

    # for batch changes
    user.last_name = 'Asante'
    user.password = 'something secret'
    user.save(False) # add to session but do not flush just yet

    # do some more work and flush with saving some other objects
    db.session.commit()

    # batch updates
    # note that password will not be updated. it is included in _attr_protected tuple
    user.update(first_name='John', last_name='Doe', password='new_password')

    # Queries
    User.count() # return 1
    User.all() # return [User<id=1>]
    User.first() # return the first entry
    User.find_by(username='kofrasa') # return first entry matching criteria
    User.where(last_name='Asante').all() # return all entries matching criteria

    """
    __abstract__ = True

    # : the query class used.  The :attr:`query` attribute is an instance
    #: of this class.  By default a :class:`BaseQuery` is used.
    query_class = flask_sqlalchemy.BaseQuery

    #: an instance of :attr:`query_class`.  Can be used to query the
    #: database for instances of this model.
    query = None

    # attributes protected from mass assignment
    _attr_protected = tuple()

    # attributes accessible through mass assignments and also returned by to_json
    _attr_accessible = tuple()

    # attributes hidden from JSON serialization
    _attr_hidden = tuple()

    def __repr__(self):
        return "%s(\n%s\n)" % (
            self.__class__.__name__,
            ', \n'.join(["  %s=%r" % (c, getattr(self, c)) for c in self.__class__.get_columns()])
        )

    def assign(self, *args, **params):
        sanitize = True
        if args and isinstance(args[0], dict):
            sanitize = args[0].get('sanitize', sanitize)
            params = params or args[0]
        del params['sanitize']

        for attr in self.get_columns():
            if attr not in params:
                continue
            if sanitize and attr in self._attr_protected:
                continue
            if hasattr(self, attr) and not sanitize or (not self._attr_accessible or attr in self._attr_accessible):
                setattr(self, attr, params[attr])
        return self

    def update(self, *args, **params):
        self.assign(*args, **params)
        return self.save()

    def save(self, commit=True):
        self.query.session.add(self)
        if commit:
            self.query.session.commit()
        return self

    def delete(self, commit=True):
        self.query.session.delete(self)
        return commit and self.query.session.commit()

    def to_dict(self, *fields, **props):
        return _model_to_dict(self, *fields, **props)

    @classmethod
    def get_columns(cls):
        return _get_columns(cls).keys()

    @classmethod
    def create(cls, **kw):
        return cls(**kw).save()

    @classmethod
    def destroy(cls, *idents):
        return cls.where(id=list(idents)).delete()

    @classmethod
    def find(cls, id):
        return cls.query.get(id)

    @classmethod
    def all(cls):
        return cls.query.all()

    @classmethod
    def first(cls):
        return cls.query.first()

    @classmethod
    def exists(cls, *criteria, **filters):
        return cls.find_by(*criteria, **filters) is not None

    @classmethod
    def count(cls):
        return cls.query.count()

    @classmethod
    def find_by(cls, *criteria, **filters):
        return cls.where(*criteria, **filters).first()

    @classmethod
    def find_each(cls, start=None, batch_size=None):
        return cls.select().find_each(start=start, batch_size=batch_size)

    @classmethod
    def find_in_batches(cls, start=None, batch_size=None):
        return cls.select().find_in_batches(start=start, batch_size=batch_size)

    @classmethod
    def select(cls, *fields):
        q = _QueryHelper(cls)
        q.select(*fields)
        return q

    @classmethod
    def where(cls, *criteria, **filters):
        q = _QueryHelper(cls)
        q.where(*criteria, **filters)
        return q