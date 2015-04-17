Flask-ActiveRecord
==================
Enable ActiveRecord support pattern for Flask-SQLAlchemy models and enjoy rails-style queries

Install
-------
install from pip ::

    $ pip install flask-activerecord

Usage
-----
::

    from flask.ext.sqlalchemy import SQLAlchemy
    from flask.ext.activerecord import patch_model
    
    # patch model first
    patch_model()

    app = Flask(__name__)
    db = SQLAlchemy(app)

    # example model

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

License
-------
BSD