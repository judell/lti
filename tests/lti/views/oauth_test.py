# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import urllib
import urlparse

from lti.views import oauth
from lti import constants

import pytest
import mock
import requests
from pyramid import httpexceptions


pytestmark = pytest.mark.usefixtures(  # pylint:disable=invalid-name
    'requests_fixture',
    'log',
    'util',
)


class TestMakeAuthorizationRequest(object):

    def test_it_unpacks_the_state_param(self, pyramid_request, util):
        oauth.make_authorization_request(pyramid_request, mock.sentinel.state)

        util.unpack_state.assert_called_once_with(mock.sentinel.state)

    def test_it_logs_an_error_if_the_state_param_isnt_valid_json(self,
                                                                 pyramid_request,
                                                                 util,
                                                                 log):
        util.unpack_state.side_effect = ValueError()

        returned = oauth.make_authorization_request(pyramid_request,
                                                    mock.sentinel.state)

        # It logs the traceback.
        log.exception.assert_called_once_with("make_authorization_request() failed:")

        # It returns a simple HTML page with None for its body.
        util.simple_response.assert_called_once_with(util.unpack_state.side_effect)
        assert returned == util.simple_response.return_value

    def test_it_gets_the_canvas_servers_url_from_the_database(self,
                                                              pyramid_request,
                                                              auth_data_svc):
        oauth.make_authorization_request(pyramid_request, mock.sentinel.state)

        auth_data_svc.get_canvas_server.assert_called_once_with(
            'TEST_OAUTH_CONSUMER_KEY')

    def test_it_redirects_the_browser_back_to_canvas_for_authorization(
            self, pyramid_request):
        returned = oauth.make_authorization_request(pyramid_request,
                                                    mock.sentinel.state)

        # It redirects the browser.
        assert isinstance(returned, httpexceptions.HTTPFound)

        # It redirects to the correct URL.
        assert returned.location.startswith(
            'https://TEST_CANVAS_SERVER.com/login/oauth2/auth')

        # It puts the correct query params in the redirect URL.
        # We actually have to parse the query string here because Python dicts
        # are unordered which means that the _order_ of the different params
        # in the query string can change each time the test is run.
        parsed = urlparse.urlparse(returned.location)
        assert urlparse.parse_qs(parsed.query) == {
            'client_id': ['TEST_OAUTH_CONSUMER_KEY'],
            'response_type': ['code'],
            'redirect_uri': ['http://TEST_LTI_SERVER.com/oauth_callback'],
            'state': ['sentinel.state'],
        }


class TestOauthCallback(object):
    """Unit tests for oauth_callback"""

    def test_it_unpacks_the_state_param(self, pyramid_request, util):
        """
        It unpacks the ``state`` URL query param that Canvas sends to us.

        Canvas sends us a ``state`` query param that is a JSON-encoded,
        URL-quoted dict. We unpack this to get a bunch of variables out of it.

        """
        oauth.oauth_callback(pyramid_request)

        util.unpack_state.assert_called_once_with('TEST_OAUTH_STATE')


    def test_it_gets_the_client_secret_from_AuthData(self,
                                                     pyramid_request,
                                                     auth_data_svc):
        """
        It reads the OAuth 2.0 consumer's saved client secret from AuthData.

        The OAuth 2.0 consumer is identified by the ``oauth_consumer_key`` that
        we unpacked from the ``state`` query param that Canvas sent to us.
        We retrieve the saved client secret for this consumer from the
        ``AuthData`` object.

        We later POST this client secret to Canvas as part of our authorization
        code request.

        """
        oauth.oauth_callback(pyramid_request)

        auth_data_svc.get_lti_secret.assert_called_once_with(
            'TEST_OAUTH_CONSUMER_KEY')


    def test_it_gets_the_canvas_server_from_AuthData(self,
                                                     pyramid_request,
                                                     auth_data_svc):
        """It gets the URL of the Canvas server to login to from AuthData."""
        oauth.oauth_callback(pyramid_request)

        auth_data_svc.get_canvas_server.assert_called_once_with(
            'TEST_OAUTH_CONSUMER_KEY')

    def test_it_saves_the_oauth_access_and_refresh_tokens(self,
                                                          pyramid_request,
                                                          auth_data_svc):
        """It saves the tokens from Canvas to the AuthData object."""
        oauth.oauth_callback(pyramid_request)

        auth_data_svc.set_tokens.assert_called_once_with(
            'TEST_USER_ID',
            'TEST_OAUTH_CONSUMER_KEY',
            'TEST_OAUTH_ACCESS_TOKEN',
            'TEST_OAUTH_REFRESH_TOKEN',
        )

    def test_it_redirects_the_browser(self, pyramid_request):
        returned = oauth.oauth_callback(pyramid_request)

        # It redirects the browser.
        assert isinstance(returned, httpexceptions.HTTPFound)

        # It redirects to the correct URL.
        parsed = urlparse.urlparse(returned.location)
        assert parsed.scheme == 'http'
        assert parsed.netloc == 'example.com'
        assert parsed.path == '/lti_setup'

        # It puts the correct query params in the redirect URL.
        # We actually have to parse the query string here because Python dicts
        # are unordered which means that the _order_ of the different params
        # in the query string can change each time the test is run.
        assert urlparse.parse_qs(parsed.query) == {
            'assignment_name': ['TEST_ASSIGNMENT_NAME'],
            'assignment_type': ['TEST_ASSIGNMENT_TYPE'],
            'assignment_value': ['TEST_ASSIGNMENT_VALUE'],
            'custom_canvas_course_id': ['TEST_COURSE_ID'],
            'custom_canvas_user_id': ['TEST_USER_ID'],
            'ext_content_return_url': ['TEST_EXT_CONTENT_RETURN_URL'],
            'oauth_consumer_key': ['TEST_OAUTH_CONSUMER_KEY'],
        }

    def assert_that_it_logged_an_error(self, log, util, returned):
        """Do some assertions about what it does when any exception happens."""
        log.exception.assert_called_once()
        util.simple_response.assert_called_once()
        assert returned == util.simple_response.return_value

    def test_it_logs_an_error_if_authorization_code_missing(self,  # pylint:disable=too-many-arguments
                                                            pyramid_request,
                                                            log,
                                                            util):
        # Query string with no 'code' param.
        pyramid_request.query_string = urllib.urlencode({
            'state': 'TEST_OAUTH_STATE',
        })

        returned = oauth.oauth_callback(pyramid_request)

        self.assert_that_it_logged_an_error(log, util, returned)

    def test_it_logs_an_error_if_state_missing(self,  # pylint:disable=too-many-arguments
                                               pyramid_request,
                                               log,
                                               util):
        # Query string with no 'state' param.
        pyramid_request.query_string = urllib.urlencode({
            'code': 'TEST_OAUTH_AUTHORIZATION_CODE',
        })

        returned = oauth.oauth_callback(pyramid_request)

        self.assert_that_it_logged_an_error(log, util, returned)

    def test_it_logs_an_error_if_state_isnt_valid_json(self,  # pylint:disable=too-many-arguments
                                                       pyramid_request,
                                                       log,
                                                       util):

        # unpack_state() raises ValueError if state isn't valid JSON.
        util.unpack_state.side_effect = ValueError()

        returned = oauth.oauth_callback(pyramid_request)

        self.assert_that_it_logged_an_error(log, util, returned)

    @pytest.mark.parametrize('missing_field', [
        constants.CUSTOM_CANVAS_COURSE_ID,
        constants.CUSTOM_CANVAS_USER_ID,
        constants.OAUTH_CONSUMER_KEY,
        constants.EXT_CONTENT_RETURN_URL,
        constants.ASSIGNMENT_TYPE,
        constants.ASSIGNMENT_NAME,
        constants.ASSIGNMENT_VALUE,
    ])  # pylint:disable=too-many-arguments
    def test_it_logs_an_error_if_a_field_is_missing_from_state(self,
                                                               pyramid_request,
                                                               log,
                                                               util,
                                                               missing_field):
        del util.unpack_state.return_value[missing_field]

        returned = oauth.oauth_callback(pyramid_request)

        self.assert_that_it_logged_an_error(log, util, returned)

    # TODO: It would also log errors if AuthData raised any.

    def test_it_logs_an_error_if_Canvas_login_response_isnt_json(self,  # pylint:disable=too-many-arguments
                                                                 pyramid_request,
                                                                 log,
                                                                 util,
                                                                 requests_fixture):
        # The requests lib's Response object's .json() method raises ValueError
        # if the response isn't a JSON response.
        requests_fixture.post.return_value.json.side_effect = ValueError()

        returned = oauth.oauth_callback(pyramid_request)

        self.assert_that_it_logged_an_error(log, util, returned)

    def test_it_logs_an_error_if_Canvas_login_response_lacks_access_token(self,  # pylint:disable=too-many-arguments
                                                                          pyramid_request,
                                                                          log,
                                                                          util,
                                                                          requests_fixture):

        del requests_fixture.post.return_value.json.return_value['access_token']

        returned = oauth.oauth_callback(pyramid_request)

        self.assert_that_it_logged_an_error(log, util, returned)


    def test_it_posts_an_authorization_code_request_to_canvas(self,
                                                              pyramid_request,
                                                              requests_fixture):
        oauth.oauth_callback(pyramid_request)

        requests_fixture.post.assert_called_once_with(
            'https://TEST_CANVAS_SERVER.com/login/oauth2/token',
            {
                'code': 'TEST_OAUTH_AUTHORIZATION_CODE',
                'grant_type': 'authorization_code',

                # The client secret that we retrieved from AuthData.
                'client_secret': 'TEST_CLIENT_SECRET',

                'client_id': u'TEST_OAUTH_CONSUMER_KEY',
                'redirect_uri': 'http://TEST_LTI_SERVER.com/oauth_callback',
            },
        )


@pytest.fixture
def requests_fixture(patch):
    requests_patch = patch('lti.views.oauth.requests')

    # The HTTP response that Canvas returns to our /login/oauth2/token
    # request. Note this is a ``requests`` library ``Response`` object,
    # not a Pyramid ``Response``.
    requests_patch.post.return_value = mock.create_autospec(requests.Response,
                                                            instance=True)
    requests_patch.post.return_value.json.return_value = {
        'access_token': 'TEST_OAUTH_ACCESS_TOKEN',
        'refresh_token': 'TEST_OAUTH_REFRESH_TOKEN',
    }

    return requests_patch


@pytest.fixture
def log(patch):
    return patch('lti.views.oauth.log')


@pytest.fixture
def pyramid_request(pyramid_request):
    # When it calls the oauth_callback or refresh_callback route,
    # Canvas calls with an OAuth authorization code and state in the
    # query params.
    pyramid_request.query_string = urllib.urlencode({
        'code': 'TEST_OAUTH_AUTHORIZATION_CODE',
        'state': 'TEST_OAUTH_STATE',
    })
    return pyramid_request


@pytest.fixture
def util(patch):
    util = patch('lti.views.oauth.util')

    # When it calls the oauth_callback route,
    # Canvas calls with a course ID, user ID, etc etc packed into
    # `state` URL query parameter. (The `state` query params is a
    # JSON-encoded, URL-quoted dict containing course ID, user ID, etc.)
    util.unpack_state.return_value = {
        constants.CUSTOM_CANVAS_COURSE_ID: 'TEST_COURSE_ID',
        constants.CUSTOM_CANVAS_USER_ID: 'TEST_USER_ID',
        constants.OAUTH_CONSUMER_KEY: 'TEST_OAUTH_CONSUMER_KEY',
        constants.EXT_CONTENT_RETURN_URL: 'TEST_EXT_CONTENT_RETURN_URL',
        constants.EXT_CONTENT_RETURN_TYPES: 'TEST_EXT_CONTENT_RETURN_TYPES',
        constants.EXT_CONTENT_RETURN_URL: 'TEST_EXT_CONTENT_RETURN_URL',
        constants.LIS_OUTCOME_SERVICE_URL: 'TEST_LIS_OUTCOME_SERVICE_URL',
        constants.LIS_RESULT_SOURCEDID: 'TEST_LIS_RESULT_SOURCEDID',
        constants.ASSIGNMENT_TYPE: 'TEST_ASSIGNMENT_TYPE',
        constants.ASSIGNMENT_NAME: 'TEST_ASSIGNMENT_NAME',
        constants.ASSIGNMENT_VALUE: 'TEST_ASSIGNMENT_VALUE',
    }

    return util

