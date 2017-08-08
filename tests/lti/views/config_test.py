# -*- coding: utf-8 -*-

import pytest
import urllib

import lti.views.config

def test_it_returns_config_xml_object(pyramid_request):
    actual = lti.views.config.config_xml(pyramid_request)
    assert actual['launch_url'] == 'http://example.com/lti_setup'
    assert actual['resource_selection_url'] == 'http://example.com/lti_setup'

@pytest.fixture
def pyramid_request(pyramid_request):
    # When it calls the token_callback or refresh_callback routes,
    # Canvas calls them with an OAuth authorization code and state in the
    # query params.
    pyramid_request.query_string = urllib.urlencode({
        'code': 'TEST_OAUTH_AUTHORIZATION_CODE',
        'state': 'TEST_OAUTH_STATE',
    })
    return pyramid_request
