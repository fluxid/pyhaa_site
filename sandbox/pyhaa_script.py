#coding:utf8

import logging
import os
import sys

logging.getLogger().setLevel(logging.ERROR)

from pyhaa import (
    PyhaaEnvironment,
    html_render_to_iterator,
)
from pyhaa.runtime.proxy import InstanceProxy

env = PyhaaEnvironment()
structure = env.parse_io(sys.stdin)
code = env.codegen_structure(structure)
bytecode = compile(code, '<string>', 'exec')
template_info = env.template_info_from_bytecode(bytecode)
template = InstanceProxy([template_info], env)
iterator = html_render_to_iterator(template)

fileno = sys.stdout.fileno()
for value in iterator:
    os.write(fileno, value)

