# -*- coding: utf-8 -*-
"""
The lti_setup view.

But note that this view should be split into multiple separate views and I don't
think there will be a ``setup`` module in the long-term.

"""
from __future__ import unicode_literals

import traceback
import logging

from sqlalchemy.orm.exc import NoResultFound

import requests
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.renderers import render

from lti import util
from lti import constants
from lti.views import oauth
from lti.views import web
from lti.views import pdf

log = logging.getLogger(__name__)


# pylint:disable=too-many-locals, too-many-return-statements
@view_config(route_name='lti_setup')
@view_config(route_name='canvas_resource_selection')
def lti_setup(request):
    """
    LTI-launched from a Canvas assignment's Find interaction to present choice of doc (PDF or URL) to annotate.

    LTI-launched again when the Canvas assignment opens.

    In those two cases we have LTI params in the HTTP POST -- if we have a Canvas API token.

    If there is no token, or the token is expired, called instead by way of OAuth redirect.
    In that case we expect params in the query string.
    """
    auth_data_svc = request.find_service(name='auth_data')

    post_data = util.requests.capture_post_data(request)

    print ("setup: %s" % post_data)

    oauth_consumer_key = util.requests.get_post_or_query_param(request, constants.OAUTH_CONSUMER_KEY)

    try:
        print 'getting canvas server for %s' % oauth_consumer_key
        canvas_server = auth_data_svc.get_canvas_server(oauth_consumer_key)
        print 'got canvas server for %s: %s' % (oauth_consumer_key, canvas_server)
    except KeyError:
        print 'no canvas server for %s' % oauth_consumer_key
        return util.simple_response("We don't have the Consumer Key %s in our "
                                    "database yet." % oauth_consumer_key)

    lis_outcome_service_url = util.requests.get_post_or_query_param(request, constants.LIS_OUTCOME_SERVICE_URL)
    lis_result_sourcedid = util.requests.get_post_or_query_param(request, constants.LIS_RESULT_SOURCEDID)

    course = util.requests.get_post_or_query_param(request, constants.CUSTOM_CANVAS_COURSE_ID)
    if course is None:
        return util.simple_response('No course number. Was Privacy set to '
                                    'Public for this installation of the '
                                    'Hypothesis LTI app? If not please do so '
                                    '(or ask someone who can to do so).')

    post_data[constants.ASSIGNMENT_TYPE] = util.requests.get_post_or_query_param(request, constants.ASSIGNMENT_TYPE)
    post_data[constants.ASSIGNMENT_NAME] = util.requests.get_post_or_query_param(request, constants.ASSIGNMENT_NAME)
    post_data[constants.ASSIGNMENT_VALUE] = util.requests.get_post_or_query_param(request, constants.ASSIGNMENT_VALUE)

    user_id = util.requests.get_post_or_query_param(request, constants.CUSTOM_CANVAS_USER_ID)
    print ('setup: user_id: %s' % user_id)

    try:
        print ('setup: try getting lti_token')
        lti_token = auth_data_svc.get_lti_token(user_id, oauth_consumer_key)
    except KeyError:
        print ('setup: got no token, begin oauth flow')
        return oauth.token_init(request, util.pack_state(post_data))

    if lti_token is None:
        print ('setup: token is none, begin oauth')
        return oauth.token_init(request, util.pack_state(post_data))

    initial_api_response = files_api_call(auth_data_svc, oauth_consumer_key, course, lti_token)
    print 'initial_api_response %s' % initial_api_response

    if initial_api_response.status_code == 401:
      print('setup: received 401 while fetching files, trying token refresh')
      return oauth.refresh_init(request, util.pack_state(post_data))

    print('setup: proceeding with valid api token') 

    print type(initial_api_response)
    response = initial_api_response
    files = response.json()
    while 'next' in response.links:
        url = response.links['next']['url']
        response = sess.get(url=url, headers={'Authorization': 'Bearer %s' % lti_token})
        files = files + response.json()

    print 'files %s' % files

    assignment_type = post_data[constants.ASSIGNMENT_TYPE]
    assignment_name = post_data[constants.ASSIGNMENT_NAME]
    assignment_value = post_data[constants.ASSIGNMENT_VALUE]

    print 'assignment_type: %s' % assignment_type

    if assignment_type == 'pdf':
        print('setup: calling lti_pdf')
        return pdf.lti_pdf(request,
                           user_id,
                           oauth_consumer_key=oauth_consumer_key,
                           lis_outcome_service_url=lis_outcome_service_url,
                           lis_result_sourcedid=lis_result_sourcedid,
                           course=course,
                           name=assignment_name,
                           value=assignment_value)

    if assignment_type == 'web':
        print('setup: calling lti_web_response user, user %s, key %s' % (user_id, oauth_consumer_key ) )
        return web.web_response(request,
                                user_id=user_id,
                                oauth_consumer_key=oauth_consumer_key,
                                lis_outcome_service_url=lis_outcome_service_url,
                                lis_result_sourcedid=lis_result_sourcedid,
                                name=assignment_name,
                                url=assignment_value)

    print('setup: neither pdf nor web, do resource selection')

    return_url = util.requests.get_post_or_query_param(request, constants.EXT_CONTENT_RETURN_URL)
    if return_url is None:  # this is an oauth redirect so get what we sent ourselves
        return_url = util.requests.get_post_or_query_param(request, 'return_url')

    launch_url_template = ('%s/lti_setup?assignment_type=__TYPE__'
                           '&assignment_name=__NAME__'
                           '&assignment_value=__VALUE__'
                           '&return_url=__RETURN_URL__' % request.registry.settings['lti_server'])

    pdf_choices = ''
    if files:
        pdf_choices += '<ul>'
        for pdf_file in files:
            file_id = str(pdf_file['id'])
            name = pdf_file['display_name']
            if not name.lower().endswith('.pdf'):
                continue
            pdf_choices += '<li><input type="radio" name="pdf_choice" onclick="javascript:go()" value="%s" id="%s">%s</li>' % (name, file_id, name)
        pdf_choices += '</ul>'

    print('setup: returning chooser')

    chooser = render('lti:templates/document_chooser.html.jinja2', dict(
        return_url=return_url,
        launch_url=launch_url_template,
        pdf_choices=pdf_choices,
    ))

    return Response(chooser)

def files_api_call(auth_data_svc, oauth_consumer_key, course, lti_token):
    print 'calling files_api_call'
    sess = requests.Session()  # ensure token is unexpired
    canvas_server = auth_data_svc.get_canvas_server(oauth_consumer_key)
    url = '%s/api/v1/courses/%s/files?per_page=100' % (canvas_server, course)
    response = sess.get(url=url, headers={'Authorization': 'Bearer %s' % lti_token})

    return response
