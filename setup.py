"""
Flask-ActiveRecord
------------------

ActiveRecord support for Flask-SQLAlchemy models

.. code:: python

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
"""

from setuptools import setup
from flask_activerecord import __version__


setup(
    name='Flask-ActiveRecord',
    version=__version__,
    license='BSD',
    author='Francis Asante',
    author_email='kofrasa@gmail.com',
    url='https://github.com/kofrasa/flask-activerecord',
    description='ActiveRecord support for Flask-SQLAlchemy models',
    long_description=__doc__,
    py_modules=['flask_activerecord'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask-SQLAlchemy>=2.0'
    ],
    test_suite='test_activerecord.suite',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)