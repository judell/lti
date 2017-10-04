# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json

from pyramid.view import view_config

import logging

from lti import util
from lti.models import OAuth2UnvalidatedCredentials

log = logging.getLogger(__name__)


@view_config(route_name='lti_credentials',
             renderer='lti:templates/lti_credentials_form.html.jinja2')
def lti_credentials(request):
    """
    Recieve credentials and save to database.

    Render the empty credentials form. When the form is submitted, save the unvalidated
    client id, client secret, authorization server and email address to the oauth2_unvalidated_credentials
    table and render the form and a thank you message confirming the submitted credentials.

    """
    credentials = util.requests.get_query_param(request, 'credentials')
    if credentials is None:
        return {
            'form_submitted': False
        }

    credentials = json.loads(credentials)

    email = credentials.get('email')
    host = credentials.get('host')

    request.db.add(OAuth2UnvalidatedCredentials(
        client_id=credentials.get("key"),
        client_secret=credentials.get("secret"),
        authorization_server=host,
        email_address=email
    ))

    message = ( 'new lti credentials from %s for %s' % (email, host) )

    log.info(message)

    slack_hook = request.registry.settings['slack_hook']

    util.notify.notify_slack(slack_hook, message)

    return {
        'form_submitted': True,
        'key': credentials.get("key"),
        'secret': credentials.get("secret"),
        'host': credentials.get("host"),
        'email': credentials.get("email"),
    }
