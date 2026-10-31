"""Tests that the installer log writes only to its local file: the module no longer sends every log line and the server address to the
external platform (a network call with a ten second timeout per line), and the local log keeps the same format and the same percentage
handling. The real function is run with a request library that fails on any use (and with the old form as a control that proves the check
sees the call), and the other installer modules are checked for left over uses of the removed address.
Run: python3 CPScripts/test_install_log_stays_local.py"""
import ast
import os
import re
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATH = os.path.join(ROOT, 'install', 'installLog.py')

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


SRC = open(PATH, encoding='utf-8').read()
tree = ast.parse(SRC)
HOST = 'platform.' + 'cyberpersons.com'
imports = sorted(a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names)
check('the module imports only the time module', imports, ['time'])
check('the module names no external address and no request call', [w for w in (HOST, 'requests', 'json', 'LogURL', 'post(') if w in SRC], [])
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'InstallLog')
attrs = sorted(t.id for n in cls.body if isinstance(n, ast.Assign) for t in n.targets)
check('the class keeps the file name, the percentage and the server address attributes', attrs, ['ServerIP', 'currentPercent', 'fileName'])


class Forbidden(types.ModuleType):
    calls = []

    def __getattr__(self, name):
        Forbidden.calls.append(name)
        raise AssertionError('the request library was used: ' + name)


def run(source, messages):
    Forbidden.calls = []
    saved = sys.modules.get('requests')
    sys.modules['requests'] = Forbidden('requests')
    handle, path = tempfile.mkstemp()
    os.close(handle)
    try:
        ns = {'__name__': 'installLog'}
        exec(compile(source, 'installLog.py', 'exec'), ns)
        ns['time'].strftime = lambda fmt: 'TS'
        cls_ = ns['InstallLog']
        cls_.fileName = path
        for m in messages:
            cls_.writeToFile(m)
        return open(path, encoding='utf-8').read().split('\n')[:-1], cls_.currentPercent, list(Forbidden.calls)
    finally:
        os.remove(path)
        if saved is None:
            sys.modules.pop('requests', None)
        else:
            sys.modules['requests'] = saved


MESSAGES = ['starting', 'step one,40', 'mount -o remount,rw', 'usermod -G lscpd,nobody x', 'after']
lines, percent, calls = run(SRC, MESSAGES)
check('every message is written to the local file in the same format and without any request', (lines, percent, calls),
      (['[TS] starting,10', '[TS] step one,40', '[TS] mount -o remount-rw,40', '[TS] usermod -G lscpd-nobody x,40', '[TS] after,40'], '40', []))

OLD = SRC.replace('import time\n', 'import json\nimport time\n\nimport requests\n', 1).replace(
    "    ServerIP = ''\n", "    LogURL = 'https://" + HOST + "/servers/RecvData'\n    ServerIP = ''\n", 1) + (
    "\n        try:\n            finalData = json.dumps({'ipAddress': InstallLog.ServerIP, \"InstallCyberPanelStatus\": message})\n"
    "            requests.post(InstallLog.LogURL, data=finalData, timeout=10)\n        except:\n            pass\n")
old_lines, old_percent, old_calls = run(OLD, ['starting'])
check('control: the old form reaches for the request library on every message and the check sees it', (old_calls, old_lines), (['post'], ['[TS] starting,10']))

# the other installer modules
leftovers = []
for name in sorted(os.listdir(os.path.join(ROOT, 'install'))):
    if name.endswith('.py') and name != 'installLog.py' and not name.startswith('test_'):
        text = open(os.path.join(ROOT, 'install', name), encoding='utf-8', errors='replace').read()
        leftovers += [(name, w) for w in ('InstallLog.LogURL', HOST + '/servers/RecvData') if w in text]
check('no other installer module reads the removed address', leftovers, [])
users = [n for n in ('install.py', 'installCyberPanel.py', 'unInstall.py') if re.search(r'import installLog as logging', open(os.path.join(ROOT, 'install', n), encoding='utf-8', errors='replace').read())]
check('the three installer modules still import the log module and use its local writer', users, ['install.py', 'installCyberPanel.py', 'unInstall.py'])

try:
    ast.parse(open(PATH, 'rb').read(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('install/installLog.py parses with the Python 3.9 grammar', parsed, True)
check('install/installLog.py has no carriage returns', b'\r' in open(PATH, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
