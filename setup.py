"""
Flask-ActiveRecord
------------------

ActiveRecord patch for Flask-SQLAlchemy models which provides flexible query methods
"""

from setuptools import setup


setup(
    name='Flask-ActiveRecord',
    version='0.1',
    license='BSD',
    author='Francis Asante',
    author_email='kofrasa@gmail.com',
    url='http://github.com/kofrasa/flask-activerecord',
    description='ActiveRecord patch for Flask-SQLAlchemy models which provides flexible query methods',
    long_description=__doc__,
    packages=['flask_activerecord'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Flask>=0.10',
        'SQLAlchemy',
        'Flask-SQLAlchemy'
    ],
    test_suite='test_activerecord.suite',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)