# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import urllib
import json
import logging

import requests
from pyramid.renderers import render
from pyramid.response import Response

from lti import util
from lti.views import oauth


log = logging.getLogger(__name__)


# pylint: disable = too-many-arguments, too-many-locals
def lti_pdf(request, user_id, oauth_consumer_key, lis_outcome_service_url,
            lis_result_sourcedid, course, name, value):
    """
    Return a PDF annotation assignment (HTML response).

    Download the PDF file to be annotated from Canvas's API and save it to a
    cache directory on disk, if the file hasn't been cached already.

    This requires an access token for the Canvas API. If we don't have one then
    kick off an authorization code flow to get one, redirecting the browser to
    Canvas's auth endpoint. We'll end up rendering the annotation assignment
    later, after Canvas directs the browser back to us with an authorization.

    """
    post_data = util.requests.capture_post_data(request)
    file_id = value
    auth_data_svc = request.find_service(name='auth_data')
    try:
        lti_token = auth_data_svc.get_lti_token(user_id, oauth_consumer_key)
    except KeyError:
        log.error ( 'no token for user %s, client_id %s' % (user_id, oauth_consumer_key) )
        return util.simple_response("Authorization error")
    canvas_server = auth_data_svc.get_canvas_server(oauth_consumer_key)
    url = '%s/api/v1/courses/%s/files/%s' % (canvas_server, course, file_id)

    sess = requests.Session()
    response = sess.get(url=url, headers={'Authorization': 'Bearer %s' % lti_token})
    if response.status_code == 401:
        return oauth.make_authorization_request(
            request, 'pdf:' + urllib.quote(json.dumps(post_data)),
            refresh=True)
    if response.status_code == 200:
        j = response.json()
        url = j['url']

    log.info('lti_pdf: url %s' % url)

    return Response(
        render('lti:templates/pdf_assignment.html.jinja2', dict(
               name=name,
               pdf_url=url,
               oauth_consumer_key=oauth_consumer_key,
               lis_outcome_service_url=lis_outcome_service_url,
               lis_result_sourcedid=lis_result_sourcedid,
               lti_server=request.registry.settings['lti_server'],
               client_origin=request.registry.settings['client_origin'],
               via_url=request.registry.settings['via_url'],
               )).encode('utf-8'),
        content_type='text/html',
    )
