# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging

from sqlalchemy.orm.exc import NoResultFound

from lti.models import OAuth2Credentials
from lti.models import OAuth2AccessToken

#logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
log = logging.getLogger(__name__)


# FIXME: This currently reads and writes the data to and from a JSON file, with
# the file reading and writing happening in the AuthDataService class itself.
# It should be changed to use SQLAlchemy, and to have AuthDataService
# communicate only with model classes that handle reading/writing from/to the
# db.
#
# FIXME: This currently stores one access token and refresh token pair per
# authorization server. It should be one per user account, where each
# authorization server has many user accounts.
#
# FIXME: This currently uses Canvas developer key IDs to identify authorization
# servers, but these don't look like they're globally unique. Two different
# authorization servers (i.e. two different Canvas instances) could have the
# same developer key ID. See https://github.com/hypothesis/lti/issues/14
class AuthDataService(object):
    """
    A service for getting and setting OAuth 2.0 authorization info.

    Lets you set the access token and refresh token for an authorization
    server.

    Lets you get the access token, refresh token, client secret, and URL for
    an authorization server.

    """

    def __init__(self, db):
        self._db = db

    def set_tokens(self, user_id, oauth_consumer_key, lti_token, lti_refresh_token):

        # Delete existing access/refresh token for this user
        access_token = self._db.query(OAuth2AccessToken).filter_by(
            user_id=user_id,
            client_id=oauth_consumer_key).one()
        self._db.delete(access_token)

        print 'set tokens user %s, key %s, token %s, refresh %s' % (
            user_id, oauth_consumer_key, lti_token, lti_refresh_token)

        # Save a new access and refresh token pair.

        oauth2_access_token = (OAuth2AccessToken(
                                  user_id=user_id,
                                  client_id=oauth_consumer_key,
                                  access_token=lti_token,
                                  refresh_token=lti_refresh_token,
                                  ))

        self._db.add(oauth2_access_token)
         

    def get_lti_token(self, user_id, oauth_consumer_key):
        print 'getting lti_token %s, %s' % (user_id, oauth_consumer_key)
        try:
            access_token = self._db.query(OAuth2AccessToken).filter_by(
                user_id=user_id,
                client_id=oauth_consumer_key).one()
            print 'got lti_token for %s, %s: %s' % (user_id, oauth_consumer_key, access_token)
        except NoResultFound:
            print 'no lti_token for %s, %s' % (user_id, oauth_consumer_key)
            raise KeyError

        if access_token is None:
            return None
        return access_token.access_token

    def get_lti_refresh_token(self, user_id, oauth_consumer_key):
        try:
            access_token = self._db.query(OAuth2AccessToken).filter_by(
                user_id=user_id,
                client_id=oauth_consumer_key).one()
        except NoResultFound:
            raise KeyError

        if access_token is None:
            return None
        return access_token.refresh_token

    def get_lti_secret(self, oauth_consumer_key):
        return self._credentials_for(oauth_consumer_key).client_secret

    def get_canvas_server(self, oauth_consumer_key):
        return self._credentials_for(oauth_consumer_key).authorization_server

    def _credentials_for(self, oauth_consumer_key):
        try:
            print '_credentials_for %s' % oauth_consumer_key
            ret = self._db.query(OAuth2Credentials).filter_by(
                client_id=oauth_consumer_key).one()
            print 'found %s' % ret.__dict__
            return ret
        except NoResultFound:
            print 'not found'
            # We raise KeyError here just to maintain compatibility with
            # the legacy API of auth_data, for now.
            raise KeyError


def auth_data_service_factory(context, request):  # pylint: disable=unused-argument
    return AuthDataService(request.db)
