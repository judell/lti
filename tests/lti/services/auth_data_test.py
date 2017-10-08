# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from sqlalchemy.orm.exc import NoResultFound
import pytest

from lti.models import OAuth2AccessToken
from lti.models import OAuth2Credentials
from lti import services


class TestAuthData(object):
    """Unit tests for the AuthData class."""

    def test_get_lti_token(self, auth_data):
        actual = auth_data.get_lti_token("TEST_USER_ID", "93820000000000002")
        expected = "9382~IAbeGEFScV  ... IIMaEdK3dXlm2d9cjozd"
        assert actual == expected

    def test_get_lti_token_raises_KeyError_if_oauth_consumer_key_doesnt_exist(self, auth_data):
        with pytest.raises(KeyError):
            auth_data.get_lti_token("USER_ID", "KEY_DOES_NOT_EXIST")

    def test_get_lti_refresh_token(self, auth_data):
        actual = auth_data.get_lti_refresh_token("TEST_USER_ID", "93820000000000002")
        expected = "9382~yRo ... Rlid9UXLhxfvwkWDnj"
        assert actual == expected

    def test_get_lti_refresh_token_raises_KeyError_if_key_doesnt_exist(self, auth_data):
        with pytest.raises(KeyError):
            auth_data.get_lti_refresh_token("TEST_USER_ID", "KEY_DOES_NOT_EXIST")

    def test_get_lti_refresh_token_returns_None_if_theres_no_token(self,
                                                                   auth_data,
                                                                   db_session):
        oauth2_credentials = OAuth2Credentials(
                   client_id='OTHER_CLIENT_ID',
                   client_secret='OTHER_CLIENT_SECRET',
                   authorization_server='OTHER_AUTH_SERVER',
                   )

        db_session.add(oauth2_credentials)

        db_session.flush()

        db_session.add(OAuth2AccessToken(
            user_id='TEST_USER_ID',
            client_id='OTHER_CLIENT_ID',
            access_token='TEST_ACCESS_TOKEN',
            refresh_token=None,
        ))

        assert auth_data.get_lti_refresh_token('TEST_USER_ID', 'OTHER_CLIENT_ID') is None

    def test_get_lti_secret(self, auth_data):
        actual = auth_data.get_lti_secret("93820000000000002")
        expected = "tJzcNSZadqlHTCW6ow  ... wodX3dfeuIokkLMjrQJqw3Y2"
        assert actual == expected

    def test_get_lti_secret_raises_KeyError_if_oauth_consumer_key_doesnt_exist(self, auth_data):
        with pytest.raises(KeyError):
            auth_data.get_lti_secret("KEY_DOES_NOT_EXIST")

    def test_get_canvas_server(self, auth_data):
        actual = auth_data.get_canvas_server("93820000000000002")
        expected = "https://hypothesis.instructure.com:1000"
        assert actual == expected

    def test_get_canvas_server_raises_KeyError_if_key_doesnt_exist(self, auth_data):
        with pytest.raises(KeyError):
            auth_data.get_canvas_server("KEY_DOES_NOT_EXIST")

    def test_set_tokens(self, auth_data):
        auth_data.set_tokens("TEST_USER_ID", "93820000000000002", "new_lti_token", "new_refresh_token")
        assert auth_data.get_lti_token("TEST_USER_ID", "93820000000000002") == "new_lti_token"
        assert auth_data.get_lti_refresh_token("TEST_USER_ID", "93820000000000002") == "new_refresh_token"


    def test_set_tokens_throws_assertion_error_if_key_doesnt_exist(self, auth_data):
        with pytest.raises(NoResultFound):
            auth_data.set_tokens("NO_SUCH_USER", "KEY_DOES_NOT_EXIST", "new_lti_token", "new_refresh_token")


@pytest.fixture
def db_session(db_session):
    oauth2_credentials = OAuth2Credentials(
                   client_id='93820000000000002',
                   client_secret='tJzcNSZadqlHTCW6ow  ... wodX3dfeuIokkLMjrQJqw3Y2',
                   authorization_server='https://hypothesis.instructure.com:1000',
                   )

    db_session.add(oauth2_credentials)

    db_session.flush()

    oauth2_access_token = OAuth2AccessToken(
            user_id="TEST_USER_ID",
            client_id='93820000000000002',
            access_token='9382~IAbeGEFScV  ... IIMaEdK3dXlm2d9cjozd',
            refresh_token='9382~yRo ... Rlid9UXLhxfvwkWDnj',
        )

    db_session.add(oauth2_access_token)

    return db_session


@pytest.fixture
def auth_data(db_session):
    return services.auth_data.AuthDataService(db_session)
