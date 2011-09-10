#coding:utf8

'''
Why WSGI from scratch?

I wanted to start fast. But suddenly I realized there is nothing Py3k 
compatible I would like to use. Not even WebOb :(
'''

from cgi import FieldStorage
import datetime
import functools
import io
import os.path
import re
import socket
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

def get_input(environ):
    return io.TextIOWrapper(io.BufferedReader(io.FileIO(environ['wsgi.input'].fileno(), 'r', False)), encoding='utf8')

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
        def wrapper(environ, **kwargs):
            f(environ, **kwargs)
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
            iterator = result(environ, **args)
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
def page_main(environ):
    pass

@expose('subpage.pha')
def page_subpage(environ):
    c.time = datetime.datetime.now().isoformat()

@expose('exec_shit.pha')
def page_exec_shit(environ):
    if environ['REQUEST_METHOD'] == 'POST':
        fields = FieldStorage(
            fp = environ['wsgi.input'],
            environ = environ,
        )
        code = fields.getfirst('code')
        if code:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(8.0)
            sock.connect('/home/fluxid/main/dev/sandboxed/socket')
            code = code.replace('\r\n', '\n')
            sock.sendall(code.encode('utf8') + b'\0')

            c.code = code
            print('===')
            print(code)
            print('===')

            def _gen_receive():
                try:
                    continue_recv = True
                    while continue_recv:
                        try:
                            data = sock.recv(4096)
                        except socket.timeout:
                            yield '\n\nExecution timed out'
                            return
                        if not data:
                            return
                        zeropos = data.find(b'\0')
                        if zeropos > -1:
                            data = data[:zeropos]
                            continue_recv = False
                        if not data:
                            return
                        # Let's say it won't stop in the middle
                        # octet stream ;)
                        yield data.decode('utf8', 'ignore')
                finally:
                    sock.close()

            c.result = _gen_receive()

application = TestApplication(
    RegexRouting((
        ('/?$', page_main),
        ('subpage/?$', page_subpage),
        ('exec_shit/?$', page_exec_shit),
    )),
)

