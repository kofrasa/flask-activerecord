"""
Flask-ActiveRecord
------------------

An active record patch for Flask-SQLAlchemy model
"""

from setuptools import setup
import flask_activerecord as ar


def read_file(name):
    with open(name, 'r') as f:
        return f.read()


setup(
    name='Flask-ActiveRecord',
    version=ar.__version__,
    license='BSD',
    author='Francis Asante',
    author_email='kofrasa@gmail.com',
    url='https://github.com/kofrasa/flask-activerecord',
    description='An active record patch for Flask-SQLAlchemy models',
    long_description=read_file('README.rst'),
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