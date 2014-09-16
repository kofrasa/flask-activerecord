"""
Flask-ActiveRecord
------------------

ActiveRecord patch for Flask-SQLAlchemy models which provides flexible and dynamic query methods
"""

from setuptools import setup


setup(
    name='Flask-ActiveRecord',
    version='0.1',
    license='BSD',
    author='Francis Asante',
    author_email='kofrasa@gmail.com',
    url='http://github.com/kofrasa/flask-activerecord',
    description='ActiveRecord patch for Flask-SQLAlchemy models which provides flexible and dynamic query methods',
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