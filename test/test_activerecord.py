#!/usr/bin/env python
#-*- coding: utf-8 -*-
__author__ = 'francis'

import unittest
from unittest import TestCase
from flask import Flask
from flask_sqlalchemy import SQLAlchemy


def create_user_model(db):
    pass


def create_contact_model(db):
    pass


class ActiveRecordTestCase(TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        self.app.config['TESTING'] = True
        self.db = SQLAlchemy(self.app)


if __name__ == '__main__':
    unittest.main()