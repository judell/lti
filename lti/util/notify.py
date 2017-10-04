# -*- coding: utf-8 -*-
"""Utility functions for notification."""

import httplib # because requests is a local module in this app
import json
import urllib2


def notify_slack(hook, text):
    message = {
        'username'   : 'notifier',
        'channel'    : '#notifications',
        'icon_emoji' : ':mailbox:',
        'text'       : text
    }

    url = 'https://hooks.slack.com/services/%s' % hook
  
    req = urllib2.Request(url,
        headers = {
            "Content-Type": "application/json",
            }, 
        data = json.dumps(message)
        )
  
    urllib2.urlopen(req)



