# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
import urlparse
import traceback

import requests
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound

from lti import constants
from lti import util

log = logging.getLogger(__name__)


def token_init(request, state=None):
    """ We don't have a Canvas API token yet. Ask Canvas for an authorization code to begin the token-getting OAuth flow """
    auth_data_svc = request.find_service(name='auth_data')
    try:
        unpacked_state = util.unpack_state(state)
        log.info( 'token_init: state: %s' % unpacked_state )
        oauth_consumer_key = unpacked_state[constants.OAUTH_CONSUMER_KEY]
        canvas_server = auth_data_svc.get_canvas_server(oauth_consumer_key)
        token_redirect_uri = '%s/login/oauth2/auth?client_id=%s&response_type=code&redirect_uri=%s/oauth_callback&state=%s' % (canvas_server, oauth_consumer_key, request.registry.settings['lti_server'], state)
        ret = HTTPFound(location=token_redirect_uri)
        log.info( 'token_init: redirecting to %s' % token_redirect_uri )
        return ret
    except:
        response = traceback.print_exc()
        log.error(response)
        return util.simple_response(response)


def make_authorization_request(request, state, refresh=False):
    """
    Send an OAuth 2.0 authorization request.

    Send an OAuth 2.0 authorization request by redirecting the browser to
    Canvas's OAuth 2.0 authorization URL, where Canvas will ask the user to
    authorize our app.

    This function gets called during an LTI launch if we don't have a Canvas
    API access token for the given client ID yet.

    """
    auth_data_svc = request.find_service(name='auth_data')
    try:
        unpacked_state = util.unpack_state(state)
        log.info('make_authorization_request: state: %s', unpacked_state)
        oauth_consumer_key = unpacked_state[constants.OAUTH_CONSUMER_KEY]
        canvas_server = auth_data_svc.get_canvas_server(oauth_consumer_key)

        redirect_uri = '%s/oauth_callback'

        redirect_uri = redirect_uri % request.registry.settings['lti_server']

        token_redirect_uri = '%s/login/oauth2/auth?client_id=%s&response_type=code&redirect_uri=%s&state=%s' % (
            canvas_server,
            oauth_consumer_key,
            redirect_uri,
            state
        )
        ret = HTTPFound(location=token_redirect_uri)
        log.info('make_authorization_request ' + token_redirect_uri)
        return ret
    except Exception as err:  # pylint:disable=broad-except
        log.exception("make_authorization_request() failed:")
        return util.simple_response(err)


@view_config( route_name='oauth_callback' )
def oauth_callback(request):
    """ Canvas called back with an authorization code. Use it to get or refresh an API token """
    try:
        auth_data_svc = request.find_service(name='auth_data')
        q = urlparse.parse_qs(request.query_string)
        code = q['code'][0]
        state = q['state'][0]
        unpacked_state = util.unpack_state(state)
        log.info ( 'oauth_callback: %s' % state)

        course = unpacked_state[constants.CUSTOM_CANVAS_COURSE_ID]
        user = unpacked_state[constants.CUSTOM_CANVAS_USER_ID]
        oauth_consumer_key = unpacked_state[constants.OAUTH_CONSUMER_KEY]
        ext_content_return_url = unpacked_state[constants.EXT_CONTENT_RETURN_URL]
        lis_outcome_service_url = unpacked_state[constants.LIS_OUTCOME_SERVICE_URL]
        lis_result_sourcedid = unpacked_state[constants.LIS_RESULT_SOURCEDID]

        assignment_type = unpacked_state[constants.ASSIGNMENT_TYPE]
        assignment_name = unpacked_state[constants.ASSIGNMENT_NAME]
        assignment_value = unpacked_state[constants.ASSIGNMENT_VALUE]

        canvas_client_secret = auth_data_svc.get_lti_secret(oauth_consumer_key)
        canvas_server = auth_data_svc.get_canvas_server(oauth_consumer_key)
        url = '%s/login/oauth2/token' % canvas_server
        params = {
                 'grant_type': 'authorization_code',
                 'code' : code,
                 'client_id': oauth_consumer_key,
                 'client_secret': canvas_client_secret,
                 'redirect_uri': '%s/oauth_callback' % request.registry.settings['lti_server']
                 }
        log.info('oauth_callback posting %s %s' % ( url, params) )
        r = requests.post(url, params)
        dict = r.json()
        lti_token = dict['access_token']
        log.info( 'oauth_callback: got token %s' % lti_token )
        if dict.has_key('refresh_token'): # does it ever not?
            lti_refresh_token = dict['refresh_token']
        auth_data_svc.set_tokens(user, oauth_consumer_key, lti_token, lti_refresh_token)
        redirect = request.route_url('lti_setup') + '?%s=%s&%s=%s&%s=%s&%s=%s&%s=%s&%s=%s&%s=%s' % (
            constants.CUSTOM_CANVAS_COURSE_ID, course,
            constants.CUSTOM_CANVAS_USER_ID, user,
            constants.OAUTH_CONSUMER_KEY, oauth_consumer_key,
            constants.EXT_CONTENT_RETURN_URL, ext_content_return_url,
            constants.ASSIGNMENT_TYPE, assignment_type,
            constants.ASSIGNMENT_NAME, assignment_name,
            constants.ASSIGNMENT_VALUE, assignment_value
            )
        log.info('oauth_callback redirecting to %s' % redirect)
        return HTTPFound(location=redirect)
    except Exception as err:  # pylint: disable=broad-except
        log.exception("oauth_callback() failed:")
        return util.simple_response(err)

def refresh_init(request, state=None):
    """ Our Canvas API token expired. Ask Canvas for an authorization code to begin the token-refreshing OAuth flow """
    auth_data_svc = request.find_service(name='auth_data')
    try:
        unpacked_state = util.unpack_state(state)
        log.info( 'refresh_init: state: %s' % unpacked_state )

        oauth_consumer_key = unpacked_state[constants.OAUTH_CONSUMER_KEY]
        canvas_server = auth_data_svc.get_canvas_server(oauth_consumer_key)

        course = unpacked_state[constants.CUSTOM_CANVAS_COURSE_ID]
        user = unpacked_state[constants.CUSTOM_CANVAS_USER_ID]
        oauth_consumer_key = unpacked_state[constants.OAUTH_CONSUMER_KEY]
        ext_content_return_url = unpacked_state[constants.EXT_CONTENT_RETURN_URL]
        lis_outcome_service_url = unpacked_state[constants.LIS_OUTCOME_SERVICE_URL]
        lis_result_sourcedid = unpacked_state[constants.LIS_RESULT_SOURCEDID]

        assignment_type = unpacked_state[constants.ASSIGNMENT_TYPE]
        assignment_name = unpacked_state[constants.ASSIGNMENT_NAME]
        assignment_value = unpacked_state[constants.ASSIGNMENT_VALUE]

        canvas_client_secret = auth_data_svc.get_lti_secret(oauth_consumer_key)
        lti_refresh_token = auth_data_svc.get_lti_refresh_token(user, oauth_consumer_key)
        canvas_server = auth_data_svc.get_canvas_server(oauth_consumer_key)
        url = '%s/login/oauth2/token' % canvas_server

        params = {
                'grant_type': 'refresh_token',
                'client_id': oauth_consumer_key,
                'client_secret': canvas_client_secret,
                'refresh_token' : lti_refresh_token
                }
        log.info('refresh_init posting %s %s' % ( url, params) )
        r = requests.post(url, params)
        dict = r.json()
        lti_token = dict['access_token']
        log.info( 'refresh_init: got token %s' % lti_token )

        auth_data_svc.set_tokens(user, oauth_consumer_key, lti_token, lti_refresh_token)

        url = 'https://h.jonudell.info/lti_setup?assignment_type=pdf&assignment_name=mueller_01.pdf&assignment_value=106&%s=%s&%s=%s&%s=%s' % (
            constants.CUSTOM_CANVAS_USER_ID, user,
            constants.OAUTH_CONSUMER_KEY, oauth_consumer_key,
            constants.CUSTOM_CANVAS_COURSE_ID, course,
            )
        log.info ('refresh_init redirecting to %s' % url)
        return HTTPFound(location=url)

    except:
        response = traceback.print_exc()
        log.error(response)
        return util.simple_response(response)

