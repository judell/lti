# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pytest
from sqlalchemy.exc import IntegrityError

from lti.models import OAuth2Credentials
from lti.models import OAuth2AccessToken


class TestOAuth2Credentials(object):

    def test_it_persists_the_id_secret_and_server(self, db_session):
        db_session.add(OAuth2Credentials(client_id="TEST_ID",
                                         client_secret="TEST_SECRET",
                                         authorization_server="TEST_AUTH_SERVER"))

        persisted = db_session.query(OAuth2Credentials).filter_by(client_id="TEST_ID").one()
        assert persisted.client_id == "TEST_ID"
        assert persisted.client_secret == "TEST_SECRET"
        assert persisted.authorization_server == "TEST_AUTH_SERVER"

    def test_you_can_have_two_oauth2_credentials_with_the_same_server(self, db_session):
        # You can have two OAuth2Credential's for the same server in the db,
        # as long as they have different IDs. This might happen if two
        # different admins create two different developer keys for us in the
        # same Canvas instance, for example.
        db_session.add(OAuth2Credentials(client_id="FIRST_ID",
                                         client_secret="FIRST_SECRET",
                                         authorization_server="TEST_AUTH_SERVER"))
        db_session.add(OAuth2Credentials(client_id="SECOND_ID",
                                         client_secret="SECOND_SECRET",
                                         authorization_server="TEST_AUTH_SERVER"))

        db_session.commit()

    @pytest.mark.filterwarnings("ignore:Column 'oauth2_credentials.client_id' is marked as a member of")
    def test_id_is_required(self, db_session):
        db_session.add(OAuth2Credentials(client_secret="FIRST_SECRET",
                                         authorization_server="TEST_AUTH_SERVER"))

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_id_cant_be_None(self, db_session):
        db_session.add(OAuth2Credentials(client_id=None,
                                         client_secret="TEST_SECRET",
                                         authorization_server="TEST_AUTH_SERVER"))

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_client_secret_is_required(self, db_session):
        db_session.add(OAuth2Credentials(client_id="TEST_ID",
                                         authorization_server="TEST_AUTH_SERVER"))

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_client_secret_cant_be_None(self, db_session):
        db_session.add(OAuth2Credentials(client_id="TEST_ID",
                                         client_secret=None,
                                         authorization_server="TEST_AUTH_SERVER"))

        expected_message = 'null value in column "client_secret" violates not-null constraint'
        with pytest.raises(IntegrityError, match=expected_message):
            db_session.flush()

    def test_authorization_server_is_required(self, db_session):
        db_session.add(OAuth2Credentials(client_id="TEST_ID", client_secret="TEST_SECRET"))

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_authorization_server_cant_be_None(self, db_session):
        db_session.add(OAuth2Credentials(client_id="TEST_ID",
                                         client_secret="TEST_SECRET",
                                         authorization_server=None))

        expected_message = ('null value in column "authorization_server" '
                            'violates not-null constraint')
        with pytest.raises(IntegrityError, match=expected_message):
            db_session.flush()

