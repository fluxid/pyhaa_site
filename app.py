#coding:utf8

'''
Why WSGI from scratch?

I wanted to start fast. But suddenly I realized there is nothing Py3k 
compatible I would like to use. Not even WebOb :(
'''

import datetime
import functools
import os.path
import re
import sys
import threading

from pyhaa import PyhaaEnvironment, html_render_to_iterator
from pyhaa.runtime.cache import FilesystemBytecodeCache
from pyhaa.runtime.loaders import FilesystemLoader


class TemplateContext:
    def __init__(self):
        super(TemplateContext, self).__setattr__('_context_storage', threading.local())

    def _context_dict(self):
        dict_ = getattr(self._context_storage, 'template_dict', None)
        if dict_ is None:
            dict_ = self._context_storage.template_dict = dict()
        return dict_

    def _context_reset(self):
        self._context_dict().clear()

    def __getattr__(self, name):
        return self._context_dict().get(name, '')

    def __setattr__(self, name, value):
        self._context_dict()[name] = value

    def __delattr__(self, name):
        return self._context_dict().pop(name, None)

# Routing stuff ported from my old'n'stupid fpyf

class RegexRouting:
    def __init__(self, route):
        path = [route]
        rpath = []

        def _make_route(r):
            output = []
            for regex, target in r:
                rpath.append(regex)
                regex = re.compile(regex)
                if isinstance(target, (list, tuple)):
                    if target in path:
                        raise Exception('Loop found in route! Path: {}'.format(rpath))
                    path.append(target)
                    target = _make_route(target)
                    path.pop()
                elif not hasattr(target, '__call__'):
                    raise Exception('Unsupported target type! Path: {}'.format(rpath))
                rpath.pop()
                output.append((regex, target))
            return output

        self.routing = _make_route(route)

    def resolve(self, path):
        a = self.routing
        start = 0
        args = {}
        while True:
            found = None
            for regex, target in a:
                g = regex.match(path, start)
                if g:
                    args.update(g.groupdict())
                    start = g.end()
                    if hasattr(target, '__call__'):
                        return target, args
                    else:
                        found = target
                        break
            if found:
                a = found
            else:
                return None

# Setting stuff up...

HERE = os.path.dirname(os.path.realpath(sys.argv[0]))

c = TemplateContext()
environment = PyhaaEnvironment(
    loader = FilesystemLoader(
        paths = os.path.join(HERE, 'template_root'),
        bytecode_cache = FilesystemBytecodeCache(
            storage_directory = os.path.join(HERE, 'template_cache'),
        ),
    ),
    template_globals = dict(c=c),
)

# Decorator stuff...

def expose(template_path):
    def decorator(f):
        def wrapper(**kwargs):
            f(**kwargs)
            template = environment.get_template(template_path)
            return html_render_to_iterator(template)
        return functools.update_wrapper(wrapper, f)
    return decorator

class TestApplication:
    def __init__(self, routing):
        self.routing = routing

    def __call__(self, environ, start_response):
        c._context_reset()
        path = environ['PATH_INFO']
        if path.startswith('/'):
            path = path[1:]
        result = self.routing.resolve(path)
        if result:
            result, args = result
            iterator = result(**args)
            start_response('200 OK', [
                ('Content-type', 'text/html; charset=utf8'),
            ])
            return iterator

        start_response('404 Not Found', [
            ('Content-type', 'text/html; charset=utf8'),
        ])
        return 'Not found :('

# Pages!

@expose('main.pha')
def page_main():
    pass

@expose('subpage.pha')
def page_subpage():
    c.time = datetime.datetime.now().isoformat()

application = TestApplication(
    RegexRouting((
        ('/?$', page_main),
        ('subpage/?$', page_subpage),
    )),
)

