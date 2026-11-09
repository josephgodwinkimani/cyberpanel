"""Tests that the paid Apache backend page and its choice on the site pages are removed without touching the free PHP and vhost helpers
that share the Apache folder: the page view and template, the two page routes and the two switch routes with their views, the config
saving method, the script controller and the choice on Create Website and Create Child Domain (and the two links on the site pages) are
gone, nothing reverses or calls them, and a request can no longer ask the create handlers for an Apache backend: the real handlers are
run with stand-ins and a crafted request that asks for one creates the site with the backend flag at 0 (with the old form as a control),
while an alias of a site that already has an Apache configuration still follows it. The free helpers and pages are byte for byte what they
were (pinned by hash where no other change touches them). The Cloud API switch methods stay until the Cloud API is removed.
Needs node for the script syntax check (reported as skipped when it is missing).
Run: python3 CPScripts/test_apache_backend_manager_removed.py"""
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
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


def fp(src):
    return hashlib.sha256(src.encode()).hexdigest()[:16]


WEBSITE, VIEWS, URLS, JS = read('websiteFunctions/website.py'), read('websiteFunctions/views.py'), read('websiteFunctions/urls.py'), read('websiteFunctions/static/websiteFunctions/websiteFunctions.js')
T = 'websiteFunctions/templates/websiteFunctions/'
ROUTES = ['ApacheManager', 'getSwitchStatus', 'switchServer', 'saveApacheConfigsToFile']

# manager, views and routes
mtree = ast.parse(WEBSITE)
manager = next(n for n in mtree.body if isinstance(n, ast.ClassDef) and n.name == 'WebsiteManager')
methods = {n.name: n for n in manager.body if isinstance(n, ast.FunctionDef)}
check('the page method and the config saving method are gone', sorted({'ApacheManager', 'saveApacheConfigsToFile'} & set(methods)), [])
check('the switch methods stay for the Cloud API until it is removed', sorted({'getSwitchStatus', 'switchServer'} & set(methods)), ['getSwitchStatus', 'switchServer'])
MPIN = {'tuneSettings': None, 'wordpressInstall': 'f2624f59552d444c', 'installWordpress': 'f592559693c97c85', 'modifyWebsite': 'f98ea286e109201c', 'deleteWebsite': '1da24203f6703c00',
        'siteState': '45f14b6a44524f93', 'listWebsites': '0d7686a9cc11d6dd', 'listChildDomains': 'c6f772ec5dcc4f48', 'listCron': 'f9a2f508142358ae',
        'domainAlias': 'ec4ccd935ba44e34', 'changePHP': '7b51bb3ca9dddb72', 'saveSSL': 'a2ba409814a65ea6', 'sshAccess': '04191e026039a761', 'setupStaging': 'ce60260109e3803f',
        'getSwitchStatus': None, 'switchServer': None}
MPIN = {k: v for k, v in MPIN.items() if v}
check('the free manager methods untouched by any other change are exactly as they were',
      {n: fp(ast.get_source_segment(WEBSITE, methods[n])) if n in methods else None for n in MPIN}, MPIN)
vtree = ast.parse(VIEWS)
vfuncs = {n.name: n for n in vtree.body if isinstance(n, ast.FunctionDef)}
check('the four views are gone', sorted(set(ROUTES) & set(vfuncs)), [])
VPIN = {'wordpressInstall': '5480ac33d3d1925e', 'installWordpress': '3c797bca3788b316', 'modifyWebsite': '3e54791374354257', 'deleteWebsite': '69e34877eff62354',
        'siteState': '203d8b9faa4e3627', 'listWebsites': '754542a257c72559', 'changePHP': '44e7493f004f1aa7', 'saveSSL': 'ae0d3af68b2bc2d6', 'sshAccess': '9a7d3c926075e6c5',
        'tuneSettings': '648bf26d6593952a', 'loadWebsitesHome': '78448ca0757e6eff', 'createWebsite': 'a87a42b128ee6202'}
check('the free views are exactly as they were', {n: fp(ast.get_source_segment(VIEWS, vfuncs[n])) if n in vfuncs else None for n in VPIN}, VPIN)


def routes(source):
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('path', 're_path'):
            view = n.args[1]
            out.append((n.args[0].value, view.attr if isinstance(view, ast.Attribute) else None, next((k.value.value for k in n.keywords if k.arg == 'name'), None)))
    return out


table = routes(URLS)
check('none of the four routes is left and no route points at a missing view', ([r for r in table if r[2] in ROUTES], [r for r in table if r[1] not in vfuncs]), ([], []))
check('the neighbouring free routes are kept and the catch alls stay last', ([n for n in ('statusFunc', 'tuneSettings', 'addSSHKey', 'deleteSSHKey') if n in [r[2] for r in table]], [r[2] for r in table][-2:]),
      (['statusFunc', 'tuneSettings', 'addSSHKey', 'deleteSSHKey'], ['launchChild', 'domain']))
check('the Apache header comment is gone', '# Apache Manager' in URLS, False)

# templates and tree
check('the page template is gone', os.path.exists(os.path.join(ROOT, T + 'ApacheManager.html')), False)
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
SKIP = ('.git', 'node_modules', 'static', 'public', 'locale')
tag_left, py_left, name_left, templates = [], [], [], 0
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if '.bak' in f or f.startswith('test_') or f.endswith('.min.js') or not f.endswith(('.py', '.html', '.js')):
            continue
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
        if f.endswith('.html'):
            templates += 1
            for line in text.split('\n'):
                if not line.lstrip().startswith('{#'):
                    tag_left += [(rel, m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) in ROUTES]
        if f.endswith('.py') and re.search(r"reverse\(\s*['\"](ApacheManager|getSwitchStatus|switchServer|saveApacheConfigsToFile)['\"]", text):
            py_left.append(rel)
        if f.endswith('.py') and re.search(r'\bwm\.(ApacheManager|saveApacheConfigsToFile)\b', text):
            py_left.append(rel)
        if 'ApacheManager.html' in text:
            name_left.append(rel)
check('no template reverses a removed route outside comments', tag_left, [])
check('the templates were scanned across the tree', templates > 100, True)
check('no code reverses a removed route or calls a removed method', py_left, [])
check('no code names the removed template', name_left, [])
check('control: a reverse of a removed route would be reported', [m.group(1) for m in URL_TAG.finditer("<a href=\"{% url 'ApacheManager' domain=domain %}\">")], ['ApacheManager'])
for rel, label in (('createWebsite.html', 'Create Website'), ('createDomain.html', 'Create Child Domain'), ('website.html', 'the site page'), ('launchChild.html', 'the child site page')):
    t = read(T + rel)
    check('%s offers no Apache backend choice or Apache page link' % label, [w for w in ('ng-model="apacheBackend"', 'OpenLiteSpeed + Apache', 'go.cyberpanel.net/ApacheRev', 'Apache Manager') if w in t], [])
site = read(T + 'website.html')
child = read(T + 'launchChild.html')
check('the other configuration boxes of the site pages are kept', ('Edit vHost Main Configurations' in site, 'Add Rewrite Rules' in site, 'Edit vHost Main Configurations' in child, 'Add Rewrite Rules' in child), (True, True, True, True))
check('the create pages keep their other options', ('ng-model="domainNameCreate"' in read(T + 'createWebsite.html'), 'masterDomain' in read(T + 'createDomain.html')), (True, True))

# scripts
found = re.findall(r"app\.controller\('([A-Za-z0-9_]+)'", JS)
check('the page controller is gone and the neighbours are kept', ('ApacheManager' in found, 'createDockerPackage' in found, 'manageGIT' in found, 'createWebsite' in found), (False, True, True, True))
left = JS
if "app.controller('createWordpress'" in left:
    a = left.index("app.controller('createWordpress'")
    b = left.index("app.controller('", a + 10)
    left = left[:a] + left[b:]
check('the create controllers no longer read or send a backend choice', ('apacheBackend' in left, 'getSwitchStatus' in JS, 'saveApacheConfigsToFile' in JS), (False, False, False))
node = shutil.which('node')
if node:
    check('websiteFunctions.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'websiteFunctions/static/websiteFunctions/websiteFunctions.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

# the create handlers: a crafted request cannot ask for the backend
src = WEBSITE
cls = manager


def method(name):
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    raw = ast.get_source_segment(src, node)
    return raw.replace('\n' + ' ' * node.col_offset, '\n')


try:
    import pwd  # noqa: F401
except ImportError:
    sys.modules['pwd'] = types.ModuleType('pwd')

COMMANDS = []
tmp = tempfile.mkdtemp()


def build(name, source=None, apache_dir=tmp):
    class Admin:
        class objects:
            @staticmethod
            def get(**kw):
                return types.SimpleNamespace(userName='admin', pk=1, defaultSite=1)

    class Sites:
        class objects:
            @staticmethod
            def get(**kw):
                if 'externalApp' in kw:
                    raise RuntimeError('no such site')
                return types.SimpleNamespace(domain='a.example', phpSelection='PHP 7.4', externalApp='aexam1234', adminEmail='a@example.invalid', defaultSite=1)

    acl = types.SimpleNamespace(
        loadedACL=lambda u: {'admin': 1}, currentContextPermission=lambda a, p: 1, checkOwnership=lambda d, ad, c: 1,
        loadErrorJson=lambda *a: {'status': 0, 'errorMessage': 'denied'}, checkOwnerProtection=lambda *a: 1, CheckDomainBlackList=lambda d: 1,
        GetServerIP=lambda: '192.0.2.1')
    pu = types.SimpleNamespace(decideServer=lambda: 'ols', ent='ent', OLS='ols', popenExecutioner=lambda c: COMMANDS.append(c))
    vhu = types.SimpleNamespace(cyberPanel='/usr/local/CyberCP')
    ns = {'json': json, 'os': os, 're': re, 'time': types.SimpleNamespace(sleep=lambda s: None), 'HttpResponse': lambda b: json.loads(b), 'ACLManager': acl,
          'Administrator': Admin, 'Websites': Sites, 'ProcessUtilities': pu, 'virtualHostUtilities': vhu, 'randint': lambda a, b: 1234,
          'validators': types.SimpleNamespace(domain=lambda d: True, email=lambda e: True), 'ApacheVhost': types.SimpleNamespace(configBasePath=apache_dir + '/'),
          'mailUtilities': types.SimpleNamespace(checkHome=lambda: None)}
    exec(source or method(name), ns)
    return lambda *a, **k: ns[name](types.SimpleNamespace(), *a, **k)


def run(fn, *a):
    del COMMANDS[:]
    try:
        result = fn(*a)
    except BaseException as exc:
        result = ('raised', type(exc).__name__, str(exc))
    return result, list(COMMANDS)


SITE = {'domainName': 'site.example', 'adminEmail': 'a@example.invalid', 'phpSelection': 'PHP 7.4', 'package': 'Default', 'websiteOwner': 'Admin', 'openBasedir': 1, 'apacheBackend': 1}
result, cmds = run(build('submitWebsiteCreation'), 1, dict(SITE))
check('Create Website with a crafted request for an Apache backend runs one create command with the backend flag at 0', (len(cmds), ' --apache 0 ' in cmds[0] if cmds else None, ' --apache 1' in cmds[0] if cmds else None), (1, True, False))
plain = dict(SITE)
del plain['apacheBackend']
result, cmds = run(build('submitWebsiteCreation'), 1, plain)
check('Create Website without the field still runs the same command with the flag at 0', (len(cmds), ' --apache 0 ' in cmds[0] if cmds else None), (1, True))
OLD = method('submitWebsiteCreation')
FLAT = '\n        apacheBackend = "0"\n'
if OLD.count(FLAT) == 1:
    OLD = OLD.replace(FLAT, '\n        try:\n            apacheBackend = str(data[\'apacheBackend\'])\n        except:\n            apacheBackend = "0"\n', 1)
result, cmds = run(build('submitWebsiteCreation', source=OLD), 1, dict(SITE))
check('control: the old form follows the request and runs the command with the flag at 1', (len(cmds), ' --apache 1 ' in cmds[0] if cmds else None), (1, True))

CHILD = {'domainName': 'child.example', 'masterDomain': 'a.example', 'phpSelection': 'PHP 7.4', 'path': '', 'openBasedir': 1, 'apacheBackend': 1}
result, cmds = run(build('submitDomainCreation'), 1, dict(CHILD))
check('Create Child Domain with a crafted request for an Apache backend runs one create command with the backend flag at 0', (len(cmds), ' --apache 0 ' in cmds[0] if cmds else None), (1, True))
OLDC = method('submitDomainCreation').replace("        ### the backend choice of the request is not used, only an alias of a site that already has one follows it\n        data['apacheBackend'] = 0\n\n", '', 1)
check('control: the guard line is what the patch added', OLDC != method('submitDomainCreation'), True)
result, cmds = run(build('submitDomainCreation', source=OLDC), 1, dict(CHILD))
check('control: the old form follows the request and runs the command with the flag at 1', (len(cmds), ' --apache 1 ' in cmds[0] if cmds else None), (1, True))
ALIAS = {'domainName': 'alias.example', 'masterDomain': 'a.example', 'path': '', 'openBasedir': 1, 'alias': 1}
result, cmds = run(build('submitDomainCreation'), 1, dict(ALIAS))
check('an alias of a site without an Apache configuration is created with the flag at 0', (len(cmds), ' --apache 0 ' in cmds[0] if cmds else None), (1, True))
open(os.path.join(tmp, 'a.example.conf'), 'w').close()
result, cmds = run(build('submitDomainCreation'), 1, dict(ALIAS))
check('an alias of a site that already has an Apache configuration still follows it with the flag at 1', (len(cmds), ' --apache 1 ' in cmds[0] if cmds else None), (1, True))
result, cmds = run(build('submitDomainCreation'), 1, dict(CHILD))
check('a child domain of such a site is still created with the flag at 0 (the request cannot turn it on)', (len(cmds), ' --apache 0 ' in cmds[0] if cmds else None), (1, True))
shutil.rmtree(tmp)

# the free Apache helpers stay
check('the folder with the free PHP and vhost helpers stays', sorted(os.listdir(os.path.join(ROOT, 'ApachController'))), ['ApacheController.py', 'ApacheVhosts.py', 'BackupUtil.py', '__init__.py', 'backup.sh', 'phpApache.xml'])
helpers = read('ApachController/ApacheVhosts.py')
check('the helpers other code imports are still defined', [n for n in ('whichPHPExists', 'DecideFPMServiceName', 'configBasePath', 'changePHP', 'DecidePHPPathforManager', 'DeleteApacheVhost') if n not in helpers], [])

for rel in ('websiteFunctions/website.py', 'websiteFunctions/views.py', 'websiteFunctions/urls.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
for rel in ('websiteFunctions/website.py', 'websiteFunctions/views.py', 'websiteFunctions/urls.py', 'websiteFunctions/static/websiteFunctions/websiteFunctions.js',
            T + 'createWebsite.html', T + 'createDomain.html', T + 'website.html', T + 'launchChild.html'):
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
