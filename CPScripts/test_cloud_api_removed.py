"""Tests that the Cloud API (a remote management endpoint of the paid cloud platform: its router and access views, its 3,000 line manager,
the cluster and remote upgrade scripts it drove) is removed while the one thing free code shares with it stays: the deployment record
model the free WordPress install and staging code store (its table name carries the app name, so the app keeps only its model). The
website page status poll no longer goes through the manager, the request filter no longer exempts the removed path, and the real
code is run side by side with the old code it replaces (the old poll with a stand-in manager, the old filter conditions with the
operand put back as a control). Run: python3 CPScripts/test_cloud_api_removed.py"""
import ast
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


def exists(rel):
    return os.path.exists(os.path.join(ROOT, rel))


APP = 'cloud' + 'API'
# the old status poll of the manager, copied verbatim so the comparison survives the removal
OLD_STATUS = 'def statusFunc(self):\n    try:\n        statusFile = self.data[\'statusFile\']\n\n        if ACLManager.CheckStatusFilleLoc(statusFile):\n            pass\n        else:\n            data_ret = {\'abort\': 1, \'installStatus\': 0, \'installationProgress\': "100",\n                        \'currentStatus\': \'Invalid status file.\'}\n            json_data = json.dumps(data_ret)\n            return HttpResponse(json_data)\n\n\n        statusData = open(statusFile, \'r\').readlines()\n        try:\n            lastLine = statusData[-1]\n            if lastLine.find(\'[200]\') > -1:\n                command = \'rm -f \' + statusFile\n                ProcessUtilities.executioner(command)\n                data_ret = {\'status\': 1, \'abort\': 1, \'installationProgress\': "100", \'currentStatus\': lastLine}\n                json_data = json.dumps(data_ret)\n                return HttpResponse(json_data)\n            elif lastLine.find(\'[404]\') > -1:\n                data_ret = {\'status\': 0, \'abort\': 1, \'installationProgress\': "0", \'error_message\': lastLine}\n                json_data = json.dumps(data_ret)\n                return HttpResponse(json_data)\n            else:\n                progress = lastLine.split(\',\')\n                currentStatus = progress[0]\n                try:\n                    installationProgress = progress[1].rstrip(\'\\n\')\n                except:\n                    installationProgress = 0\n                data_ret = {\'status\': 1, \'abort\': 0, \'installationProgress\': installationProgress,\n                            \'currentStatus\': currentStatus}\n                json_data = json.dumps(data_ret)\n                return HttpResponse(json_data)\n        except IndexError:\n            data_ret = {\'status\': 1, \'abort\': 0, \'installationProgress\': 0,\n                        \'currentStatus\': \'Working..\'}\n            json_data = json.dumps(data_ret)\n            return HttpResponse(json_data)\n\n    except BaseException as msg:\n        data_ret = {\'status\': 0, \'abort\': 0, \'installationProgress\': "0", \'errorMessage\': str(msg)}\n        json_data = json.dumps(data_ret)\n        return HttpResponse(json_data)'

check('the router, the manager and the access view are gone', [exists(APP + '/' + n) for n in ('cloudManager.py', 'views.py', 'urls.py')], [False, False, False])
check('the cluster and remote upgrade scripts only that endpoint ran are gone', [exists('plogical/' + n) for n in ('ClusterManager.py', 'CyberPanelUpgrade.py')], [False, False])
check('the app keeps its model files', sorted(n for n in os.listdir(os.path.join(ROOT, APP)) if not n.startswith('__pycache__')), ['__init__.py', 'admin.py', 'apps.py', 'migrations', 'models.py', 'tests.py'])
models_tree = ast.parse(read(APP + '/models.py'))
dep = next(n for n in models_tree.body if isinstance(n, ast.ClassDef) and n.name == 'WPDeployments')
check('the deployment model keeps its two fields', sorted(t.id for n in dep.body if isinstance(n, ast.Assign) for t in n.targets), ['config', 'owner'])
users = sorted(r for r in ('websiteFunctions/StagingSetup.py', 'plogical/applicationInstaller.py') if APP + '.models import WPDeployments' in read(r))
check('the free staging and install code still import it and its table creation stays', (users, APP + '_wpdeployments' in read('plogical/upgrade.py')), (['plogical/applicationInstaller.py', 'websiteFunctions/StagingSetup.py'], True))

settings = ast.parse(read('CyberCP/settings.py'))
apps = next(n.value for n in settings.body if isinstance(n, ast.Assign) and any(getattr(t, 'id', '') == 'INSTALLED_APPS' for t in n.targets))
check('the app stays installed so its model keeps working', APP in [e.value for e in apps.elts if isinstance(e, ast.Constant)], True)
URLS = read('CyberCP/urls.py')
check('the root URL file no longer includes the app and keeps its neighbours', (APP in URLS, "include('emailMarketing.urls')" in URLS, "include('dockerManager.urls')" in URLS), (False, True, True))
check('no module imports the removed router, manager or access view', [
    r for r in [os.path.relpath(os.path.join(b, f), ROOT) for b, d, fs in os.walk(ROOT) if not any(x in b for x in ('.git', 'node_modules', 'static', 'locale')) for f in fs if f.endswith('.py') and not f.startswith('test_')]
    if re.search(APP + r'\.(cloudManager|views|urls)\b', read(r)) or 'import ' + APP + '.cloudManager' in read(r)], [])
named = [r for r in [os.path.relpath(os.path.join(b, f), ROOT) for b, d, fs in os.walk(ROOT) if not any(x in b for x in ('.git', 'node_modules', 'static', 'locale')) for f in fs if f.endswith(('.py', '.sh', '.html', '.js')) and not f.startswith('test_')]
         if 'ClusterManager' in open(os.path.join(ROOT, r), encoding='utf-8', errors='replace').read() or 'CyberPanelUpgrade' in open(os.path.join(ROOT, r), encoding='utf-8', errors='replace').read()]
check('nothing names the cluster or remote upgrade scripts', named, [])

# the request filter
SEC = read('CyberCP/secMiddleware.py')
stree = ast.parse(SEC)
tests = [n.test for n in ast.walk(stree) if isinstance(n, ast.If) and '/backup/localInitiate' in (ast.get_source_segment(SEC, n.test) or '')]
check('the session exemption condition is found once', len(tests), 1)
EXEMPT = re.sub(r'\\\s*\n', ' ', ast.get_source_segment(SEC, tests[0])).replace('\n', ' ')
PATHS = {'/backup/localInitiate': True, '/': True, '/verifyLogin': True, '/logout': True, '/api/x': True, '/anything/webhook': True, '/anything/gitNotify': True,
         '/' + APP: False, '/' + APP + '/access': False, '/websites/list': False, '/emailPremium/statusFunc': False}
got = {p: bool(eval(EXEMPT, {'pathActual': p})) for p in PATHS}
check('the removed path no longer bypasses the session check and every other exemption is unchanged', got, PATHS)
old_exempt = EXEMPT.replace(" or pathActual.endswith('/gitNotify')", " or pathActual.startswith('/" + APP + "') or pathActual.endswith('/gitNotify')")
check('control: with the operand put back the removed path would bypass the check and the check sees it', (old_exempt != EXEMPT, bool(eval(old_exempt, {'pathActual': '/' + APP + '/access'}))), (True, True))
calls = [n for n in ast.walk(stree) if isinstance(n, ast.If) and "'verifyLogin'" in (ast.get_source_segment(SEC, n.test) or '') and "'docker'" in (ast.get_source_segment(SEC, n.test) or '')]
check('the body filter exemption condition is found once', len(calls), 1)
FILTER = re.sub(r'\\\s*\n', ' ', ast.get_source_segment(SEC, calls[0].test)).replace('\n', ' ')
URLCASES = {'http://h/api/remoteTransfer': True, 'http://h/api/verifyConn': True, 'http://h/x/webhook': True, 'http://h/saveSpamAssassinConfigurations': True, 'http://h/docker/x': True,
            'http://h/verifyLogin': True, 'http://h/submitUserCreation': True, 'http://h/' + APP + '/': False, 'http://h/websites/submitWebsiteCreation': False}
check('the body filter no longer exempts the removed path and every other exemption is unchanged', {u: bool(eval(FILTER, {'FinalURL': u})) for u in URLCASES}, URLCASES)
check('no other mention of the app in the filter', len(re.findall(APP, SEC)), 1)

# the website page status poll
SRC = read('websiteFunctions/views.py')
vtree = ast.parse(SRC)
funcs = {n.name: n for n in vtree.body if isinstance(n, ast.FunctionDef)}


def seg(name):
    return ast.get_source_segment(SRC, funcs[name])


files = {}
calls_made = []
stub_acl = types.SimpleNamespace(CheckStatusFilleLoc=lambda f: f.startswith('/valid/'))
stub_pu = types.SimpleNamespace(executioner=lambda c: calls_made.append(c))


class FakeFile:
    def __init__(self, content):
        self.content = content

    def readlines(self):
        return self.content.splitlines(True)


def fake_open(path, mode='r'):
    if path not in files:
        raise FileNotFoundError(path)
    return FakeFile(files[path])


class Admins:
    present = True

    class objects:
        @staticmethod
        def get(**kw):
            if not Admins.present:
                raise LookupError('no such administrator')
            return types.SimpleNamespace(pk=kw['pk'])


def redirect(target):
    return ('redirect', target)


respond = lambda b: json.loads(b)
sys.modules['plogical.acl'] = types.SimpleNamespace(ACLManager=stub_acl)
sys.modules['plogical.processUtilities'] = types.SimpleNamespace(ProcessUtilities=stub_pu)
ns_new = {'json': json, 'HttpResponse': respond, 'Administrator': Admins, 'redirect': redirect, 'loadLoginPage': 'login-page', 'open': fake_open}
exec(seg('fetchStatusFileProgress') + '\n\n' + seg('statusFunc'), ns_new)

OLD_VIEW = '''def statusFunc(request):
    try:
        userID = request.session['userID']
        data = json.loads(request.body)
        from cloudAPI.cloudManager import CloudManager
        admin = Administrator.objects.get(pk=userID)
        cm = CloudManager(data, admin)
        return cm.statusFunc()
    except KeyError:
        return redirect(loadLoginPage)
'''
ns_cloud = {'json': json, 'HttpResponse': respond, 'ACLManager': stub_acl, 'ProcessUtilities': stub_pu, 'open': fake_open}
exec(OLD_STATUS, ns_cloud)


class FakeCloud:
    def __init__(self, data=None, admin=None):
        self.data, self.admin = data, admin

    statusFunc = ns_cloud['statusFunc']


sys.modules[APP] = types.ModuleType(APP)
sys.modules[APP + '.cloudManager'] = types.SimpleNamespace(CloudManager=FakeCloud)
ns_old = {'json': json, 'Administrator': Admins, 'redirect': redirect, 'loadLoginPage': 'login-page', 'HttpResponse': respond}
exec(OLD_VIEW, ns_old)

NL = chr(10)
files.update({'/valid/a': 'step,50' + NL + 'all done [200]' + NL, '/valid/b': 'x' + NL + 'it failed [404]' + NL, '/valid/c': 'Installing the thing,35' + NL, '/valid/d': 'Working' + NL, '/valid/e': ''})
CASES = {'invalid location': ({'statusFile': '/other'}, True, True), 'finished': ({'statusFile': '/valid/a'}, True, True), 'failed': ({'statusFile': '/valid/b'}, True, True),
         'progress': ({'statusFile': '/valid/c'}, True, True), 'no percentage': ({'statusFile': '/valid/d'}, True, True), 'empty file': ({'statusFile': '/valid/e'}, True, True),
         'missing key': ({}, True, True), 'missing file': ({'statusFile': '/valid/gone'}, True, True), 'no session': ({'statusFile': '/valid/a'}, False, True), 'no administrator': ({'statusFile': '/valid/a'}, True, False)}


def call(ns, data, session, present):
    Admins.present = present
    del calls_made[:]
    request = types.SimpleNamespace(session={'userID': 1} if session else {}, body=json.dumps(data))
    try:
        result = ns['statusFunc'](request)
    except BaseException as exc:
        result = ('raised', type(exc).__name__)
    return result, list(calls_made)


same = {k: call(ns_new, *v) == call(ns_old, *v) for k, v in CASES.items()}
check('the view answers every scenario exactly like the old view through the manager and makes the same calls (including no session and no administrator)', same, {k: True for k in CASES})
check('the scenarios differ from each other (a finished poll removes its file, a failed one does not)',
      (call(ns_new, *CASES['finished'])[1], call(ns_new, *CASES['failed'])[1], call(ns_new, *CASES['no session'])[0], call(ns_new, *CASES['no administrator'])[0]),
      (['rm -f /valid/a'], [], ('redirect', 'login-page'), ('raised', 'LookupError')))
check('the view file no longer names the app or its manager', (APP in SRC, 'CloudManager' in SRC), (False, False))
for m in ('plogical.acl', 'plogical.processUtilities', APP, APP + '.cloudManager'):
    sys.modules.pop(m, None)

for rel in ('CyberCP/secMiddleware.py', 'CyberCP/urls.py', 'websiteFunctions/views.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
