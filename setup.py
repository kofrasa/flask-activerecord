"""
Flask-ActiveRecord
------------------

ActiveRecord mixin implementation providing Rails-style utilities for Flask-SQLAlchemy models
"""

from setuptools import setup


setup(
    name='Flask-ActiveRecord',
    version='0.1',
    license='BSD',
    author='Francis Asante',
    author_email='kofrasa@gmail.com',
    url='http://github.com/kofrasa/flask-activerecord',
    description='ActiveRecord mixin implementation providing rails-style utilities for Flask-SQLAlchemy models',
    long_description=__doc__,
    packages=['flask_activerecord'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask-SQLAlchemy'
    ],
    test_suite='tests',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)