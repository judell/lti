# -*- coding: utf-8 -*-

from pyramid.view import view_config

from pyramid.response import FileResponse


@view_config(route_name='about')
def about(request):
    path = '.'
    file_name = 'about.html'
    content_type = 'text/html'

    return FileResponse('%s/%s' % (path, file_name),
                        request=request,
                        content_type=content_type)
