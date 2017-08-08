# -*- coding: utf-8 -*-

"""Functions for caching files."""

from __future__ import unicode_literals

import os.path

from lti import constants


def exists_html(hash_):
    """Return True if an HTML file with the given hash is already cached."""
    return os.path.isfile('%s/%s.html' % (constants.FILES_PATH, hash_))
