"""Tests DatabaseManager.MySQLManager in databases/databaseManager.py: the MySQL Manager page no longer asks a third-party licence service
whether it may open. It always renders its own template for administrators (its permission argument is unchanged), makes no network call
and does not read the host address. The neighbouring methods, the route and the sidebar entry are unchanged. The real method is run with
stand-ins and a request library that fails on any call. The old method is rebuilt from the new one as a control. Names are built here so
this file does not name the licence service.
Run: python3 CPScripts/test_mysql_manager_without_licence_call.py"""
import ast
import hashlib
import json
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


SRC = read('databases/databaseManager.py')
cls = next(n for n in ast.parse(SRC).body if isinstance(n, ast.ClassDef) and n.name == 'DatabaseManager')
methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
node = methods['MySQLManager']
source = ast.get_source_segment(SRC, node).replace('\n' + ' ' * node.col_offset, '\n')

HOST = 'platform.' + 'cyberpersons.com'
SERVICE = 'https://' + HOST + '/Cyberpanel' + 'AdOns/' + 'Adon' + 'permission'
check('the method no longer names the licence service, the request library or the host address lookup', [w for w in (HOST, 'Adon' + 'permission', 'req' + 'uests', 'fetchIP', 'cyberpanel-' + 'addons') if w in source], [])

calls = []


class Fake:
    @staticmethod
    def post(url, *a, **k):
        calls.append(url)
        raise AssertionError('licence service called')


def run(code, status=None, error=False):
    del calls[:]
    posts = []

    class Resp:
        def json(self):
            return {'status': status}

    class Req:
        @staticmethod
        def post(url, data=None):
            posts.append(url)
            if error:
                raise RuntimeError('unreachable')
            return Resp()

    class Page:
        def __init__(self, request, template, data, function):
            self.args = (template, data, function)

        def render(self):
            return ('rendered',) + self.args

    sys.modules['requests'] = Req if (status is not None or error) else Fake
    pu = types.SimpleNamespace(decideServer=lambda: 'ols', OLS='ols', ent='ent')
    pl = types.ModuleType('plogical')
    pl.__path__ = []
    pm = types.ModuleType('plogical.processUtilities')
    pm.ProcessUtilities = pu
    saved = {k: sys.modules.get(k) for k in ('plogical', 'plogical.processUtilities')}
    sys.modules['plogical'], sys.modules['plogical.processUtilities'] = pl, pm
    ns = {'json': json, 'httpProc': Page, 'redirect': lambda url: ('redirect', url), 'ACLManager': types.SimpleNamespace(fetchIP=lambda: calls.append('address') or '192.0.2.1'),
          'ProcessUtilities': types.SimpleNamespace(decideServer=lambda: 'ols', OLS='ols', ent='ent')}
    exec(code, ns)
    try:
        out = ns['MySQLManager'](types.SimpleNamespace(), request=None, userID=1)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return out, posts, list(calls)


out, posts, calls_made = run(source)
check('the page renders its own template for administrators with no call and no address lookup', (out, posts, calls_made), (('rendered', 'databases/mysqlmanager.html', None, 'admin'), [], []))

OLD = ("    try:" + chr(10) + chr(10) + "        from plogical.processUtilities import ProcessUtilities" + chr(10) + "        if ProcessUtilities.decideServer() == ProcessUtilities.OLS:" + chr(10) + chr(10) +
       "            url = " + chr(34) + SERVICE + chr(34) + chr(10) + "            data = {" + chr(10) + "                " + chr(34) + "name" + chr(34) + ": " + chr(34) + "Filemanager" + chr(34) + "," + chr(10) +
       "                " + chr(34) + "IP" + chr(34) + ": ACLManager.fetchIP()" + chr(10) + "            }" + chr(10) + chr(10) + "            import requests" + chr(10) +
       "            response = requests.post(url, data=json.dumps(data))" + chr(10) + "            Status = response.json()['status']" + chr(10) + chr(10) + "            if (Status == 1):" + chr(10) +
       "                template = 'baseTemplate/FileManager.html'" + chr(10) + "            else:" + chr(10) + "                return redirect(" + chr(34) + "https://cyberpanel.net/cyberpanel-" + 'addons' + chr(34) + ")" + chr(10) +
       "        else:" + chr(10) + "            template = 'databases/mysqlmanager.html'" + chr(10) + "    except BaseException as msg:" + chr(10) + "        template = 'databases/mysqlmanager.html'" + chr(10) + chr(10))
anchor = "    template = 'databases/mysqlmanager.html'" + chr(10)
assert source.count(anchor) == 1
old_source = source.replace(anchor, OLD + anchor)
out, posts, calls_made = run(old_source, status=0)
check('control: the old method with a no answer sent the user to the add-on store and read the host address', (out[0], posts, calls_made), ('redirect', [SERVICE], ['address']))
out, posts, calls_made = run(old_source, status=1)
check('control: the old method with a yes answer rendered the page', (out[0], out[1]), ('rendered', 'databases/mysqlmanager.html'))
out, posts, calls_made = run(old_source, error=True)
check('control: the old method with an unreachable service also rendered the page', (out[0], out[1], posts), ('rendered', 'databases/mysqlmanager.html', [SERVICE]))

PIN = {'loadDatabaseHome': '3ecce0c9503d4ec9', 'createDatabase': 'eecfcc58b0071d42', 'Upgardemysql': '997bfd857ecdac33',
       'fetchDatabases': '8b514cf269d6086c', 'listDBs': 'e222a5a707949008'}
check('five neighbouring methods are exactly as they were', {n: hashlib.sha256(ast.get_source_segment(SRC, methods[n]).encode()).hexdigest()[:16] if n in methods else None for n in PIN}, PIN)
check('the free database methods are still all there', sorted(set(['loadDatabaseHome', 'phpMyAdmin', 'createDatabase', 'submitDBCreation', 'deleteDatabase', 'fetchDatabases', 'submitDatabaseDeletion', 'listDBs', 'changePassword', 'remoteAccess', 'allowRemoteIP', 'generatePHPMYAdminData']) - set(methods)), [])
check('the route and the sidebar entry are unchanged', ("name='MysqlManager'" in read('databases/urls.py'), "url 'MysqlManager'" in read('baseTemplate/templates/baseTemplate/index.html')), (True, True))
check('the database app names no licence service any more', [w for w in (HOST, 'Adon' + 'permission', 'CheckFor' + 'PremFeature') if w in read('databases/databaseManager.py') + read('databases/views.py')], [])
try:
    ast.parse(open(os.path.join(ROOT, 'databases/databaseManager.py'), 'rb').read(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('databaseManager.py parses with the Python 3.9 grammar and has no carriage returns', (parsed, b'\r' in open(os.path.join(ROOT, 'databases/databaseManager.py'), 'rb').read()), (True, False))

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
