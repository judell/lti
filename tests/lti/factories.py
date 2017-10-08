# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import factory
import faker

from lti import models

FAKER = faker.Factory.create()
SESSION = None


def set_session(value):
    global SESSION  # pylint:disable=global-statement

    SESSION = value


class ModelFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Base class for all factory classes for model classes."""

    class Meta(object):
        abstract = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # We override SQLAlchemyModelFactory's default _create classmethod so
        # that rather than fetching the session from cls._meta (which is
        # created at parse time... ugh) we fetch it from the SESSION global,
        # which is dynamically filled out by the `factories` fixture when
        # used.
        if SESSION is None:
            raise RuntimeError('no session: did you use the factories fixture?')
        obj = model_class(*args, **kwargs)
        SESSION.add(obj)
        if cls._meta.sqlalchemy_session_persistence == 'flush':
            SESSION.flush()
        return obj


class OAuth2Credentials(ModelFactory):

    class Meta(object):
        model = models.OAuth2Credentials
        sqlalchemy_session_persistence = 'flush'

    client_id = factory.sequence(lambda n: 'TEST_CLIENT_ID_' + str(n))
    client_secret = factory.sequence(lambda n: 'TEST_CLIENT_SECRET_' + str(n))
    authorization_server = 'TEST_AUTHORIZATION_SERVER'


class OAuth2AccessToken(ModelFactory):

    class Meta(object):
        model = models.OAuth2AccessToken
        sqlalchemy_session_persistence = 'flush'

    authorization_server = 'TEST_AUTHORIZATION_SERVER'
    user_id = factory.sequence(lambda n: 'TEST_USER_ID_' + str(n))
    access_token = factory.sequence(lambda n: 'TEST_ACCESS_TOKEN_' + str(n))
    refresh_token = factory.sequence(lambda n: 'TEST_REFRESH_TOKEN_' + str(n))
