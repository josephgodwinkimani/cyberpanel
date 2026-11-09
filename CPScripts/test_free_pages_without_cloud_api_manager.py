"""Tests that the free pages no longer import the Cloud API manager: the Onboarding status poll (emailPremium/statusFunc) and the Optimize
MySQL page now carry their own copy of the code they used from it, and the unused import in the database views is gone. The new code is
run side by side with the Cloud API manager methods it was copied from (taken from the same tree) with stand-ins for the access checks,
the process runner, the memory reader and the status files, and both must give the same answers and make the same calls, including the
failure paths. Needs no network and writes only temporary files that it removes.
Run: python3 CPScripts/test_free_pages_without_cloud_api_manager.py"""
import ast
import json
import os
import sys
import tempfile
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


def segment(src, name, scope=None):
    tree = ast.parse(src)
    body = tree.body if scope is None else next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == scope).body
    node = next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, node).replace('\n' + ' ' * node.col_offset, '\n')


# the Cloud API manager methods the free pages used to call, copied verbatim so the comparison survives the removal of that app
OLD_STATUS = 'def statusFunc(self):\n    try:\n        statusFile = self.data[\'statusFile\']\n\n        if ACLManager.CheckStatusFilleLoc(statusFile):\n            pass\n        else:\n            data_ret = {\'abort\': 1, \'installStatus\': 0, \'installationProgress\': "100",\n                        \'currentStatus\': \'Invalid status file.\'}\n            json_data = json.dumps(data_ret)\n            return HttpResponse(json_data)\n\n\n        statusData = open(statusFile, \'r\').readlines()\n        try:\n            lastLine = statusData[-1]\n            if lastLine.find(\'[200]\') > -1:\n                command = \'rm -f \' + statusFile\n                ProcessUtilities.executioner(command)\n                data_ret = {\'status\': 1, \'abort\': 1, \'installationProgress\': "100", \'currentStatus\': lastLine}\n                json_data = json.dumps(data_ret)\n                return HttpResponse(json_data)\n            elif lastLine.find(\'[404]\') > -1:\n                data_ret = {\'status\': 0, \'abort\': 1, \'installationProgress\': "0", \'error_message\': lastLine}\n                json_data = json.dumps(data_ret)\n                return HttpResponse(json_data)\n            else:\n                progress = lastLine.split(\',\')\n                currentStatus = progress[0]\n                try:\n                    installationProgress = progress[1].rstrip(\'\\n\')\n                except:\n                    installationProgress = 0\n                data_ret = {\'status\': 1, \'abort\': 0, \'installationProgress\': installationProgress,\n                            \'currentStatus\': currentStatus}\n                json_data = json.dumps(data_ret)\n                return HttpResponse(json_data)\n        except IndexError:\n            data_ret = {\'status\': 1, \'abort\': 0, \'installationProgress\': 0,\n                        \'currentStatus\': \'Working..\'}\n            json_data = json.dumps(data_ret)\n            return HttpResponse(json_data)\n\n    except BaseException as msg:\n        data_ret = {\'status\': 0, \'abort\': 0, \'installationProgress\': "0", \'errorMessage\': str(msg)}\n        json_data = json.dumps(data_ret)\n        return HttpResponse(json_data)'
OLD_AJAX = "def ajaxPre(self, status, errorMessage):\n    final_dic = {'status': status, 'error_message': errorMessage}\n    final_json = json.dumps(final_dic)\n    return HttpResponse(final_json)"
OLD_RAM = "def fetchRam(self, request):\n    try:\n        # request.session['userID'] = self.admin.pk\n        # currentACL = ACLManager.loadedACL(self.admin.pk)\n        #\n        # if currentACL['admin'] == 0:\n        #     return self.ajaxPre(0, 'Only administrators can see MySQL status.')\n\n        # if ProcessUtilities.decideDistro() == ProcessUtilities.ubuntu:\n        #    return self.ajaxPre(0, 'This feature is currently only available on CentOS.')\n\n        from psutil import virtual_memory\n        import math\n\n        finalData = {}\n        mem = virtual_memory()\n        inGB = math.ceil(float(mem.total) / float(1024 * 1024 * 1024))\n        finalData['ramInGB'] = inGB\n\n        if ProcessUtilities.decideDistro() == ProcessUtilities.centos or ProcessUtilities.decideDistro() == ProcessUtilities.cent8:\n            finalData['conf'] = ProcessUtilities.outputExecutioner('sudo cat /etc/my.cnf')\n        else:\n            finalData['conf'] = ProcessUtilities.outputExecutioner('sudo cat /etc/mysql/my.cnf')\n\n        finalData['status'] = 1\n\n        finalData = json.dumps(finalData)\n        return HttpResponse(finalData)\n    except BaseException as msg:\n        return self.ajaxPre(0, str(msg))"
VIEWS, MANAGER, DBVIEWS = read('emailPremium/views.py'), read('databases/databaseManager.py'), read('databases/views.py')
PACKAGE = 'cloud' + 'API'
check('the three free modules no longer name the Cloud API app or its manager', [n for n, t in (('emailPremium/views.py', VIEWS), ('databases/databaseManager.py', MANAGER), ('databases/views.py', DBVIEWS)) if PACKAGE in t or 'CloudManager' in t], [])

# the Onboarding status poll
calls = []


def build_helper(source, name):
    stub_acl = types.SimpleNamespace(CheckStatusFilleLoc=lambda f: 'valid' in f, loadedACL=lambda u: {'admin': 1}, loadErrorJson=lambda *a: {'status': 0, 'errorMessage': 'denied'})
    stub_pu = types.SimpleNamespace(executioner=lambda c: calls.append(c))
    ns = {'ACLManager': stub_acl, 'ProcessUtilities': stub_pu, 'HttpResponse': lambda b: json.loads(b), 'json': json}
    exec(source, ns)
    return ns[name]


new_fn = build_helper(segment(VIEWS, 'fetchStatusFileProgress'), 'fetchStatusFileProgress')
old_fn = build_helper(OLD_STATUS, 'statusFunc')
tmp = tempfile.mkdtemp()


def status_file(name, content):
    path = os.path.join(tmp, name + '_valid')
    open(path, 'w').write(content)
    return path


SCENARIOS = {'invalid location': {'statusFile': os.path.join(tmp, 'other')}, 'finished': {'statusFile': status_file('a', 'step,50\nall done [200]\n')},
             'failed': {'statusFile': status_file('b', 'x\nit failed [404]\n')}, 'progress': {'statusFile': status_file('c', 'Installing the thing,35\n')},
             'no percentage': {'statusFile': status_file('d', 'Working\n')}, 'empty file': {'statusFile': status_file('e', '')},
             'missing key': {}, 'missing file': {'statusFile': os.path.join(tmp, 'gone_valid')}}


def run_pair(data):
    del calls[:]
    new = new_fn(dict(data))
    new_calls = list(calls)
    del calls[:]
    old = old_fn(types.SimpleNamespace(data=dict(data)))
    return (new, new_calls), (old, list(calls))


results = {k: run_pair(v) for k, v in SCENARIOS.items()}
check('the copied status reader answers every scenario exactly like the Cloud API manager method and makes the same calls',
      {k: v[0] == v[1] for k, v in results.items()}, {k: True for k in SCENARIOS})
check('the scenarios cover the finished, failed, progress, empty and error paths (not all the same answer)',
      (len({json.dumps(v[0][0], sort_keys=True) for v in results.values()}), results['finished'][0][1], results['failed'][0][1]), (8, [('rm -f ' + SCENARIOS['finished']['statusFile'])], []))
check('control: an answer that differs would be reported', results['progress'][0] == results['finished'][0], False)

# the view keeps its admin check and passes the request body on
body_ns = {}
view_src = segment(VIEWS, 'statusFunc')
view_ns = {'ACLManager': types.SimpleNamespace(loadedACL=lambda u: {'admin': view_admin[0]}, loadErrorJson=lambda *a: 'denied-response'), 'json': json,
           'HttpResponse': lambda b: json.loads(b), 'fetchStatusFileProgress': lambda data: ('helper', data)}
view_admin = [1]
exec(view_src, view_ns)
req = types.SimpleNamespace(session={'userID': 1}, body=json.dumps({'statusFile': 'x'}))
check('the view hands the decoded request body to the helper for an administrator', view_ns['statusFunc'](req), ('helper', {'statusFile': 'x'}))
view_admin[0] = 0
check('the view still refuses a user who is not an administrator', view_ns['statusFunc'](req), 'denied-response')
view_admin[0] = 1
check('the view still answers a missing session with its error message', view_ns['statusFunc'](types.SimpleNamespace(session={}, body='{}'))['status'], 0)

# the Optimize MySQL page
OLD_PAGE = '''def OptimizeMySQL(self, request = None, userID = None):
    from cloudAPI.cloudManager import CloudManager
    cm = CloudManager()
    result = cm.fetchRam(request)

    data1 = json.loads(result.content)

    data = {}
    data['ramInGB'] = data1.get('ramInGB')
    data['conf'] = data1.get('conf')

    template = 'databases/OptimizeMySQL.html'
    proc = httpProc(request, template, data, 'admin')
    return proc.render()
'''
NEW_PAGE = segment(MANAGER, 'OptimizeMySQL', 'DatabaseManager')
check('the page method is the old one with only the first four lines replaced', NEW_PAGE.split("    data = {}\n")[1].strip() == OLD_PAGE.split("    data = {}\n")[1].strip(), True)

state = {'distro': 'centos', 'ram': 8 * 1024 ** 3 + 1, 'fail': False, 'commands': []}


class PU:
    centos, cent8, ubuntu = 'centos', 'cent8', 'ubuntu'

    @staticmethod
    def decideDistro():
        return state['distro']

    @staticmethod
    def outputExecutioner(c):
        state['commands'].append(c)
        if state['fail']:
            raise RuntimeError('cannot read')
        return 'CONF OF ' + c


def memory():
    if state['fail']:
        raise RuntimeError('no memory reader')
    return types.SimpleNamespace(total=state['ram'])


class Page:
    def __init__(self, request, template, data, permission):
        self.template, self.data, self.permission = template, data, permission

    def render(self):
        return (self.template, self.data, self.permission)


def fetch_ram(self, request):
    pass


def run_page(source, old):
    sys.modules['psutil'] = types.SimpleNamespace(virtual_memory=memory)
    sys.modules['plogical.processUtilities'] = types.SimpleNamespace(ProcessUtilities=PU)
    ns = {'json': json, 'httpProc': Page, 'HttpResponse': lambda b: types.SimpleNamespace(content=b)}
    if old:
        ns_cloud = {'json': json, 'ProcessUtilities': PU, 'HttpResponse': lambda b: types.SimpleNamespace(content=b)}
        exec(OLD_AJAX, ns_cloud)
        exec(OLD_RAM, ns_cloud)

        class FakeCloud:
            ajaxPre = ns_cloud['ajaxPre']
            fetchRam = ns_cloud['fetchRam']

        sys.modules['cloud' + 'API'] = types.ModuleType('cloud' + 'API')
        sys.modules['cloud' + 'API.cloudManager'] = types.SimpleNamespace(CloudManager=FakeCloud)
    exec(source, ns)
    del state['commands'][:]
    result = ns['OptimizeMySQL'](types.SimpleNamespace(), types.SimpleNamespace(), 1)
    return result, list(state['commands'])


try:
    for label, distro, fail in (('CentOS', 'centos', False), ('AlmaLinux 8', 'cent8', False), ('Ubuntu', 'ubuntu', False), ('a failing reader', 'centos', True)):
        state.update(distro=distro, fail=fail)
        new = run_page(NEW_PAGE, False)
        old = run_page(OLD_PAGE, True)
        check('Optimize MySQL gives the same page data and runs the same commands as before on %s' % label, new == old, True)
    state.update(distro='centos', fail=False)
    page, cmds = run_page(NEW_PAGE, False)
    check('on a CentOS family system it reads the Red Hat style config and rounds the memory up to whole GB',
          (page[0], page[1]['ramInGB'], page[1]['conf'], page[2], cmds), ('databases/OptimizeMySQL.html', 9, 'CONF OF sudo cat /etc/my.cnf', 'admin', ['sudo cat /etc/my.cnf']))
    state.update(distro='ubuntu')
    page, cmds = run_page(NEW_PAGE, False)
    check('on Ubuntu it reads the Debian style config', (page[1]['conf'], cmds), ('CONF OF sudo cat /etc/mysql/my.cnf', ['sudo cat /etc/mysql/my.cnf']))
    state.update(fail=True)
    page, cmds = run_page(NEW_PAGE, False)
    check('a failing reader still renders the page with empty values', (page[1], page[0]), ({'ramInGB': None, 'conf': None}, 'databases/OptimizeMySQL.html'))
finally:
    for m in ('psutil', 'plogical.processUtilities', 'cloud' + 'API', 'cloud' + 'API.cloudManager'):
        sys.modules.pop(m, None)
    for name in os.listdir(tmp):
        os.remove(os.path.join(tmp, name))
    os.rmdir(tmp)

for rel in ('emailPremium/views.py', 'databases/databaseManager.py', 'databases/views.py'):
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
