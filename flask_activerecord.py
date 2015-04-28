"""
    flask.ext.activerecord
    ~~~~~~~~~~~~~~~~~~~~~~
    Patch and extend `flask_sqlalchemy.Model` with ActiveRecord support.

    :copyright: (c) 2015 by Francis Asante
    :license: BSD, see LICENSE for more details.
"""

__version__ = '0.2.1'
__all__ = ['patch_model', 'json_value']

import datetime as dt
from functools import wraps
import flask_sqlalchemy
from sqlalchemy.orm import RelationshipProperty, \
    object_mapper, class_mapper, defer, eagerload


def patch_model():
    """Patches the `flask_sqlalchemy.Model` object to support active record style queries
    """
    # monkey path the default Model with ActiveRecord
    flask_sqlalchemy.Model = ActiveRecord


def _get_mapper(obj):
    """Returns the primary mapper for the given instance or class"""
    its_a_model = isinstance(obj, type)
    mapper = class_mapper if its_a_model else object_mapper
    return mapper(obj)


__CACHE = {}


def _memoize(f):
    @wraps(f)
    def wrapper(obj):
        key = f.__name__
        mapper = _get_mapper(obj)
        if mapper in __CACHE and key in __CACHE[mapper]:
            return __CACHE[mapper][key]
        __CACHE.setdefault(mapper, {})
        __CACHE[mapper][key] = f(obj)
        return __CACHE[mapper][key]
    return wrapper


@_memoize
def _get_primary_keys(obj):
    """Returns the name of the primary key of the specified model or instance
    of a model, as a string.

    If `model_or_instance` specifies multiple primary keys and `'id'` is one
    of them, `'id'` is returned. If `model_or_instance` specifies multiple
    primary keys and `'id'` is not one of them, only the name of the first
    one in the list of primary keys is returned.
    """
    return [key for key, val in _get_mapper(obj).c.items() if val.primary_key]


@_memoize
def _get_columns(model):
    """Returns a `list` of columns names of the given model
    """
    return [key for key, val in _get_mapper(model).c.items()]


@_memoize
def _get_relations(model):
    """Return a `list` of relationship names or the given model
    """
    return [c.key for c in _get_mapper(model).iterate_properties if isinstance(c, RelationshipProperty)]


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
    related_fields = _get_relations(models[0])
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

        hidden_attributes = model.__attribute_filters__.get('hidden', EMPTY)

        # handle column attributes
        for k in model_attr:
            if k in hidden_attributes:
                continue
            v = getattr(model, k)
            # change dates to human readable format
            data[k] = json_value(v)

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

        result.append(data)

    result = result if has_many else result[0]
    return result


def json_value(value):
    """Returns a JSON serializable type of the given value

    :param value: the object to return as JSON a json value
    """
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    elif isinstance(value, (list, tuple, set)):
        return [json_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: json_value(value[k]) for k in value}
    elif isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    elif hasattr(value, 'to_dict') and callable(getattr(value, 'to_dict')):
        return json_value(value.to_dict())
    else:
        return str(value)


def _select_options(model, *fields):
    """Projects given columns to be included in query output
    """
    pk_columns = set(_get_primary_keys(model))
    all_columns = set(_get_columns(model))
    relations = set(_get_relations(model))

    fields = set(fields) | pk_columns if fields else all_columns
    options = []

    # include PKs and defer unrequested attributes (including related)
    # NB: intentionally allows fields like "related.attribute" to pass through

    for key in (all_columns - fields):
        options.append(defer(getattr(model, key)))
    for key in (relations & fields):
        options.append(eagerload(getattr(model, key)))

    return options


def _where_clause(model, *criteria, **filters):
    """Builds a list of where conditions for this applying the correct operators
    for representing the values.

    `=` expression is generated for single simple values (int, str, datetime, etc.)
    `IN` expression is generated for list/set of simple values
    `BETWEEN` expression is generated for 2-tuple of simple values
    """
    conditions = list(criteria)

    if not filters:
        return conditions

    for key in set(_get_relations(model)) & set(filters.keys()):
        value = filters[key]
        if not isinstance(value, list):
            value = [value]

        if len(value) == 1:
            conditions.append(getattr(model, key) == value[0])
        else:
            # Not implemented yet as of SQLAlchemy 0.7.9
            conditions.append(getattr(model, key).in_(value))

    for key in set(_get_columns(model)) & set(filters.keys()):
        value = filters[key]

        if isinstance(value, tuple):
            # ensure only two values in tuple
            if len(value) != 2:
                raise ValueError(
                    "Expected tuple of size 2 generate BETWEEN expression "
                    "for column '%s.%s'" % (model.__name__, key))
            lower, upper = min(value), max(value)
            value = (lower, upper)
        elif not isinstance(value, list):
            value = [value]
        elif not value:
            raise ValueError(
                "Expected non-empty list to generate IN expression "
                "for column '%s.%s'" % (model.__name__, key))

        if len(value) == 1:
            value = getattr(model, key) == value[0]
        elif isinstance(value, tuple):
            value = getattr(model, key).between(value[0], value[1])
        else:
            value = getattr(model, key).in_(value)

        conditions.append(value)

    return conditions


class _QueryHelper(object):
    """
    A query helper interface also used to proxy query methods
    """

    def __init__(self, model):
        self._model = model
        self._scalar = None
        self._options = None
        self._filters = None
        self._order_by = None
        self._group_by = None
        self._having = None
        self._offset = None
        self._limit = None
        self._compiled = None

    @property
    def _query(self):
        if not self._compiled:

            session = self._model.query.session

            if self._scalar is not None:
                self._model = self._scalar
                self._options = []
            elif not self._options:
                self.select()

            query = session.query(self._model).options(*self._options)

            if self._filters:
                query = query.filter(*self._filters)
            if self._order_by:
                query = query.order_by(*self._order_by)
            if self._group_by:
                query = query.group_by(*self._group_by)
                if self._having:
                    query = query.having(self._having)
            if self._offset and self._offset > 0:
                query = query.offset(self._offset)
            if self._limit and self._limit > 0:
                query = query.limit(self._limit)
            self._compiled = query
        return self._compiled

    def all(self):
        return self._query.all()

    def first(self):
        """Return the first record of this model"""
        return self._query.first()

    def one(self):
        return self._query.one()

    def count(self):
        """Return a count of records in the query"""
        from sqlalchemy import func

        self._scalar = func.count(getattr(self._model, 'id'))
        return self._query.scalar()

    def delete(self):
        """Delete all records matched by the query"""
        return self._query.delete()

    def exists(self):
        """Returns true if records exist for this query"""
        return bool(self.count())

    def join(self, *props, **kwargs):
        return self._query.join(*props, **kwargs)

    def where(self, *criteria, **filters):
        """Specify conditions for use in query.
         Multiple conditions are join with an `AND` clause. Example::

            User.where(User.fullname=='John Smith', country=['US', 'GH']).all()

        :param \*criteria: a tuple of :class:`SQLAlchemy` criteria expressions
        :param \**filters: extra filter expressions
        :return:
        """
        self._filters = _where_clause(self._model, *criteria, **filters)
        return self

    def select(self, *columns):
        """Columns to project in query. Example::

            User.select('id', 'fullname').all()

        :param \*columns: the column names
        """
        self._options = _select_options(self._model, *columns)
        return self

    def order_by(self, *expressions):
        from sqlalchemy.sql.expression import desc, asc

        self._order_by = []
        for key in expressions:
            if isinstance(key, basestring):
                fn, key = (desc, key[1:]) if key.startswith('-') else (asc, key)
                field = fn(getattr(self._model, key))
                self._order_by.append(field)
            else:
                self._order_by.append(key)
        return self

    def group_by(self, *criteria):
        self._group_by = criteria
        return self

    def having(self, *criteria):
        self._having = criteria
        return self

    def offset(self, offset):
        self._offset = offset
        return self

    def limit(self, limit):
        self._limit = limit
        return self

    def find_each(self, start=None, batch_size=None):
        """Fetch each record efficiently. Similar to :meth:`find_in_batches`
        but yields single objects. Example::

            # starting from offset 10 in batches of 100
            for user in User.find_each(10, 100):
                # do something with user
                pass
        """
        for rows in self.find_in_batches(start, batch_size):
            for obj in rows:
                yield obj

    def find_in_batches(self, start=None, batch_size=None):
        """Fetch records in batches. Example::

            for user_batch in User.find_in_batches(100):
                # do something with batch
                pass

        If the batch_size is not given, the `start` index value is used as the `batch_size`
        if provided and `start` is set to zero.

        :param start: the start position
        :param batch_size: the batch size
        :return: an generator yielding record batches
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


EMPTY = tuple()


class ActiveRecord(flask_sqlalchemy.Model):
    """A implementation of the `ActiveRecord` pattern for FlaskSQLAlchemy models

    ..code:: python

        from flask import Flask
        from flask_activerecord import patch_model
        from flask_sqlalchemy import SQLAlchemy

        patch_model()

        app = Flask(__name__)
        db = SQLAlchemy(app)

        # example Model
        class User(db.Model):
            __attribute_filters__ = {
                'accessible': ('fullname', 'country'),
                'protected': ('id', 'email', 'password')
                'hidden': ('password', )
            }

            email = db.Column(db.String, unique=True)
            password = db.Column(db.String, unique=True)
            fullname = db.Column(db.String)
            country = db.Column(db.String(2))

    """

    #: a `dict` of attribute filters for different purposes
    __attribute_filters__ = {}

    def __repr__(self):
        return "%s(\n%s\n)" % (
            self.__class__.__name__,
            ', \n'.join(["  %s=%r" % (c, getattr(self, c)) for c in
                         self.__class__.get_columns()]))

    def assign(self, **kwargs):
        """Allows assigning model attributes in batch.
        Filters out *protected* attributes and allow only *accessible* attributes if non-empty.
        This method does not persist changes to the database. Example::

            # with reference to User model. `password` is ignored
            user.assign(fullname='Joe Smith', country='US', password='012345')

        :param kwargs: a `dict` with names matching model attributes
        """
        for key in self.get_columns():
            if key in self.__attribute_filters__.get('protected', EMPTY):
                continue
            attr_accessible = self.__attribute_filters__.get('accessible', EMPTY)
            if key in kwargs and (not attr_accessible or key in attr_accessible):
                setattr(self, key, kwargs[key])
        return self

    def update(self, **kwargs):
        """Same as :meth:`assign` method but persists changes to database.
        """
        return self.assign(**kwargs).save()

    def save(self, commit=True):
        """Saves the updated model to the current entity session.

        :param commit: flag to determine whether to persist to database instantly
        """
        self.query.session.add(self)
        if commit:
            self.query.session.commit()
        return self

    def delete(self, commit=True):
        """Removes the model from the current entity session and mark for deletion.

        :param commit: flag to determine whether to persist to database instantly
        """
        self.query.session.delete(self)
        return commit and self.query.session.commit()

    def to_dict(self, *fields, **kwargs):
        """Serialize the model to a `dict`

        :param fields: the attribute names to include
        :param kwargs: extra data and options
        :return: a `dict` representation of the model
        """
        return _model_to_dict(self, *fields, **kwargs)

    @classmethod
    def get_columns(cls):
        return _get_columns(cls)

    @classmethod
    def create(cls, **kwargs):
        """Create and persist a new record for the model

        :param kwargs: attributes for the record
        :return: the new model instance
        """
        return cls(**kwargs).save()

    @classmethod
    def destroy(cls, *ids):
        """Delete the records with the given ids

        :param ids: primary key ids of records
        """
        for pk in ids:
            cls.find(pk).delete(False)
        cls.query.session.commit()

    @classmethod
    def find(cls, id):
        """Find record by the id

        :param id: the primary key id
        """
        return cls.query.get(id)

    @classmethod
    def all(cls):
        """Return all records for this model type"""
        return cls.query.all()

    @classmethod
    def first(cls):
        """Returns the first record of this model after ordering by `id`"""
        rs = cls.take(1)
        return rs[0] if rs else None

    @classmethod
    def last(cls):
        rs = cls.take(1, True)
        return rs[0] if rs else None

    @classmethod
    def take(cls, n, reverse=False):
        return cls.select().order_by((reverse and '-' or '') + 'id').limit(n).all()

    @classmethod
    def count(cls):
        """Return the count of the number of records of this model"""
        return cls.select().count()

    @classmethod
    def find_by(cls, *criteria, **filters):
        """An alias to using `where(*criteria, **filters).first()` for convenience"""
        return cls.where(*criteria, **filters).order_by('id').first()

    @classmethod
    def find_each(cls, start=None, batch_size=None):
        return cls.select().find_each(start=start, batch_size=batch_size)

    @classmethod
    def find_in_batches(cls, start=None, batch_size=None):
        return cls.select().find_in_batches(start=start, batch_size=batch_size)

    @classmethod
    def select(cls, *columns):
        return _QueryHelper(cls).select(*columns)

    @classmethod
    def where(cls, *criteria, **filters):
        return _QueryHelper(cls).where(*criteria, **filters)