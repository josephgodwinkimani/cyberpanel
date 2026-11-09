"""Tests remove_destination in IncBackups/views.py: it deletes one destination file and nothing outside the destinations
folders, whatever name the request carries. The real function is run against temporary folders with stubs for the panel's
permission check and response classes. Run: python3 CPScripts/test_incremental_destination_removal.py"""
import ast
import enum
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'IncBackups', 'views.py')

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


src = open(SOURCE, encoding='utf-8').read()
tree = ast.parse(src)
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'remove_destination')
func_src = ast.get_source_segment(src, node)

# the same function with the new check cut out, as a control
guard = next(n for n in ast.walk(node) if isinstance(n, ast.If) and 'isinstance(file_name, str)' in ast.get_source_segment(src, n.test))
without_guard = func_src.replace(ast.get_source_segment(src, guard), 'pass')
assert without_guard != func_src

work = tempfile.mkdtemp(prefix='incdest-')
sftp = os.path.join(work, 'sftp')
aws = os.path.join(work, 'aws')
outside = os.path.join(work, 'outside.txt')


class Provider(enum.Enum):
    SFTP = 1
    AWS = 2


class PathEnum(enum.Enum):
    SFTP = sftp
    AWS = aws


class FakeACL:
    allowed = True

    @staticmethod
    def currentContextPermission(acl, name):
        return 1 if FakeACL.allowed else 0

    @staticmethod
    def loadErrorJson(key, code):
        return ('ERRORJSON', key, code)


class Resp:
    def __init__(self, body):
        self.body = body


def build(source):
    ns = {
        'json': json, 'Path': Path, 'HttpResponse': Resp, 'IncBackupProvider': Provider, 'IncBackupPath': PathEnum,
        'ACLManager': FakeACL, '_get_user_acl': lambda request: (1, object()),
        'logging': types.SimpleNamespace(writeToFile=lambda m: None),
    }
    exec(source, ns)
    return ns['remove_destination']


real, control = build(func_src), build(without_guard)


def fresh():
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(sftp)
    os.makedirs(aws)
    open(os.path.join(sftp, '192.0.2.10'), 'w').write('192.0.2.10\n22')
    open(os.path.join(sftp, '192.0.2.11'), 'w').write('192.0.2.11\n22')
    open(os.path.join(aws, 'AKIAEXAMPLEKEY'), 'w').write('secret')
    open(outside, 'w').write('keep me')


def call(fn, kind, name, as_json=True):
    body = {'type': kind}
    if name is not None:
        body['IPAddress'] = name
    return fn(types.SimpleNamespace(body=json.dumps(body).encode()))


def status(resp):
    return resp if isinstance(resp, tuple) else json.loads(resp.body)


# normal removal still works
fresh()
r = status(call(real, 'SFTP', '192.0.2.10'))
check('removing an SFTP destination succeeds', (r['status'], os.path.exists(os.path.join(sftp, '192.0.2.10')), os.path.exists(os.path.join(sftp, '192.0.2.11'))), (1, False, True))
r = status(call(real, 'aws', 'AKIAEXAMPLEKEY'))
check('removing an AWS destination succeeds (type is case-insensitive)', (r['status'], os.listdir(aws)), (1, []))
fresh()
r = status(call(real, 'SFTP', '192.0.2.99'))
check('removing a destination that does not exist reports the same error as before', (r['destStatus'], 'No such file' in r['error_message'] or 'cannot find' in r['error_message'].lower() or '192.0.2.99' in r['error_message']), (0, True))
fresh()
r = status(call(real, 'SFTP', None))
check('a request without IPAddress still returns status 1 and removes nothing', (r['status'], sorted(os.listdir(sftp))), (1, ['192.0.2.10', '192.0.2.11']))
FakeACL.allowed = False
fresh()
r = status(call(real, 'SFTP', '192.0.2.10'))
check('without the permission nothing is removed (unchanged)', (r, os.path.exists(os.path.join(sftp, '192.0.2.10'))), (('ERRORJSON', 'destStatus', 0), True))
FakeACL.allowed = True

# traversal names are refused and nothing outside is touched
bad = {
    'parent folder': '../outside.txt',
    'two levels': '../../outside.txt',
    'absolute path': outside.replace('\\', '/'),
    'nested path': 'sub/../../outside.txt',
    'backslash path': '..\\outside.txt',
    'single dot': '.',
    'double dot': '..',
    'empty name': '',
    'NUL byte': '192.0.2.10\0x',
    'a list': ['192.0.2.10'],
    'a number': 5,
    'null': None,
}
for label, name in bad.items():
    if label == 'null':
        body = {'type': 'SFTP', 'IPAddress': None}
        fresh()
        r = status(real(types.SimpleNamespace(body=json.dumps(body).encode())))
    else:
        fresh()
        r = status(call(real, 'SFTP', name))
    check('%s: refused' % label, r, ('ERRORJSON', 'destStatus', 0))
    check('%s: the outside file and both destinations are untouched' % label, (os.path.exists(outside), sorted(os.listdir(sftp))), (True, ['192.0.2.10', '192.0.2.11']))

# the same names against the AWS folder
for name in ('../outside.txt', outside.replace('\\', '/')):
    fresh()
    r = status(call(real, 'AWS', name))
    check('AWS folder: %r is refused and the outside file stays' % (name if name.startswith('..') else 'absolute path',), (r, os.path.exists(outside)), (('ERRORJSON', 'destStatus', 0), True))

# control: without the check the same request deletes the file outside the folder
fresh()
call(control, 'SFTP', '../outside.txt')
check('control: without the check a parent-folder name deletes the outside file', os.path.exists(outside), False)
fresh()
call(control, 'SFTP', outside.replace('\\', '/'))
check('control: without the check an absolute path deletes the outside file', os.path.exists(outside), False)

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('IncBackups/views.py parses with the Python 3.9 grammar', parsed, True)
check('IncBackups/views.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

shutil.rmtree(work, ignore_errors=True)
print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
