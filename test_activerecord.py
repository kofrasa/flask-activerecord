from __future__ import with_statement

import atexit
import unittest
from datetime import datetime
import flask
from flask.ext import sqlalchemy
from sqlalchemy.orm import sessionmaker
from flask_activerecord import patch_model


# path the default model
patch_model()


def make_todo_model(db):
    class Todo(db.Model):
        id = db.Column('todo_id', db.Integer, primary_key=True)
        title = db.Column(db.String(60))
        text = db.Column(db.String)
        done = db.Column(db.Boolean)
        pub_date = db.Column(db.DateTime)

        def __init__(self, title, text):
            self.title = title
            self.text = text
            self.done = False
            self.pub_date = datetime.utcnow()

    return Todo


def make_user_model(db):
    class User(db.Model):
        __tablename__ = 'user'
        id = db.Column(db.Integer)
        name = db.Column(db.String(60))
        todo_id = db.Column(db.Integer, db.ForeignKey('todo.todo_id'))
        todo = db.relationship('Todo')

        __table_args__ = (
            db.PrimaryKeyConstraint('id'),
        )

        def __init__(self, name, todo):
            self.name = name
            self.todo = todo

    return User


class BasicAppTestCase(unittest.TestCase):
    def setUp(self):
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True
        db = sqlalchemy.SQLAlchemy(app)
        self.Todo = make_todo_model(db)

        @app.route('/')
        def index():
            return '\n'.join(x.title for x in self.Todo.query.all())

        @app.route('/add', methods=['POST'])
        def add():
            form = flask.request.form
            todo = self.Todo(form['title'], form['text'])
            db.session.add(todo)
            db.session.commit()
            return 'added'

        db.create_all()

        self.app = app
        self.db = db

    def tearDown(self):
        self.db.drop_all()

    def test_basic_insert(self):
        c = self.app.test_client()
        c.post('/add', data=dict(title='First Item', text='The text'))
        c.post('/add', data=dict(title='2nd Item', text='The text'))
        rv = c.get('/')
        self.assertEqual(rv.data, b'First Item\n2nd Item')

    def test_query_recording(self):
        with self.app.test_request_context():
            todo = self.Todo('Test 1', 'test')
            self.db.session.add(todo)
            self.db.session.commit()

            queries = sqlalchemy.get_debug_queries()
            self.assertEqual(len(queries), 1)
            query = queries[0]
            self.assertTrue('insert into' in query.statement.lower())
            self.assertEqual(query.parameters[0], 'Test 1')
            self.assertEqual(query.parameters[1], 'test')
            self.assertTrue('test_activerecord.py' in query.context)
            self.assertTrue('test_query_recording' in query.context)

    def test_helper_api(self):
        self.assertEqual(self.db.metadata, self.db.Model.metadata)


class TestQueryProperty(unittest.TestCase):
    def setUp(self):
        self.app = flask.Flask(__name__)
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.app.config['TESTING'] = True

    def test_no_app_bound(self):
        db = sqlalchemy.SQLAlchemy()
        db.init_app(self.app)
        Todo = make_todo_model(db)

        # If no app is bound to the SQLAlchemy instance, a
        # request context is required to access Model.query.
        self.assertRaises(RuntimeError, getattr, Todo, 'query')
        with self.app.test_request_context():
            db.create_all()
            todo = Todo('Test', 'test')
            db.session.add(todo)
            db.session.commit()
            self.assertEqual(len(Todo.query.all()), 1)

    def test_app_bound(self):
        db = sqlalchemy.SQLAlchemy(self.app)
        Todo = make_todo_model(db)
        db.create_all()

        # If an app was passed to the SQLAlchemy constructor,
        # the query property is always available.
        todo = Todo('Test', 'test')
        db.session.add(todo)
        db.session.commit()
        self.assertEqual(len(Todo.query.all()), 1)


class SignallingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True
        self.db = sqlalchemy.SQLAlchemy(app)
        self.Todo = make_todo_model(self.db)
        self.db.create_all()

    def tearDown(self):
        self.db.drop_all()

    def test_model_signals(self):
        recorded = []

        def committed(sender, changes):
            self.assertTrue(isinstance(list(changes), list))
            recorded.extend(changes)

        with sqlalchemy.models_committed.connected_to(committed,
                                                      sender=self.app):
            todo = self.Todo('Awesome', 'the text')
            self.db.session.add(todo)
            self.assertEqual(len(recorded), 0)
            self.db.session.commit()
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0][0], todo)
            self.assertEqual(recorded[0][1], 'insert')
            del recorded[:]
            todo.text = 'aha'
            self.db.session.commit()
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0][0], todo)
            self.assertEqual(recorded[0][1], 'update')
            del recorded[:]
            self.db.session.delete(todo)
            self.db.session.commit()
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0][0], todo)
            self.assertEqual(recorded[0][1], 'delete')


class HelperTestCase(unittest.TestCase):
    def test_default_table_name(self):
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        db = sqlalchemy.SQLAlchemy(app)

        class FOOBar(db.Model):
            id = db.Column(db.Integer, primary_key=True)

        class BazBar(db.Model):
            id = db.Column(db.Integer, primary_key=True)

        self.assertEqual(FOOBar.__tablename__, 'foo_bar')
        self.assertEqual(BazBar.__tablename__, 'baz_bar')


class PaginationTestCase(unittest.TestCase):
    def test_basic_pagination(self):
        p = sqlalchemy.Pagination(None, 1, 20, 500, [])
        self.assertEqual(p.page, 1)
        self.assertFalse(p.has_prev)
        self.assertTrue(p.has_next)
        self.assertEqual(p.total, 500)
        self.assertEqual(p.pages, 25)
        self.assertEqual(p.next_num, 2)
        self.assertEqual(list(p.iter_pages()),
            [1, 2, 3, 4, 5, None, 24, 25])
        p.page = 10
        self.assertEqual(list(p.iter_pages()),
            [1, 2, None, 8, 9, 10, 11, 12, 13, 14, None, 24, 25])

    def test_pagination_pages_when_0_items_per_page(self):
        p = sqlalchemy.Pagination(None, 1, 0, 500, [])
        self.assertEqual(p.pages, 0)


class BindsTestCase(unittest.TestCase):
    def test_basic_binds(self):
        import tempfile

        _, db1 = tempfile.mkstemp()
        _, db2 = tempfile.mkstemp()

        def _remove_files():
            import os

            try:
                os.remove(db1)
                os.remove(db2)
            except IOError:
                pass

        atexit.register(_remove_files)

        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['SQLALCHEMY_BINDS'] = {
            'foo': 'sqlite:///' + db1,
            'bar': 'sqlite:///' + db2
        }
        db = sqlalchemy.SQLAlchemy(app)

        class Foo(db.Model):
            __bind_key__ = 'foo'
            __table_args__ = {"info": {"bind_key": "foo"}}
            id = db.Column(db.Integer, primary_key=True)

        class Bar(db.Model):
            __bind_key__ = 'bar'
            id = db.Column(db.Integer, primary_key=True)

        class Baz(db.Model):
            id = db.Column(db.Integer, primary_key=True)

        db.create_all()

        # simple way to check if the engines are looked up properly
        self.assertEqual(db.get_engine(app, None), db.engine)
        for key in 'foo', 'bar':
            engine = db.get_engine(app, key)
            connector = app.extensions['sqlalchemy'].connectors[key]
            self.assertEqual(engine, connector.get_engine())
            self.assertEqual(str(engine.url),
                             app.config['SQLALCHEMY_BINDS'][key])

        # do the models have the correct engines?
        self.assertEqual(db.metadata.tables['foo'].info['bind_key'], 'foo')
        self.assertEqual(db.metadata.tables['bar'].info['bind_key'], 'bar')
        self.assertEqual(db.metadata.tables['baz'].info.get('bind_key'), None)

        # see the tables created in an engine
        metadata = db.MetaData()
        metadata.reflect(bind=db.get_engine(app, 'foo'))
        self.assertEqual(len(metadata.tables), 1)
        self.assertTrue('foo' in metadata.tables)

        metadata = db.MetaData()
        metadata.reflect(bind=db.get_engine(app, 'bar'))
        self.assertEqual(len(metadata.tables), 1)
        self.assertTrue('bar' in metadata.tables)

        metadata = db.MetaData()
        metadata.reflect(bind=db.get_engine(app))
        self.assertEqual(len(metadata.tables), 1)
        self.assertTrue('baz' in metadata.tables)

        # do the session have the right binds set?
        self.assertEqual(db.get_binds(app), {
            Foo.__table__: db.get_engine(app, 'foo'),
            Bar.__table__: db.get_engine(app, 'bar'),
            Baz.__table__: db.get_engine(app, None)
        })


class DefaultQueryClassTestCase(unittest.TestCase):
    def test_default_query_class(self):
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True
        db = sqlalchemy.SQLAlchemy(app)

        class Parent(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            children = db.relationship("Child", backref="parents", lazy='dynamic')

        class Child(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            parent_id = db.Column(db.Integer, db.ForeignKey('parent.id'))

        p = Parent()
        c = Child()
        c.parent = p
        self.assertEqual(type(Parent.query), sqlalchemy.BaseQuery)
        self.assertEqual(type(Child.query), sqlalchemy.BaseQuery)
        self.assertTrue(isinstance(p.children, sqlalchemy.BaseQuery))
        # self.assertTrue(isinstance(c.parents, sqlalchemy.BaseQuery))


class SQLAlchemyIncludesTestCase(unittest.TestCase):
    def test(self):
        """Various SQLAlchemy objects are exposed as attributes.
        """
        db = sqlalchemy.SQLAlchemy()

        import sqlalchemy as sqlalchemy_lib

        self.assertTrue(db.Column == sqlalchemy_lib.Column)

        # The Query object we expose is actually our own subclass.
        from flask.ext.sqlalchemy import BaseQuery

        self.assertTrue(db.Query == BaseQuery)


class RegressionTestCase(unittest.TestCase):
    def test_joined_inheritance(self):
        app = flask.Flask(__name__)
        db = sqlalchemy.SQLAlchemy(app)

        class Base(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            type = db.Column(db.Unicode(20))
            __mapper_args__ = {'polymorphic_on': type}

        class SubBase(Base):
            id = db.Column(db.Integer, db.ForeignKey('base.id'),
                           primary_key=True)
            __mapper_args__ = {'polymorphic_identity': 'sub'}

        self.assertEqual(Base.__tablename__, 'base')
        self.assertEqual(SubBase.__tablename__, 'sub_base')
        db.create_all()

    def test_single_table_inheritance(self):
        app = flask.Flask(__name__)
        db = sqlalchemy.SQLAlchemy(app)

        class Base(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            type = db.Column(db.Unicode(20))
            __mapper_args__ = {'polymorphic_on': type}

        class SubBase(Base):
            __mapper_args__ = {'polymorphic_identity': 'sub'}

        self.assertEqual(Base.__tablename__, 'base')
        self.assertEqual(SubBase.__tablename__, 'base')
        db.create_all()

    def test_joined_inheritance_relation(self):
        app = flask.Flask(__name__)
        db = sqlalchemy.SQLAlchemy(app)

        class Relation(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            base_id = db.Column(db.Integer, db.ForeignKey('base.id'))
            name = db.Column(db.Unicode(20))

            def __init__(self, name):
                self.name = name

        class Base(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            type = db.Column(db.Unicode(20))
            __mapper_args__ = {'polymorphic_on': type}

        class SubBase(Base):
            id = db.Column(db.Integer, db.ForeignKey('base.id'),
                           primary_key=True)
            __mapper_args__ = {'polymorphic_identity': u'sub'}
            relations = db.relationship(Relation)

        db.create_all()

        base = SubBase()
        base.relations = [Relation(name=u'foo')]
        db.session.add(base)
        db.session.commit()

        base = base.query.one()

    def test_connection_binds(self):
        app = flask.Flask(__name__)
        db = sqlalchemy.SQLAlchemy(app)
        assert db.session.connection()


class SessionScopingTestCase(unittest.TestCase):
    def test_default_session_scoping(self):
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True
        db = sqlalchemy.SQLAlchemy(app)

        class FOOBar(db.Model):
            id = db.Column(db.Integer, primary_key=True)

        db.create_all()

        with app.test_request_context():
            fb = FOOBar()
            db.session.add(fb)
            assert fb in db.session

    def test_session_scoping_changing(self):
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True

        def scopefunc():
            return id(dict())

        db = sqlalchemy.SQLAlchemy(app, session_options=dict(scopefunc=scopefunc))

        class FOOBar(db.Model):
            id = db.Column(db.Integer, primary_key=True)

        db.create_all()

        with app.test_request_context():
            fb = FOOBar()
            db.session.add(fb)
            assert fb not in db.session  # because a new scope is generated on each call


class CommitOnTeardownTestCase(unittest.TestCase):
    def setUp(self):
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
        db = sqlalchemy.SQLAlchemy(app)
        Todo = make_todo_model(db)
        db.create_all()

        @app.route('/')
        def index():
            return '\n'.join(x.title for x in Todo.query.all())

        @app.route('/create', methods=['POST'])
        def create():
            db.session.add(Todo('Test one', 'test'))
            if flask.request.form.get('fail'):
                raise RuntimeError("Failing as requested")
            return 'ok'

        self.client = app.test_client()

    def test_commit_on_success(self):
        resp = self.client.post('/create')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.get('/').data, b'Test one')

    def test_roll_back_on_failure(self):
        resp = self.client.post('/create', data={'fail': 'on'})
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(self.client.get('/').data, b'')


class StandardSessionTestCase(unittest.TestCase):
    def test_insert_update_delete(self):
        # Ensure _SignalTrackingMapperExtension doesn't croak when
        # faced with a vanilla SQLAlchemy session.
        #
        # Verifies that "AttributeError: 'SessionMaker' object has no attribute '_model_changes'"
        # is not thrown.
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True
        db = sqlalchemy.SQLAlchemy(app)
        Session = sessionmaker(bind=db.engine)

        class QazWsx(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            x = db.Column(db.String, default='')

        db.create_all()
        session = Session()
        session.add(QazWsx())
        # issues an INSERT.
        session.flush()
        session.expunge_all()
        qaz_wsx = session.query(QazWsx).first()
        assert qaz_wsx.x == ''
        qaz_wsx.x = 'test'
        # issues an UPDATE.
        session.flush()
        session.expunge_all()
        qaz_wsx = session.query(QazWsx).first()
        assert qaz_wsx.x == 'test'
        # issues a DELETE.
        session.delete(qaz_wsx)
        assert session.query(QazWsx).first() is None


class ActiveRecordTestCase(unittest.TestCase):
    def setUp(self):
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['SQLALCHEMY_ECHO'] = True
        app.config['TESTING'] = True
        db = sqlalchemy.SQLAlchemy(app)
        self.Todo = make_todo_model(db)
        self.User = make_user_model(db)
        db.create_all()
        self.app = app
        self.todo_list = self.create_models()

    def create_models(self):
        todo_list = list()
        todo_list.append(self.Todo.create(title="First Title", text="First Item"))
        todo_list.append(self.Todo.create(title="Second Title", text="Second Item"))
        todo_list.append(self.Todo.create(title="Third Title", text="Third Item"))

        self.User.create(name="Bill", todo=todo_list[0])
        self.User.create(name="Jane", todo=todo_list[1])
        return todo_list

    def test_count(self):
        self.assertEqual(self.Todo.count(), 3)
        self.assertEqual(self.Todo.where(id=2).count(), 1)

    def test_first(self):
        self.assertEqual(self.todo_list[0], self.Todo.first())

    def test_all(self):
        self.assertEqual(self.todo_list, self.Todo.all())

    def test_select(self):
        self.Todo.select('title').all()
        self.User.select('id', 'todo').all()

    def test_update(self):
        todo = self.Todo.first()
        text = "Primary Item"
        todo.update(text=text)
        self.assertEqual(text, self.Todo.first().text)

    def test_find_by(self):
        # match one field
        todo = self.Todo.find_by(title="First Title")
        self.assertEqual(self.todo_list[0], todo)
        # match multiple fileds
        todo = self.Todo.find_by(title="First Title", text="First Item")
        self.assertEqual(self.todo_list[0], todo)
        # mismatch
        todo = self.Todo.find_by(title="First Title", text="Second Item")
        self.assertFalse(todo)

    def test_exists(self):
        self.assertFalse(self.Todo.where(title="Bad Title").exists())
        self.assertTrue(self.Todo.where(title="Second Title").exists())

    def test_find_each(self):
        it = self.Todo.find_each()
        for i in range(len(self.todo_list)):
            self.assertTrue(next(it))

    def test_find_in_batches(self):
        # take 2 at a time from 3 element
        it = self.Todo.find_in_batches(2)
        self.assertEqual(2, len(next(it)))
        self.assertEqual(1, len(next(it)))

    def test_json_value(self):
        todo_json = self.todo_list[0].to_dict()
        self.assertTrue(isinstance(todo_json, dict))
        self.assertTrue('title' in todo_json and 'text' in todo_json)
        self.assertEqual(5, len(todo_json))

    def test_delete_and_destroy(self):
        self.todo_list[0].delete()
        self.assertEqual(2, self.Todo.count())
        self.Todo.destroy(2, 3)
        self.assertEqual(0, self.Todo.count())

    def test_order_by(self):
        todos = self.Todo.select('id').order_by('-id').all()
        for i in range(len(todos)):
            self.assertEqual(len(todos) - i, todos[i].id)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BasicAppTestCase))
    suite.addTest(unittest.makeSuite(TestQueryProperty))
    suite.addTest(unittest.makeSuite(HelperTestCase))
    suite.addTest(unittest.makeSuite(PaginationTestCase))
    suite.addTest(unittest.makeSuite(BindsTestCase))
    suite.addTest(unittest.makeSuite(DefaultQueryClassTestCase))
    suite.addTest(unittest.makeSuite(SQLAlchemyIncludesTestCase))
    suite.addTest(unittest.makeSuite(RegressionTestCase))
    suite.addTest(unittest.makeSuite(SessionScopingTestCase))
    suite.addTest(unittest.makeSuite(CommitOnTeardownTestCase))
    if flask.signals_available:
        suite.addTest(unittest.makeSuite(SignallingTestCase))
    suite.addTest(unittest.makeSuite(StandardSessionTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
