"""Tests clearLogFile in serverLogs/views.py: only the log files the page can show may be cleared.
The real function source is taken from the file and run with stubs, so nothing is executed and nothing is truncated.
It also reads the file names the page's own JavaScript sends, so the allow-list and the page cannot drift apart.
Run: python3 CPScripts/test_clear_log_file.py"""
import ast
import json
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, 'serverLogs', 'views.py')
JS = os.path.join(ROOT, 'serverLogs', 'static', 'serverLogs', 'serverLogs.js')

src = open(SOURCE, encoding='utf-8').read()
node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'clearLogFile')
func_src = ast.get_source_segment(src, node)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


executed = []


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeACL:
    admin = 1

    @staticmethod
    def loadedACL(user_id):
        return {'admin': FakeACL.admin}

    @staticmethod
    def loadErrorJson(key, code):
        return 'ERR:%s:%s' % (key, code)


class FakeProcess:
    @staticmethod
    def outputExecutioner(command):
        executed.append(command)
        return '1,None'


ns = {
    'json': json, 'HttpResponse': FakeResponse, 'ACLManager': FakeACL, 'ProcessUtilities': FakeProcess,
    'installUtilities': types.SimpleNamespace(Server_root_path='/usr/local/lsws'),
    'virtualHostUtilities': types.SimpleNamespace(cyberPanel='/usr/local/CyberCP'),
    'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=lambda m: None)),
}
exec(func_src, ns)
clear = ns['clearLogFile']


def call(file_name, method='POST', admin=1, session=True, raw=None):
    FakeACL.admin = admin
    executed.clear()
    body = raw if raw is not None else json.dumps({'fileName': file_name}).encode()
    request = types.SimpleNamespace(method=method, body=body, session={'userID': 1} if session else {})
    result = clear(request)
    return result.content if isinstance(result, FakeResponse) else result


ALLOWED = ['/usr/local/lsws/logs/access.log', '/usr/local/lsws/logs/error.log', '/var/log/maillog', '/var/log/mail.log',
           '/var/log/messages', '/var/log/syslog', '/usr/local/lsws/logs/auditmodsec.log', '/home/cyberpanel/error-logs.txt']

for path in ALLOWED:
    out = call(path)
    check('allowed: %s is cleared with the original command' % path, (json.loads(out)['cleanStatus'], executed),
          (1, ['/usr/local/CyberCP/bin/python /usr/local/CyberCP/plogical/serverLogs.py cleanLogFile --fileName ' + path]))

ATTACKS = [
    ('/etc/passwd', 'an arbitrary file'),
    ('/etc/shadow', 'another arbitrary file'),
    ('/usr/local/lsws/logs/access.log --fileName /etc/passwd', 'an extra argument after a valid path'),
    ('/usr/local/lsws/logs/access.log /etc/passwd', 'a second path after a valid one'),
    ('/usr/local/lsws/logs/../../../etc/passwd', 'a traversal through the log folder'),
    ('/usr/local/lsws/logs/access.log ', 'a trailing space'),
    ('/usr/local/lsws/logs/access.log\n', 'a trailing newline'),
    ('/usr/local/lsws/logs/', 'the log folder itself'),
    ('/home/cyberpanel/error-logs.txt.bak', 'a similar name'),
    ('', 'an empty name'),
    ('/USR/LOCAL/LSWS/LOGS/ACCESS.LOG', 'a different case'),
]
for value, label in ATTACKS:
    out = call(value)
    check('refused: %s' % label, (out, executed), ('ERR:cleanStatus:0', []))

check('refused: a name that is not a string', (call(['/var/log/maillog']), executed), ('ERR:cleanStatus:0', []))
check('refused: a number', (call(123), executed), ('ERR:cleanStatus:0', []))
check('refused: null', (call(None), executed), ('ERR:cleanStatus:0', []))

# behaviour that must not change
check('a non administrator is still refused and nothing runs', (call('/var/log/maillog', admin=0), executed), ('ERR:cleanStatus:0', []))
out = call(None, raw=json.dumps({'other': 1}).encode())
check('a body without fileName still gives the error response and nothing runs', (json.loads(out)['cleanStatus'], executed), (0, []))
out = call('/var/log/maillog', session=False)
check('a request without a session still gives the error response and nothing runs', (json.loads(out)['cleanStatus'], executed), (0, []))

# the page and the allow-list stay in step
js = open(JS, encoding='utf-8').read()
sent = sorted(set(re.findall(r'fileName: "([^"]+)"', js)))
check('the page sends five log names', len(sent), 5)
check('every name the page sends is accepted', [s for s in sent if json.loads(call(s))['cleanStatus'] != 1], [])

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('views.py parses with the Python 3.9 grammar', parsed, True)
check('views.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
