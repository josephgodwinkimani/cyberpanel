"""Tests WebsiteManager.tuneSettings in websiteFunctions/website.py: it only replaces the website's own PHP-FPM pool file and
only with plain integer settings, and a legitimate request behaves as before. The real method is run with stand-ins for the
access checks, the models, the pool file lookup and the command runner (nothing is written or run).
Run: python3 CPScripts/test_tune_settings_pool_file.py"""
import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'websiteFunctions', 'website.py')

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
cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == 'WebsiteManager')
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'tuneSettings')
raw = ast.get_source_segment(src, node)
dedent = lambda text: text.replace('\n' + ' ' * node.col_offset, '\n')
real_src = dedent(raw)

path_test = 'if not expectedPhpPath or phpPath != expectedPhpPath:'
int_line = "pmMaxChildren = str(int(pmMaxChildren))"
assert raw.count(path_test) == 1 and raw.count(int_line) == 1
no_path_check = dedent(raw.replace(path_test, 'if False:'))
no_int_check = dedent(raw.replace(int_line, 'pass'))

TEMPLATE = 'user = {externalApp}\npm.max_children = {pmMaxChildren}\npm.start_servers = {pmStartServers}\npm.min_spare_servers = {pmMinSpareServers}\npm.max_spare_servers = {pmMaxSpareServers}\n[{www}] {Sock} {sockPath} {group}\n'

state = {}


def build(source, distro='centos', pool=None):
    commands, written, normal = [], {}, []

    class FakeFile:
        def __init__(self, path, mode='r'):
            self.path = path
            written[path] = ''

        def writelines(self, text):
            written[self.path] += text

        def write(self, text):
            written[self.path] += text

        def close(self):
            pass

    pu = types.SimpleNamespace(
        decideDistro=lambda: distro, centos='centos', cent8='cent8', ubuntu='ubuntu', ubuntu20='ubuntu20',
        executioner=lambda c, *a, **k: commands.append(c), normalExecutioner=lambda c, *a, **k: normal.append(c),
        debugPath='/nonexistent/debug')
    ns = {
        'json': json, 'os': os, 're': __import__('re'), 'randint': lambda a, b: 1234, 'open': FakeFile,
        'HttpResponse': lambda b: json.loads(b) if isinstance(b, str) else b,
        'ACLManager': types.SimpleNamespace(loadedACL=lambda u: {'admin': 0}, checkOwnership=lambda d, a, c: 1,
                                            loadErrorJson=lambda *a: {'status': 0, 'errorMessage': 'You are not authorized to access this resource.'}),
        'Administrator': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda pk: object())),
        'Websites': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda domain: types.SimpleNamespace(externalApp='siteuser'))),
        'ChildDomains': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda domain: None)),
        'ProcessUtilities': pu, 'vhostConfs': types.SimpleNamespace(phpFpmPoolReplace=TEMPLATE),
        'ApacheVhost': types.SimpleNamespace(whichPHPExists=lambda d: pool.get(d) if pool else None,
                                             DecideFPMServiceName=lambda v: 'svc-' + v.replace(' ', '')),
        'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=lambda m: None)),
    }
    exec(source, ns)
    fn = ns['tuneSettings']
    return (lambda data: fn(types.SimpleNamespace(), 1, data)), commands, written, normal


GOOD = '/etc/opt/remi/php74/php-fpm.d/a.example.conf'
OTHER = '/etc/opt/remi/php74/php-fpm.d/b.example.conf'
POOLS = {'a.example': GOOD, 'b.example': OTHER}


def request(path=GOOD, **over):
    d = {'domainName': 'a.example', 'pmMaxChildren': '10', 'pmStartServers': '4', 'pmMinSpareServers': '4', 'pmMaxSpareServers': '8', 'phpPath': path}
    d.update(over)
    return d


# a legitimate request
fn, cmds, written, normal = build(real_src, pool=POOLS)
r = fn(request())
check('legitimate request succeeds', r, {'status': 1})
check('the pool file is moved over the site\'s own pool file with the same command as before', cmds, ['sudo mv /home/cyberpanel/1234 ' + GOOD])
check('the written pool file holds the posted numbers', ('pm.max_children = 10' in written['/home/cyberpanel/1234'], 'pm.max_spare_servers = 8' in written['/home/cyberpanel/1234']), (True, True))
check('the PHP-FPM service is stopped and restarted as before', normal, ['systemctl stop svc-PHP7.4', 'systemctl restart svc-PHP7.4'])

fn, cmds, written, normal = build(real_src, distro='ubuntu', pool={'a.example': '/etc/php/8.1/fpm/pool.d/a.example.conf'})
r = fn(request(path='/etc/php/8.1/fpm/pool.d/a.example.conf'))
# the service name on Debian paths comes from phpPath[2] (the literal 'php' segment): unchanged here, only the move target matters
check('a Debian style pool path works as before', (r, cmds, normal), ({'status': 1}, ['sudo mv /home/cyberpanel/1234 /etc/php/8.1/fpm/pool.d/a.example.conf'], ['systemctl stop svc-PHPphp', 'systemctl restart svc-PHPphp']))

fn, cmds, written, normal = build(real_src, pool=POOLS)
r = fn(request(pmMaxChildren=10, pmStartServers=4, pmMinSpareServers=4, pmMaxSpareServers=8))
check('numbers sent as JSON integers also work', (r, cmds), ({'status': 1}, ['sudo mv /home/cyberpanel/1234 ' + GOOD]))

# the path
hostile_paths = {
    'an unrelated system file': '/etc/passwd',
    'a path with parent folders': '/etc/opt/remi/php74/php-fpm.d/../../../../etc/passwd',
    'the right path plus extra mv arguments': GOOD + ' -t /etc',
    "another website's pool file": OTHER,
    'a path that does not exist for the site': '/etc/opt/remi/php74/php-fpm.d/zzz.conf',
    'an empty path': '',
}
for label, path in hostile_paths.items():
    fn, cmds, written, normal = build(real_src, pool=POOLS)
    r = fn(request(path=path))
    check('%s: refused, nothing written or moved or restarted' % label, (r['status'], cmds, written, normal), (0, [], {}, []))

fn, cmds, written, normal = build(real_src, pool={})
r = fn(request())
check('a site without a pool file is refused (nothing to tune)', (r['status'], cmds), (0, []))

fn, cmds, written, normal = build(real_src, pool={})
r = fn(request(path=None))
check('no pool file and a null path: refused, nothing moved (None must not match None)', (r['status'], cmds, written, normal), (0, [], {}, []))
fn, cmds, written, normal = build(no_path_check, pool={})
fn(request(path=None))
check('control: without the check a null path would run mv with the text None', cmds, ['sudo mv /home/cyberpanel/1234 None'])

fn, cmds, written, normal = build(no_path_check, pool=POOLS)
fn(request(path='/etc/passwd'))
check('control: without the path check the move command targets /etc/passwd', cmds, ['sudo mv /home/cyberpanel/1234 /etc/passwd'])

# the numbers
for label, over in (('pm.max_children with a new line and extra directive', {'pmMaxChildren': '10\nuser = root'}),
                    ('pm.max_children with text', {'pmMaxChildren': 'many'}),
                    ('pm.start_servers with text', {'pmStartServers': '4; x'}),
                    ('pm.max_spare_servers with text', {'pmMaxSpareServers': '8\nlisten = /x'})):
    fn, cmds, written, normal = build(real_src, pool=POOLS)
    r = fn(request(**over))
    check('%s: refused with the handler error response and nothing written' % label, (r['status'], 'error_message' in r, cmds, written), (0, True, [], {}))

fn, cmds, written, normal = build(no_int_check, pool=POOLS)
fn(request(pmMaxChildren='10\nuser = root'))
check('control: without the number check an extra directive is written into the pool file', 'user = root' in written.get('/home/cyberpanel/1234', ''), True)

# the existing relation between the numbers is unchanged
fn, cmds, written, normal = build(real_src, pool=POOLS)
r = fn(request(pmStartServers='5', pmMinSpareServers='4'))
check('the existing start/min spare check still applies', (r['status'], cmds), (0, []))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('website.py parses with the Python 3.9 grammar', parsed, True)
check('website.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
