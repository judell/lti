﻿import json
import urllib
import urlparse
import requests
import traceback
import os
import re
import md5
import logging
import filelock
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from pyramid.response import FileResponse
from requests_oauthlib import OAuth1

from pyramid.renderers import render

from lti.config import configure
from lti import util
from lti import constants
from lti.views import oauth
from lti.views import web


log = logging.getLogger(__name__)


def bare_response(text):
    r = Response(text.encode('utf-8'))
    r.headers.update({
        'Access-Control-Allow-Origin': '*'
        })
    r.content_type = 'text/plain'
    return r

def page_response(html):
    r = Response(html.encode('utf-8'))
    r.headers.update({
        'Access-Control-Allow-Origin': '*'
        })
    r.content_type = 'text/html'
    return r

def serve_file(path=None, file=None, request=None, content_type=None):
    response = FileResponse('%s/%s' % (path, file),
                            request=request,
                            content_type=content_type)
    return response


@view_config( route_name='lti_setup' )
def lti_setup(request):
    """
    LTI-launched from a Canvas assignment's Find interaction to present choice of doc (PDF or URL) to annotate.
  
    LTI-launched again when the Canvas assignment opens.
  
    In those two cases we have LTI params in the HTTP POST -- if we have a Canvas API token.

    If there is no token, or the token is expired, called instead by way of OAuth redirect. 
    In that case we expect params in the query string.
    """
    log.info ( 'lti_setup: query: %s' % request.query_string )
    log.info ( 'lti_setup: post: %s' % request.POST )
    post_data = util.requests.capture_post_data(request)

    oauth_consumer_key = util.requests.get_post_or_query_param(request, constants.OAUTH_CONSUMER_KEY)
    if oauth_consumer_key is None:
        log.error( 'oauth_consumer_key cannot be None %s' % request.POST )
    oauth_consumer_key = oauth_consumer_key.strip()
    lis_outcome_service_url = util.requests.get_post_or_query_param(request, constants.LIS_OUTCOME_SERVICE_URL)
    lis_result_sourcedid = util.requests.get_post_or_query_param(request, constants.LIS_RESULT_SOURCEDID)

    course = util.requests.get_post_or_query_param(request, constants.CUSTOM_CANVAS_COURSE_ID)
    if course is None:
        log.error ( 'course cannot be None' )
        return util.simple_response('No course number. Was Privacy set to Public for this installation of the Hypothesis LTI app? If not please do so (or ask someone who can to do so).')
    
    post_data[constants.ASSIGNMENT_TYPE] = util.requests.get_post_or_query_param(request, constants.ASSIGNMENT_TYPE)
    post_data[constants.ASSIGNMENT_NAME] = util.requests.get_post_or_query_param(request, constants.ASSIGNMENT_NAME)
    post_data[constants.ASSIGNMENT_VALUE] = util.requests.get_post_or_query_param(request, constants.ASSIGNMENT_VALUE)

    log.info ( 'lti_setup: post_data: %s' % post_data )

    try:
        lti_token = request.auth_data.get_lti_token(oauth_consumer_key)
    except:
        response = "We don't have the Consumer Key %s in our database yet." % oauth_consumer_key
        log.error ( response )
        log.error ( traceback.print_exc() )
        return util.simple_response(response)

    if lti_token is None:
        log.info ( 'lti_setup: getting token' )
        return oauth.make_authorization_request(request, util.pack_state(post_data))

    sess = requests.Session()  # ensure we have a token before calling lti_pdf or lti_web
    canvas_server = request.auth_data.get_canvas_server(oauth_consumer_key)
    log.info ( 'canvas_server: %s' % canvas_server )
    url = '%s/api/v1/courses/%s/files?per_page=100' % (canvas_server, course)
    r = sess.get(url=url, headers={'Authorization':'Bearer %s' % lti_token })
    if r.status_code == 401:
      log.info ( 'lti_setup: refreshing token' )
      return oauth.make_authorization_request(
            request, util.pack_state(post_data), refresh=True)
    files = r.json()
    while ('next' in r.links):
        url = r.links['next']['url']
        r = sess.get(url=url, headers={'Authorization':'Bearer %s' % lti_token })
        files = files + r.json()
    log.info ('files: %s' % len(files))

    #return HTTPFound(location='http://h.jonudell.info:3000/courses/2/external_content/success/external_tool_dialog?return_type=lti_launch_url&url=http%3A%2F%2F98.234.245.185%3A8000%2Flti_setup%3FCUSTOM_CANVAS_COURSE_ID%3D2%26type%3Dpdf%26name%3Dfilename%26value%3D9')
    
    assignment_type = post_data[constants.ASSIGNMENT_TYPE]
    assignment_name = post_data[constants.ASSIGNMENT_NAME]
    assignment_value = post_data[constants.ASSIGNMENT_VALUE]

    if assignment_type == 'pdf':
        return lti_pdf(request, oauth_consumer_key=oauth_consumer_key, lis_outcome_service_url=lis_outcome_service_url, lis_result_sourcedid=lis_result_sourcedid, course=course, name=assignment_name, value=assignment_value)

    if assignment_type == 'web':
        return web.web_response(request.registry.settings,
                                request.auth_data,
                                oauth_consumer_key=oauth_consumer_key,
                                course=course,
                                lis_outcome_service_url=lis_outcome_service_url,
                                lis_result_sourcedid=lis_result_sourcedid,
                                name=assignment_name,
                                value=assignment_value)

    return_url = util.requests.get_post_or_query_param(request, constants.EXT_CONTENT_RETURN_URL)
    if return_url is None: # this is an oauth redirect so get what we sent ourselves
        return_url = util.requests.get_post_or_query_param(request, 'return_url')

    log.info ( 'return_url: %s' % return_url )

    launch_url_template = '%s/lti_setup?assignment_type=__TYPE__&assignment_name=__NAME__&assignment_value=__VALUE__&return_url=__RETURN_URL__' % request.registry.settings['lti_server']

    log.info ( 'key %s, course %s, token %s' % (oauth_consumer_key, course, lti_token) )

    pdf_choices = ''
    if len(files) > 0:
        pdf_choices += '<ul>'
        for file in files:
            id = str(file['id'])
            name = file['display_name']
            if not name.lower().endswith('.pdf'):
                continue
            pdf_choices += '<li><input type="radio" name="pdf_choice" onclick="javascript:go()" value="%s" id="%s">%s</li>' % (name, id, name) 
        pdf_choices += '</ul>'
   
    return Response(render('lti:templates/document_chooser.html.jinja2', dict(
        return_url=return_url,
        launch_url=launch_url_template,
        pdf_choices=pdf_choices,
    )))

def exists_pdf(hash):
    return os.path.isfile('%s/%s.pdf' % (constants.FILES_PATH, hash))

def lti_pdf(request, oauth_consumer_key=None, lis_outcome_service_url=None, lis_result_sourcedid=None, course=None, name=None, value=None):
    """ 
    Called from lti_setup if it was called from a pdf assignment. 

    We expect to know at least the oauth_consume_key, course number, name of the PDF, 
    and value of the PDF (its number as known to the Canvas API)

    If we are called in a student context we also expect the lis* params needed for the submission URL.

    Download the PDF to a timestamp-based name in the PDFJS subtree, and call pdf_response to 
    return a page that serves it back in an iframe.
    """
    log.info ( 'lti_pdf: query: %s' % request.query_string )
    log.info ( 'lti_pdf: post: %s' % request.POST )
    post_data = util.requests.capture_post_data(request)
    if oauth_consumer_key is None:
        oauth_consumer_key = util.requests.get_post_or_query_param(request, constants.OAUTH_CONSUMER_KEY)
    file_id = value
    try:
        lti_token = request.auth_data.get_lti_token(oauth_consumer_key)
    except:
        return util.simple_response("We don't have the Consumer Key %s in our database yet." % oauth_consumer_key)
    canvas_server = request.auth_data.get_canvas_server(oauth_consumer_key)
    url = '%s/api/v1/courses/%s/files/%s' % (canvas_server, course, file_id)
    m = md5.new()
    m.update('%s/%s/%s' % ( canvas_server, course, file_id ))
    hash = m.hexdigest()
    log.info( 'server %s, course %s, file_id %s, hash %s' % ( canvas_server, course, file_id, hash ))
    if exists_pdf(hash) is False:
        sess = requests.Session()
        r = sess.get(url=url, headers={'Authorization':'Bearer %s' % lti_token})
        if r.status_code == 401:
          log.info( 'lti_pdf: refreshing token' )
          return oauth.make_authorization_request(
                request, 'pdf:' + urllib.quote(json.dumps(post_data)),
                refresh=True)
        if r.status_code == 200:
            j = r.json()
            log.info( j )
            url = j['url']
            log.info( url )
            urllib.urlretrieve(url, hash)
            os.rename(hash, '%s/%s.pdf' % (constants.FILES_PATH, hash))
        else:
            log.error('%s retrieving %s, %s, %s' % (r.status_code, canvas_server, course, file_id))
    fingerprint = util.pdf.get_fingerprint(hash)
    if fingerprint is None:
        pdf_uri = '%s/viewer/web/%s.pdf' % ( request.registry.settings['lti_server'], hash )
    else:
        pdf_uri = 'urn:x-pdf:%s' % fingerprint

    return Response(
        render('lti:templates/pdf_assignment.html.jinja2', dict(
                name=name,
                hash=hash,
                oauth_consumer_key=oauth_consumer_key,
                lis_outcome_service_url=lis_outcome_service_url,
                lis_result_sourcedid=lis_result_sourcedid,
                doc_uri=pdf_uri,
                lti_server=request.registry.settings['lti_server'],
            ),
        ).encode('utf-8'),
        content_type='text/html',
    )

@view_config( route_name='lti_submit' )
def lti_submit(request, oauth_consumer_key=None, lis_outcome_service_url=None, lis_result_sourcedid=None, export_url=None):
    """
    Called from a student's view of an assignment.

    In theory can be an LTI launch but that's undocumented and did not seem to work. 
    So we use info we send to ourselves from the JS we generate on the assignment page.
    """
    log.info ( 'lti_submit: query: %s' % request.query_string )
    log.info ( 'lti_submit: post: %s' % request.POST )
    oauth_consumer_key = util.requests.get_post_or_query_param(request, constants.OAUTH_CONSUMER_KEY)
    lis_outcome_service_url = util.requests.get_post_or_query_param(request, constants.LIS_OUTCOME_SERVICE_URL)
    lis_result_sourcedid = util.requests.get_post_or_query_param(request, constants.LIS_RESULT_SOURCEDID)
    export_url = util.requests.get_post_or_query_param(request, constants.EXPORT_URL)

    try:
        secret = request.auth_data.get_lti_secret(oauth_consumer_key)   # because the submission must be OAuth1-signed
    except:
        return util.simple_response("We don't have the Consumer Key %s in our database yet." % oauth_consumer_key)

    oauth_client = OAuth1(client_key=oauth_consumer_key, client_secret=secret, signature_method='HMAC-SHA1', signature_type='auth_header', force_include_body=True)
    body = render('lti:templates/submission.xml.jinja2', dict(
        url=export_url,
        sourcedid=lis_result_sourcedid,
    ))
    headers = {'Content-Type': 'application/xml'}
    r = requests.post(url=lis_outcome_service_url, data=body, headers=headers, auth=oauth_client)
    log.info ( 'lti_submit: %s' % r.status_code )
    log.info ( 'lti_submit: %s' % r.text )
    response = None
    if ( r.status_code == 200 ):
        response = 'OK! Assignment successfully submitted.'
    else:
        response = 'Something is wrong. %s %s' % (r.status_code, r.text)        
    return util.simple_response(response)

@view_config( route_name='lti_export' )
def lti_export(request):
    """ 
    Called from Speed Grader, which presents the URL that the student submitted.

    Redirects to a variant of our viewer/export prototype which displays annotations for the
    assignment's PDF or URL, filtered to threads involving the (self-identified) H user, and
    highlighting contributions by that user.
    """
    args = util.requests.get_query_param(request, 'args')  # because canvas swallows & in the submitted pox, we pass an opaque construct and unpack here
    log.info ( 'lti_export: query: %s' % request.query_string )
    parsed_args = urlparse.parse_qs(args)
    user = parsed_args['user'][0]
    uri = parsed_args['uri'][0]
    log.info( 'lti_export user: %s, uri %s' % ( user, uri) )
    export_url = '%s/export/facet.html?facet=uri&mode=documents&search=%s&user=%s' % ( request.registry.settings['lti_server'], urllib.quote(uri), user )
    return HTTPFound(location=export_url)


def lti_credentials_form(settings):
    return render('lti:templates/lti_credentials_form.html.jinja2', dict(
        lti_credentials_url=settings['lti_credentials_url'],
    ))

def cors_response(request, response=None):
    if response is None:
        response = Response()
    request_headers = request.headers['Access-Control-Request-Headers'].lower()
    request_headers = re.findall('\w(?:[-\w]*\w)', request_headers)
    response_headers = ['access-control-allow-origin']
    for req_acoa_header in request_headers:
        if req_acoa_header not in response_headers:
            response_headers.append(req_acoa_header)
    response_headers = ','.join(response_headers)
    response.headers.update({
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': '%s' % response_headers,
        'Access-Control-Allow-Methods': "UPDATE, POST, GET"
        })
    response.status_int = 204
    print ( response.headers )
    return response

@view_config( route_name='lti_credentials' )
def lti_credentials(request):
    """ 
    Receive credentials for path A (key/secret/host) or path B (username.username/token/host)
    """
    if  request.method == 'OPTIONS':
        return cors_response(request)

    credentials = util.requests.get_query_param(request, 'credentials')
    if ( credentials is None ):
      return page_response(lti_credentials_form(request.registry.settings))

    lock = filelock.FileLock("credentials.lock")
    with lock.acquire(timeout = 1):
      with open('credentials.txt', 'a') as f:
        f.write(credentials + '\n')
    return bare_response("<p>Thanks!</p><p>We received:</p><p>%s</p><p>We'll contact you to explain next steps.</p>" % credentials)


@view_config( route_name='lti_serve_pdf' )
def lti_serve_pdf(request):
    if request.referer is not None and 'pdf.worker.js' in request.referer:
        return serve_file(path=constants.FILES_PATH,
                      file=request.matchdict['file'] + '.pdf',
                      request=request,
                      content_type='application/pdf')

    return util.simple_response('You are not logged in to Canvas')

from pyramid.response import Response
from pyramid.static import static_view

def create_app(global_config, **settings):  # pylint: disable=unused-argument
    config = configure(settings=settings)

    config.include('pyramid_jinja2')
    config.include('lti.routes')
    config.include('lti.models')

    pdf_view = static_view('lti:static/pdfjs')
    config.add_view(pdf_view, route_name='catchall_pdf')
    config.add_static_view(name='export', path='lti:static/export')

    config.scan()
    return config.make_wsgi_app()
