"""Tests that the hosted backup plan add-on is removed without touching the free backup pages: its six views and routes, six manager
methods, three templates, two JavaScript controllers, sidebar entry, restore worker with its dispatch, folder listing helper with its
command line branch, the failure notice at the end of the scheduled backup loop, the upsell paragraphs of two free pages and the
dashboard banner with the flag that rendered it are gone. The flag was set on every page render by a database query, so the page renderer
is run with stand-ins: it must not query or import the removed model and must still set every other value. The free views and manager
methods are pinned by hash. Names are built here so this file does not name the add-on. Needs node for the script syntax check
(reported as skipped when it is missing).
Run: python3 CPScripts/test_hosted_backup_plans_removed.py"""
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
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


OC = 'One' + 'Click'
REMOVED = [OC + 'Backups', 'ManageOCBackups', 'RestoreOCBackups', 'fetchOCSites', 'StartOCRestore', 'DeployAccount']
VIEWS, URLS, MANAGER = read('backup/views.py'), read('backup/urls.py'), read('backup/backupManager.py')
UTILS, INSTALLER, SCHED = read('plogical/backupUtilities.py'), read('plogical/applicationInstaller.py'), read('plogical/IncScheduler.py')
JS, INDEX, HTTPPROC = read('backup/static/backup/backup.js'), read('baseTemplate/templates/baseTemplate/index.html'), read('plogical/httpProc.py')


def funcs(src, scope=None):
    tree = ast.parse(src)
    body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == scope).body if scope else tree.body
    return {n.name: n for n in body if isinstance(n, ast.FunctionDef)}


def digest(src, node):
    return hashlib.sha256(ast.get_source_segment(src, node).encode()).hexdigest()[:16]


views, manager = funcs(VIEWS), funcs(MANAGER, 'BackupManager')
check('the six views are gone', sorted(set(REMOVED) & set(views)), [])
check('the six manager methods are gone', sorted(set(REMOVED) & set(manager)), [])
PIN_V = {'loadBackupHome': 'dd4e6de98548df15', 'backupSite': 'a42c1cba7c3a8b9a', 'restoreSite': '71d5f5f7824dd024', 'submitBackupCreation': 'a29c54bc105c7a86',
         'backupDestinations': '797caf2c7412aebb', 'scheduleBackup': 'e3363556bd8bb3b2', 'remoteBackups': 'eb90cae9b091e932', 'fetchNormalLogs': '7daaa65886df5547'}
check('eight free backup views are exactly as they were', {n: digest(VIEWS, views[n]) if n in views else None for n in PIN_V}, PIN_V)
PIN_M = {'loadBackupHome': '184afbb4d2a813f0', 'backupSite': '58baf9f63a5b738b', 'restoreSite': 'e4d7021918debbf0', 'submitRestore': 'd7cf920244b33809',
         'deleteBackup': '075fd2c4142518f4', 'backupDestinations': '4b26b38c9ef7ab02', 'submitDestinationCreation': '594e9c385585f175', 'scheduleBackup': '0ce5dc8f8a1e3191'}
check('eight free manager methods are exactly as they were', {n: digest(MANAGER, manager[n]) if n in manager else None for n in PIN_M}, PIN_M)


def routes(source):
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('path', 're_path'):
            view = n.args[1]
            out.append((view.attr if isinstance(view, ast.Attribute) else None, next((k.value.value for k in n.keywords if k.arg == 'name'), None)))
    return out


table = routes(URLS)
check('no route points at a view that does not exist', [r for r in table if r[0] not in views], [])
check('no route of the removed views is left', [r for r in table if r[0] in REMOVED or r[1] in REMOVED], [])
check('the free routes are kept', [n for n in ('loadBackupHome', 'backupSite', 'restoreSite', 'backupDestinations', 'scheduleBackup', 'remoteBackups', 'fetchNormalLogs') if n not in {r[1] for r in table}], [])
bad = URLS.replace("    re_path(r'^backupSite$'", "    re_path(r'^x$', views.%s, name='x'),\n    re_path(r'^backupSite$'" % REMOVED[0])
check('control: a route put back is reported as dangling', [r[0] for r in routes(bad) if r[0] not in views], [REMOVED[0]])

# the page renderer: no query and no flag any more, everything else as before
cls_node = next(n for n in ast.parse(HTTPPROC).body if isinstance(n, ast.ClassDef) and n.name == 'httpProc')
CLASS_SRC = ast.get_source_segment(HTTPPROC, cls_node)


def render_with(class_src):
    calls = []
    imported = []

    class Model:
        class objects:
            @staticmethod
            def filter(**kw):
                calls.append('query')
                return types.SimpleNamespace(count=lambda: 0)

    def module(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        return m

    class ModelsModule(types.ModuleType):
        def __getattr__(self, item):
            if item == OC + 'Backups':
                imported.append(item)
                return Model
            raise AttributeError(item)

    admin_obj = types.SimpleNamespace(firstName='A', lastName='B', config=json.dumps({'onboarding': 1}))
    mods = {'loginSystem': module('loginSystem'), 'loginSystem.models': module('loginSystem.models', Administrator=types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda **kw: admin_obj))),
            'plogical': module('plogical'), 'plogical.acl': module('plogical.acl', ACLManager=types.SimpleNamespace(loadedACL=lambda u: {'admin': 1, 'createBackup': 1}, GetServiceStatus=lambda d: None)),
            'IncBackups': module('IncBackups'), 'IncBackups.models': ModelsModule('IncBackups.models'),
            'baseTemplate': module('baseTemplate'), 'baseTemplate.models': module('baseTemplate.models', CyberPanelCosmetic=types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda pk: 'cosmetic')))}
    saved = {k: sys.modules.get(k) for k in mods}
    sys.modules.update(mods)
    try:
        ns = {'json': json, 'render': lambda request, template, data: ('rendered', template, dict(data)), 'HttpResponse': lambda x: x,
              'ProcessUtilities': types.SimpleNamespace(decideServer=lambda: 'ols', ent='ent'),
              'open': lambda path: types.SimpleNamespace(read=lambda: '192.0.2.1' + chr(10))}
        exec(class_src, ns)
        page = ns['httpProc'](types.SimpleNamespace(session={'userID': 1}), 'x.html', {'own': 1}, None)
        out = page.render()
        return out, calls, imported
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


out, calls, imported = render_with(CLASS_SRC)
check('the page renderer renders the template with the caller data and the usual values', (out[0], out[1], sorted(out[2])),
      ('rendered', 'x.html', sorted(['own', 'onboarding', 'ipAddress', 'fullName', 'cosmetic', 'admin', 'createBackup'])))
check('the page renderer runs no query and imports nothing of the removed model', (calls, imported), ([], []))
check('the page renderer sets no banner flag', 'backupDisplay' in out[2], False)
flag = ("                from IncBackups.models import " + OC + "Backups" + chr(10) + "                if " + OC + "Backups.objects.filter(owner=admin).count() == 0:" + chr(10) +
        "                    self.data['backupDisplay'] = 1" + chr(10) + "                else:" + chr(10) + "                    self.data['backupDisplay'] = 0" + chr(10) + chr(10))
anchor = "                ### Onboarding checks" + chr(10)
assert CLASS_SRC.count(anchor) == 1
old_out, old_calls, old_imported = render_with(CLASS_SRC.replace(anchor, flag + anchor))
check('control: with the old flag block put back the renderer queries on every page and sets the banner flag', (old_calls, old_out[2].get('backupDisplay')), (['query'], 1))
check('control: the old renderer sets exactly one more value than the new one', sorted(set(old_out[2]) - set(out[2])), ['backupDisplay'])

# templates and sidebar
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
defined = set()
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f == 'urls.py':
            defined |= {r[1] for r in routes(open(os.path.join(base, f), encoding='utf-8').read()) if r[1]}
check('the removed route names exist nowhere', sorted(set(REMOVED) & defined), [])
leftovers, templates, refs = [], 0, []
HARD = ['/backup/' + n for n in REMOVED]
ALLOWED = {'websiteFunctions/static/websiteFunctions/websiteFunctions.js', 'websiteFunctions/templates/websiteFunctions/WPsiteHome.html'}
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        rel = os.path.relpath(os.path.join(base, f), ROOT).replace(os.sep, '/')
        if f.endswith('.html') and '.bak' not in f:
            templates += 1
            for line in open(os.path.join(base, f), encoding='utf-8', errors='replace').read().split('\n'):
                if not line.lstrip().startswith('{#'):
                    leftovers += [(rel, m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) in REMOVED]
        if f.endswith(('.py', '.html', '.js')) and '.bak' not in f and not f.startswith('test_') and not f.endswith('.min.js') and not rel.startswith('cloudAPI'):
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            refs += [(rel, t) for t in HARD + ['backup/oneClick' + 'Backups.html', 'restoreOC' + 'Backups.html', 'backupDisplay'] if t in text and rel not in ALLOWED]
check('no template reverses a removed route', leftovers, [])
check('the templates were scanned across the tree', templates > 100, True)
check('nothing else links to the removed addresses or names the removed templates or the banner flag (two WordPress files are removed with their own add-on)', refs, [])
check('the three templates are gone', [t for t in ('oneClick' + 'Backups.html', OC + 'BackupSchedule.html', 'restoreOC' + 'Backups.html') if os.path.exists(os.path.join(ROOT, 'backup/templates/backup/' + t))], [])
check('the sidebar has no entry and no banner and keeps the free backup entries', (("url '" + REMOVED[0] + "'") not in INDEX, 'backupDisplay' not in INDEX, 'not secured with automatic backups' not in INDEX, "url 'backupSite'" in INDEX, "url 'loadBackupHome'" in INDEX), (True, True, True, True, True))
for t, ctrl in (('backup.html', 'backupWebsiteControl'), ('backupDestinations.html', 'backupDestinations')):
    text = read('backup/templates/backup/' + t)
    check('%s lost the upsell paragraph and kept its controller' % t, ('secure servers in 60 seconds' in text, ('ng-controller="%s"' % ctrl) in text), (False, True))
sample = "<a href=\"{% url '" + REMOVED[0] + "' %}\">x</a>"
check('control: the template check would report a left-over reverse', [m.group(1) for m in URL_TAG.finditer(sample) if m.group(1) in REMOVED], [REMOVED[0]])

# script
controllers = re.findall(r"^app\.controller\('([A-Za-z]+)'", JS, flags=re.M)
check('both controllers are gone and the six free ones are kept', ([c for c in controllers if c in ('backupPlanNow' + OC, OC + 'restoreWebsiteControl')],
                                                                    [c for c in ('backupWebsiteControl', 'restoreWebsiteControl', 'remoteBackupControl', 'backupLogsScheduled', 'backupDestinations', 'scheduleBackup') if c not in controllers]), ([], []))
node = shutil.which('node')
if node:
    check('backup.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'backup/static/backup/backup.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

# the scheduled loop, the helper, the worker
sched = funcs(SCHED, 'IncScheduler')
src = ast.get_source_segment(SCHED, sched['startNormalBackups'])
check('the scheduled backup loop no longer sends a failure notice and ends at its own last statement', ([w for w in ('Billing', OC, 'platform.') if w in src], src.rstrip().endswith('backupjob.save()')), ([], True))
check('the scheduled backup loop is as expected (pinned)', digest(SCHED, sched['startNormalBackups']), '345ed7de2358dbb5')
check('the folder listing helper and its command line branch are gone', ('FetchOCBackupsFolders' in UTILS, 'FetchOCBackupsFolders' in UTILS), (False, False))
inst = funcs(INSTALLER, 'ApplicationInstaller')
check('the restore worker and its dispatch are gone and the neighbours kept', ('StartOCRestore' in inst, 'StartOCRestore' in INSTALLER, 'RestoreWPbackupNow' in inst, "self.installApp == 'UpgradeCP'" in INSTALLER), (False, False, True, True))

for rel in ('plogical/httpProc.py', 'backup/views.py', 'backup/urls.py', 'backup/backupManager.py', 'plogical/backupUtilities.py', 'plogical/applicationInstaller.py', 'plogical/IncScheduler.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar and has no carriage returns' % rel, (parsed, b'\r' in open(os.path.join(ROOT, rel), 'rb').read()), (True, False))

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
