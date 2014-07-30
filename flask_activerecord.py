#!/usr/bin/env python


import datetime as dt
from sqlalchemy.orm import ColumnProperty, RelationshipProperty, object_mapper, class_mapper, defer, lazyload
from sqlalchemy import Column, BigInteger


def _get_mapper(obj):
    """Returns the primary mapper for the given instance or class"""
    its_a_model = isinstance(obj, type)
    mapper = class_mapper if its_a_model else object_mapper
    return mapper(obj)


def _primary_key_names(obj):
    """Returns the name of the primary key of the specified model or instance
    of a model, as a string.

    If `model_or_instance` specifies multiple primary keys and ``'id'`` is one
    of them, ``'id'`` is returned. If `model_or_instance` specifies multiple
    primary keys and ``'id'`` is not one of them, only the name of the first
    one in the list of primary keys is returned.
    """
    return [key.name for key in _get_mapper(obj).primary_key]


def _get_columns(model):
    """Returns a dictionary-like object containing all the columns properties of the
    specified `model` class.
    """
    return {c.key: c for c in _get_mapper(model).iterate_properties
            if isinstance(c, ColumnProperty)}


def _get_relations(model):
    return {c.key: c for c in _get_mapper(model).iterate_properties
            if isinstance(c, RelationshipProperty)}


def _model_to_dict(models, *fields, **props):
    """Converts an SQLAlchemy model object to JSON dict
    """
    result = []
    fields = list(fields)

    is_many = isinstance(models, list)

    # terminate early if there is nothing to work on
    if not models:
        return [] if is_many else {}

    if not is_many:
        models = [models]

    assert isinstance(models[0], ActiveRecord), "Invalid ActiveRecord object"

    if fields and len(fields) == 1:
        fields = [s.strip() for s in fields[0].split(',')]

    # pop of meta information
    # _overwrite = props.pop('_overwrite', None)
    _exclude = props.pop('_exclude', [])
    if isinstance(_exclude, basestring):
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
            index = k.index(".")
            model, attr = k[:index], k[index + 1:]
            if model in related_fields:
                related_map[model] = related_map.get(model, [])
            related_map[model].append(attr)
        elif k in related_fields:
            related_map[k] = []

    # no fields to return
    if not model_attr and not related_map:
        return {}

    for key in _primary_key_names(models[0]):
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

        # add extra properties
        for k in props:
            data[k] = props[k]
            if callable(data[k]):
                data[k] = data[k](model)

        # add to results
        result.append(data)

    # get correct response
    result = result if is_many else result[0]
    return result


def json_serialize(value):
    """Returns a JSON serializable python type of the given value

    :param value:
    """
    if value is None or isinstance(value, (int, long, float, basestring, bool)):
        return value
    elif isinstance(value, (list, tuple, set)):
        return [json_serialize(v) for v in value]
    elif isinstance(value, dict):
        for k, v in value.items():
            value[k] = json_serialize(v)
        return value
    # return date/time in isoformat
    elif isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    elif isinstance(value, ActiveRecord):
        return _model_to_dict(value)
    else:
        return unicode(value)


def _select(model, *fields):
    """Projects given columns to be included in query output
    """
    pk_columns = _primary_key_names(model)
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


class ActiveRecord(object):
    """Implements a simple ActiveRecord pattern for Flask-SQLAlchemy adding Rails-style sweetness

    Example:

    class User(db.Model, ActiveRecord):
        username = db.Column(db.String(80), unique=True)
        email = db.Column(db.String(120), unique=True)
        addresses = db.relationship('Address', backref='user', lazy='joined')

    class Address(db.Model, ActiveRecord):
        city = db.Column(db.String(50))
        state = db.Column(db.String(50))
        street = db.Column(db.String(50))
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    """
    __abstract__ = True

    query_class = None

    # default primary key of ActiveRecord class
    id = Column(BigInteger, primary_key=True)

    # attributes protected from mass assignment
    _attr_protected = tuple()

    # attributes accessible through mass assignments and also returned by to_json
    _attr_accessible = tuple()

    # attributes hidden from JSON serialization
    _attr_hidden = tuple()

    def __repr__(self):
        return "%s(\n%s\n)" % (
            self.__class__.__name__,
            ', \n'.join(["%s=%r" % (c, getattr(self, c)) for c in self.__class__.get_columns()])
        )

    def assign_attributes(self, *args, **params):
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
            if hasattr(self, attr) and (not sanitize or not self._attr_accessible or attr in self._attr_accessible):
                setattr(self, attr, params[attr])

        return self

    def update_attributes(self, *args, **params):
        self.assign_attributes(*args, **params)
        return self.save()

    def save(self):
        self.query.session.add(self)
        self.query.session.commit()
        return self

    def delete(self):
        self.query.session.delete(self)
        self.query.session.commit()
        return self

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
    def find(cls, ident):
        return cls.query.get(ident)

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
    def find_by(cls, *criteria, **filters):
        return cls.where(*criteria, **filters).first()

    @classmethod
    def find_each(cls, batch_size=1000):
        return cls.select().find_each(batch_size=batch_size)

    @classmethod
    def find_in_batches(cls, batch_size=1000):
        return cls.select().find_in_batches(batch_size=batch_size)

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


class _QueryHelper(object):

    def __init__(self, model):
        self._model_cls = model
        self._options = []
        self._filters = []
        self._order_by = []
        self._group_by = []
        self._having = None
        self._offset = 0
        self._limit = None
        self._compiled = None

    @property
    def _query(self):
        if not self._compiled:
            query = self._model_cls.query
            if not self._options:
                # force lazy loading of unselected relations
                self.select()
            query = query.options(*self._options)

            if self._filters:
                query = query.filter(*self._filters)
            if self._order_by:
                query = query.order_by(*self._order_by)
            if self._group_by:
                query = query.group_by(*self._group_by)
                if self._having:
                    query = query.having(self._having)
            self._compiled = query

        return self._compiled

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

    def find_each(self, batch_size=1000):
        if batch_size < 1:
            raise Exception("batch_size must be positive")

        offset = 0
        counter = 0
        while True:
            self._query.offset(offset).limit(batch_size)
            for row in self._query:
                yield row
                counter += 1
            if counter < batch_size:
                raise StopIteration()
            else:
                offset += batch_size
                counter = 0

    def find_in_batches(self, batch_size=1000):
        if batch_size < 1:
            raise Exception("batch_size must be positive")

        offset = 0
        while True:
            self._query.offset(offset).limit(batch_size)
            batch = self._query.all()
            if batch:
                yield batch
            if len(batch) < batch_size:
                raise StopIteration()
            else:
                offset += batch_size