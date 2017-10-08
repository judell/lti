# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from sqlalchemy.exc import IntegrityError
import pytest

from lti.models import OAuth2AccessToken, OAuth2Credentials


class TestOAuth2AccessToken(object):

    def test_it_persists_the_client_id_access_token_and_refresh_token(self,
                                                                      db_session):

        db_session.add(OAuth2Credentials(client_id="TEST_CLIENT_ID",
                                         client_secret="TEST_CLIENT_SECRET",
                                         authorization_server="TEST_AUTHORIZATION_SERVER"))

        db_session.flush()  

        db_session.add(OAuth2AccessToken(user_id="TEST_USER_ID",
                                         client_id="TEST_CLIENT_ID",
                                         access_token="TEST_ACCESS_TOKEN",
                                         refresh_token="TEST_REFRESH_TOKEN"))

        persisted = db_session.query(OAuth2AccessToken).one()
     
        assert persisted.client_id == "TEST_CLIENT_ID"
        assert persisted.access_token == "TEST_ACCESS_TOKEN"
        assert persisted.refresh_token == "TEST_REFRESH_TOKEN"


    def test_unique_ids_are_automatically_generated(self, db_session):

        db_session.add(OAuth2Credentials(client_id="TEST_CLIENT_ID",
                                         client_secret="TEST_CLIENT_SECRET",
                                         authorization_server="TEST_AUTHORIZATION_SERVER"))

        db_session.flush()  

        access_token = (OAuth2AccessToken(user_id="TEST_USER_ID",
                                         client_id="TEST_CLIENT_ID",
                                         access_token="TEST_ACCESS_TOKEN",
                                         refresh_token="TEST_REFRESH_TOKEN"))

        db_session.add(access_token)
        db_session.flush()  # The id is generated when the session is flushed.

        assert access_token.id


    def test_client_id_must_refer_to_an_existing_client_id(self, db_session):


        db_session.add(OAuth2Credentials(client_id="TEST_CLIENT_ID",
                                         client_secret="TEST_CLIENT_SECRET",
                                         authorization_server="TEST_AUTHORIZATION_SERVER"))

        db_session.flush()

        db_session.add(OAuth2AccessToken(user_id="TEST_USER_ID",
                                         client_id="DOES_NOT_EXIST",
                                         access_token="TEST_ACCESS_TOKEN",
                                         refresh_token="TEST_REFRESH_TOKEN"))

        with pytest.raises(IntegrityError):
            db_session.flush()

        db_session.close()


    def test_client_id_cant_be_None(self, db_session):

        db_session.add(OAuth2Credentials(client_id="TEST_CLIENT_ID",
                                         client_secret="TEST_CLIENT_SECRET",
                                         authorization_server="TEST_AUTHORIZATION_SERVER"))

        db_session.flush()

        db_session.add(OAuth2AccessToken(user_id="TEST_USER_ID",
                                         client_id=None,
                                         access_token="TEST_ACCESS_TOKEN",
                                         refresh_token="TEST_REFRESH_TOKEN"))

        expected_message = 'null value in column "client_id" violates not-null constraint'
        with pytest.raises(IntegrityError, match=expected_message):
            db_session.flush()


    def test_access_token_cant_be_None(self, db_session):


        db_session.add(OAuth2Credentials(client_id="TEST_CLIENT_ID",
                                         client_secret="TEST_CLIENT_SECRET",
                                         authorization_server="TEST_AUTHORIZATION_SERVER"))

        db_session.flush()

        db_session.add(OAuth2AccessToken(user_id="TEST_USER_ID",
                                         client_id="TEST_CLIENT_ID",
                                         access_token=None,
                                         refresh_token="TEST_REFRESH_TOKEN"))


        expected_message = 'null value in column "access_token" violates not-null constraint'
        with pytest.raises(IntegrityError, match=expected_message):
            db_session.flush()


    def test_refresh_token_can_be_None(self, db_session, oauth2_credentials):
        db_session.add(OAuth2Credentials(client_id="TEST_CLIENT_ID",
                                         client_secret="TEST_CLIENT_SECRET",
                                         authorization_server="TEST_AUTHORIZATION_SERVER"))

        db_session.flush()

        db_session.add(OAuth2AccessToken(user_id="TEST_USER",
                                         client_id="TEST_CLIENT_ID",
                                         access_token="TEST_ACCESS_TOKEN",
                                         refresh_token=None))

    @pytest.fixture
    def oauth2_credentials(self, factories):
        return factories.OAuth2Credentials()

