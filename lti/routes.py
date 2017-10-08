# -*- coding: utf-8 -*-

from __future__ import unicode_literals


def includeme(config):
    config.add_route('about', '/')

    config.add_route('oauth_callback', '/oauth_callback')

    config.add_route('config_xml', '/config.xml')

    config.add_route('lti_credentials', '/lti_credentials')
    config.add_route('lti_setup', '/lti_setup')
    config.add_route('canvas_resource_selection', '/canvas/resource_selection')
    config.add_route('lti_submit', '/lti_submit')
    config.add_route('lti_export', '/lti_export')

    # Health check
    config.add_route('status', '/_status')
