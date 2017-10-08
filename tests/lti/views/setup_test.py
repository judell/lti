# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import urllib

import pytest
import mock
from requests.models import Response

from lti import constants
from lti.views import setup

pytestmark = pytest.mark.usefixtures(  # pylint:disable=invalid-name
    'simple_response',
    'requests',
    'render',
    'files_api_call',
    'pack_state',
    'oauth',
    'web',
    'pdf',
)


class SharedLTISetupTests(object):

    def test_it_gets_the_canvas_servers_url_from_the_database(self,
                                                              pyramid_request,
                                                              auth_data_svc):
        setup.lti_setup(pyramid_request)

        auth_data_svc.get_canvas_server.assert_called_once_with(
            'TEST_OAUTH_CONSUMER_KEY')

    def test_it_returns_chooser_when_assignment_type_is_none(
            self, pyramid_resource_selection_request, render, auth_data_svc):

        setup.lti_setup(pyramid_resource_selection_request)
        
        assert 'pdf_choices' in render.call_args[0][1].keys() 

    def test_theres_no_course_param_it_returns_an_error_page(
            self, pyramid_request, simple_response):
        del pyramid_request.POST[constants.CUSTOM_CANVAS_COURSE_ID]

        returned = setup.lti_setup(pyramid_request)

        simple_response.assert_called_once_with(
            'No course number. Was Privacy set to Public for this '
            'installation of the Hypothesis LTI app? If not please do so (or '
            'ask someone who can to do so).')
        assert returned == simple_response.return_value

    def test_it_gets_the_access_token_from_the_db(self, pyramid_request, auth_data_svc):
        setup.lti_setup(pyramid_request)

        auth_data_svc.get_lti_token.assert_called_once_with(
            'TEST_CANVAS_USER_ID',
            'TEST_OAUTH_CONSUMER_KEY')

    def test_if_we_dont_have_the_consumer_key_it_returns_an_error_page(
            self, pyramid_request, simple_response, auth_data_svc):
        # get_lti_token() raises KeyError if the given consumer key doesn't
        # exist in the db.

        auth_data_svc.get_canvas_server.side_effect = KeyError

        returned = setup.lti_setup(pyramid_request)

        error_message = (
            "We don't have the Consumer Key TEST_OAUTH_CONSUMER_KEY in our "
            "database yet.")
        simple_response.assert_called_once_with(error_message)
        assert returned == simple_response.return_value


class TestLTISetupWhenWeDontHaveAnAccessToken(SharedLTISetupTests):
    """
    Unit tests for lti_setup() when we don't have an access token.

    These test what lti_setup() does when we _do_ have the consumer key in the
    db, but we don't yet have an access token for that consumer key.

    """

    def test_it_packs_the_launch_params_into_a_string(
            self, pyramid_request, pack_state):
        auth_data_svc = pyramid_request.find_service(name='auth_data')
        auth_data_svc.get_lti_token.return_value = None

        setup.lti_setup(pyramid_request)

        pack_state.assert_called_once_with({
            constants.ASSIGNMENT_VALUE: 'TEST_ASSIGNMENT_URL',
            constants.ASSIGNMENT_NAME: 'TEST_ASSIGNMENT_NAME',
            constants.ASSIGNMENT_TYPE: 'TEST_ASSIGNMENT_TYPE',
            constants.CUSTOM_CANVAS_ASSIGNMENT_ID: 'TEST_ASSIGNMENT_ID',
            constants.CUSTOM_CANVAS_COURSE_ID: 'TEST_COURSE_ID',
            constants.CUSTOM_CANVAS_USER_ID: 'TEST_CANVAS_USER_ID',
            constants.EXT_CONTENT_RETURN_TYPES: 'TEST_EXT_CONTENT_RETURN_TYPES',
            constants.EXT_CONTENT_RETURN_URL: 'TEST_EXT_CONTENT_RETURN_URL',
            constants.LIS_OUTCOME_SERVICE_URL: 'TEST_LIS_OUTCOME_SERVICE_URL',
            constants.LIS_RESULT_SOURCEDID: 'TEST_LIS_RESULT_SOURCEDID',
            constants.OAUTH_CONSUMER_KEY: 'TEST_OAUTH_CONSUMER_KEY',
        })


    def test_it_starts_an_oauth_flow_to_get_access_token(self,
                                                         pyramid_request,
                                                         pack_state,
                                                         oauth,
                                                         ):
        auth_data_svc = pyramid_request.find_service(name='auth_data')
        auth_data_svc.get_lti_token.return_value = None
       
        returned = setup.lti_setup(pyramid_request)

        oauth.token_init.assert_called_once_with(
            pyramid_request, pack_state.return_value)

        assert returned == oauth.token_init.return_value


class TestLTISetupWhenWeOurAccessTokenHasExpired(SharedLTISetupTests):
    """Unit tests for lti_setup() when our access token is expired."""

    def test_it_starts_an_oauth_flow_to_refresh_access_token(self,
                                                                 pyramid_request,
                                                                 oauth,
                                                                 pack_state,
                                                                 files_api_call):

        canvas_api_response = Response()
        canvas_api_response.status_code = 401
        files_api_call.return_value = canvas_api_response

        returned = setup.lti_setup(pyramid_request)

        oauth.refresh_init.assert_called_once_with(
            pyramid_request, pack_state.return_value)
        assert returned == oauth.refresh_init.return_value


class TestLTISetupWhenWeHaveAValidAccessToken(SharedLTISetupTests):
    """Unit tests for lti_setup() when we have a valid access token."""


    def test_it_gets_the_courses_files(self, pyramid_request, auth_data_svc, files_api_call):
        setup.lti_setup(pyramid_request)

        # It makes an initial request to the Canvas API to get
        # the first page of results from a files API call
        files_api_call.assert_called_once_with(
            auth_data_svc,
            'TEST_OAUTH_CONSUMER_KEY',
            'TEST_COURSE_ID',
            'TEST_OAUTH_ACCESS_TOKEN',
        )

    """
    def test_it_requests_every_page_of_the_files_list(self,
                                                      pyramid_request,
                                                      files_api_call):
        setup.lti_setup(pyramid_request)

        assert files_api_call.call_args_list == [
            mock.call(
                headers={'Authorization': 'Bearer TEST_OAUTH_ACCESS_TOKEN'},
                url='https://TEST_CANVAS_SERVER.com/api/v1/courses/TEST_COURSE_ID/files?per_page=100',
            ),
            mock.call(
                headers={'Authorization': 'Bearer TEST_OAUTH_ACCESS_TOKEN'},
                url='SECOND_PAGE',
            ),
            mock.call(
                headers={'Authorization': 'Bearer TEST_OAUTH_ACCESS_TOKEN'},
                url='THIRD_PAGE',
            ),
        ]


    """

    def test_it_returns_lti_pdf_when_its_a_pdf_assignment(self,
                                                          pyramid_request,
                                                          pdf):
        # FIXME: We shouldn't have to actually encode a query string in tests
        # like this.
        pyramid_request.query_string = urllib.urlencode({
            constants.ASSIGNMENT_VALUE: 'TEST_ASSIGNMENT_VALUE',
            constants.ASSIGNMENT_NAME: 'TEST_ASSIGNMENT_NAME',
            constants.ASSIGNMENT_TYPE: 'pdf',
            constants.CUSTOM_CANVAS_USER_ID: 'TEST_USER_ID',
        })

        returned = setup.lti_setup(pyramid_request)

        pdf.lti_pdf.assert_called_once_with(
            pyramid_request,
            user_id='TEST_USER_ID',
            oauth_consumer_key='TEST_OAUTH_CONSUMER_KEY',
            lis_outcome_service_url='TEST_LIS_OUTCOME_SERVICE_URL',
            lis_result_sourcedid='TEST_LIS_RESULT_SOURCEDID',
            course='TEST_COURSE_ID',
            name='TEST_ASSIGNMENT_NAME',
            value='TEST_ASSIGNMENT_VALUE',
        )
        assert returned == pdf.lti_pdf.return_value

    def test_it_returns_web_response_when_its_a_web_assignment(self,
                                                               pyramid_request,
                                                               web):
        # FIXME: We shouldn't have to actually encode a query string in tests
        # like this.
        pyramid_request.query_string = urllib.urlencode({
            constants.ASSIGNMENT_VALUE: 'TEST_ASSIGNMENT_URL',
            constants.ASSIGNMENT_NAME: 'TEST_ASSIGNMENT_NAME',
            constants.ASSIGNMENT_TYPE: 'web',
            constants.CUSTOM_CANVAS_USER_ID: 'TEST_USER_ID',

        })

        returned = setup.lti_setup(pyramid_request)

        web.web_response.assert_called_once_with(
            pyramid_request,
            user_id='TEST_USER_ID',
            oauth_consumer_key='TEST_OAUTH_CONSUMER_KEY',
            lis_outcome_service_url='TEST_LIS_OUTCOME_SERVICE_URL',
            lis_result_sourcedid='TEST_LIS_RESULT_SOURCEDID',
            name='TEST_ASSIGNMENT_NAME',
            url='TEST_ASSIGNMENT_URL',
        )
        assert returned == web.web_response.return_value

    """
    def test_it_omits_non_pdf_files(self, pyramid_request, requests, render):
        # Make Canvas return three uploaded files, one of them is not a PDF
        # file.
        requests.Session.return_value.get.side_effect = None
        requests.Session.return_value.get.return_value = mock.MagicMock(
            json=mock.MagicMock(return_value=[
                {'id': 1, 'display_name': 'File One.pdf'},
                {'id': 2, 'display_name': 'File Two.doc'},
                {'id': 3, 'display_name': 'File Three.pdf'},
            ]),
        )

        setup.lti_setup(pyramid_request)

        # Only the two PDF files are rendered.
        assert render.call_args[0][1]['pdf_choices'] == (
            '<ul>'
            '<li>'
            '<input type="radio" '
            'name="pdf_choice" '
            'onclick="javascript:go()" '
            'value="File One.pdf" '
            'id="1">'
            'File One.pdf'
            '</li>'
            '<li>'
            '<input type="radio" '
            'name="pdf_choice" '
            'onclick="javascript:go()" '
            'value="File Three.pdf" '
            'id="3">'
            'File Three.pdf'
            '</li>'
            '</ul>'
        )

    def test_PDF_files_are_still_rendered(self, pyramid_request, requests, render):
        # The filename ends in ".PDF" not ".pdf".
        requests.Session.return_value.get.side_effect = None
        requests.Session.return_value.get.return_value = mock.MagicMock(
            json=mock.MagicMock(return_value=[
                {'id': 1, 'display_name': 'File One.PDF'},
            ]),
        )

        setup.lti_setup(pyramid_request)

        assert render.call_args[0][1]['pdf_choices'] == (
            '<ul>'
            '<li>'
            '<input type="radio" '
            'name="pdf_choice" '
            'onclick="javascript:go()" '
            'value="File One.PDF" '
            'id="1">'
            'File One.PDF'
            '</li>'
            '</ul>'
        )
    """

    def test_it_can_also_read_return_url_as_return_url(self,
                                                       pyramid_request,
                                                       render):
        del pyramid_request.POST[constants.EXT_CONTENT_RETURN_URL]
        pyramid_request.query_string = urllib.urlencode({
            'return_url': 'OAUTH_REDIRECT_RETURN_URL',
        })

        setup.lti_setup(pyramid_request)

        assert render.call_args[0][1]['return_url'] == 'OAUTH_REDIRECT_RETURN_URL'

    @pytest.fixture
    def requests(self, requests):
        # Make get() return a list of three responses one after another.
        # The first two responses include 'next' URLs.
        requests.Session.return_value.get.side_effect = [
            mock.MagicMock(
                json=mock.MagicMock(return_value=[
                    {'id': 1, 'display_name': 'File One.pdf'},
                    {'id': 2, 'display_name': 'File Two.pdf'},
                    {'id': 3, 'display_name': 'File Three.pdf'},
                ]),
                links={'next': {'url': 'SECOND_PAGE'}},
            ),
            mock.MagicMock(
                json=mock.MagicMock(return_value=[
                    {'id': 4, 'display_name': 'File Four.pdf'},
                    {'id': 5, 'display_name': 'File Five.pdf'},
                    {'id': 6, 'display_name': 'File Six.pdf'},
                ]),
                links={'next': {'url': 'THIRD_PAGE'}},
            ),
            mock.MagicMock(
                json=mock.MagicMock(return_value=[
                    {'id': 7, 'display_name': 'File Seven.pdf'},
                    {'id': 8, 'display_name': 'File Eight.pdf'},
                ]),
                links={},
            ),
        ]

        return requests


@pytest.fixture
def pyramid_resource_selection_request(pyramid_request):
    pyramid_request.query_string = ''

    # Add the params that Canvas POSTs to us in the body of its launch request.
    pyramid_request.POST.update({
        constants.CUSTOM_CANVAS_COURSE_ID: 'TEST_COURSE_ID',
        constants.CUSTOM_CANVAS_USER_ID: 'TEST_CANVAS_USER_ID',
        constants.EXT_CONTENT_RETURN_URL: 'TEST_EXT_CONTENT_RETURN_URL',
        constants.EXT_CONTENT_RETURN_TYPES: 'TEST_EXT_CONTENT_RETURN_TYPES',
        constants.LIS_OUTCOME_SERVICE_URL: 'TEST_LIS_OUTCOME_SERVICE_URL',
        constants.LIS_RESULT_SOURCEDID: 'TEST_LIS_RESULT_SOURCEDID',
        constants.LTI_LAUNCH_URL: 'TEST_LTI_LAUNCH_URL',
        constants.OAUTH_CONSUMER_KEY: 'TEST_OAUTH_CONSUMER_KEY',
    })

    return pyramid_request

@pytest.fixture
def pyramid_request(pyramid_request):
    # These params need to actually be in the query string because our code
    # actually parses request.query_string to get them.
    #
    # FIXME: It looks like these params _also_ appear in the request body, so
    # our code should just get them from the request body like the others.
    pyramid_request.query_string = urllib.urlencode({
        constants.ASSIGNMENT_VALUE: 'TEST_ASSIGNMENT_URL',
        constants.ASSIGNMENT_NAME: 'TEST_ASSIGNMENT_NAME',
        constants.ASSIGNMENT_TYPE: 'TEST_ASSIGNMENT_TYPE',
    })

    # Add the params that Canvas POSTs to us in the body of its launch request.
    pyramid_request.POST.update({
        constants.CUSTOM_CANVAS_ASSIGNMENT_ID: 'TEST_ASSIGNMENT_ID',
        constants.CUSTOM_CANVAS_COURSE_ID: 'TEST_COURSE_ID',
        constants.CUSTOM_CANVAS_USER_ID: 'TEST_CANVAS_USER_ID',
        constants.EXT_CONTENT_RETURN_TYPES: 'TEST_EXT_CONTENT_RETURN_TYPES',
        constants.EXT_CONTENT_RETURN_URL: 'TEST_EXT_CONTENT_RETURN_URL',
        constants.LIS_OUTCOME_SERVICE_URL: 'TEST_LIS_OUTCOME_SERVICE_URL',
        constants.LIS_RESULT_SOURCEDID: 'TEST_LIS_RESULT_SOURCEDID',
        constants.OAUTH_CONSUMER_KEY: 'TEST_OAUTH_CONSUMER_KEY',
    })

    return pyramid_request


@pytest.fixture
def files_api_call(patch):
    return patch('lti.views.setup.files_api_call')

@pytest.fixture
def token_init(patch):
    return patch('lti.views.setup.token_init')


@pytest.fixture
def pack_state(patch):
    return patch('lti.views.setup.util.pack_state')


@pytest.fixture
def simple_response(patch):
    return patch('lti.views.setup.util.simple_response')


@pytest.fixture
def requests(patch):
    return patch('lti.views.setup.requests')


@pytest.fixture
def render(patch):
    return patch('lti.views.setup.render')


@pytest.fixture
def oauth(patch):
    return patch('lti.views.setup.oauth')


@pytest.fixture
def pdf(patch):
    return patch('lti.views.setup.pdf')


@pytest.fixture
def web(patch):
    return patch('lti.views.setup.web')


