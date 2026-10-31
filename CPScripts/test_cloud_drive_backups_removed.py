"""Tests that the Google Drive backup add-on is removed without touching the free backup pages or the scheduled backups: its nine views and
routes, nine manager methods, template, JavaScript controller, sidebar entry, scheduler runner and ownership helper are gone. The root cron
lines run the scheduler entry point, so the real entry point is run with stand-ins for every period and must call exactly what it called
before in the same order, minus the removed runner. The free views, manager methods, scheduler functions and access helpers are pinned by
hash, the models and the ACL field stay. Needs node for the script syntax check (reported as skipped when it is missing).
Run: python3 CPScripts/test_cloud_drive_backups_removed.py"""
import ast
import hashlib
import os
import re
import shutil
import subprocess
import sys

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


G = 'g' + 'Drive'
REMOVED = [G, G + 'Setup', 'fetch' + G + 'Sites', 'addSite' + G, 'deleteAccount' + G, 'changeAccountFrequency' + G, 'changeFileRetention', 'deleteSite' + G, 'fetchDriveLogs']
RUNNER = 'runGoogle' + 'DriveBackups'
OWNER = 'check' + 'GDriveOwnership'
VIEWS, URLS, MANAGER, SCHED, ACL = read('backup/views.py'), read('backup/urls.py'), read('backup/backupManager.py'), read('plogical/IncScheduler.py'), read('plogical/acl.py')
JS, INDEX = read('backup/static/backup/backup.js'), read('baseTemplate/templates/baseTemplate/index.html')


def funcs(src, scope=None):
    tree = ast.parse(src)
    body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == scope).body if scope else tree.body
    return {n.name: n for n in body if isinstance(n, ast.FunctionDef)}


def digest(src, node):
    return hashlib.sha256(ast.get_source_segment(src, node).encode()).hexdigest()[:16]


views, manager, sched, acl = funcs(VIEWS), funcs(MANAGER, 'BackupManager'), funcs(SCHED, 'IncScheduler'), funcs(ACL, 'ACLManager')
check('the nine views are gone', sorted(set(REMOVED) & set(views)), [])
check('the nine manager methods are gone', sorted(set(REMOVED) & set(manager)), [])
check('the scheduler runner and the ownership helper are gone', (RUNNER in sched, OWNER in acl), (False, False))
PIN_V = {'loadBackupHome': 'dd4e6de98548df15', 'backupSite': 'a42c1cba7c3a8b9a', 'restoreSite': '71d5f5f7824dd024', 'submitBackupCreation': 'a29c54bc105c7a86', 'backupDestinations': '797caf2c7412aebb', 'scheduleBackup': 'e3363556bd8bb3b2'}
check('six free backup views are exactly as they were', {n: digest(VIEWS, views[n]) if n in views else None for n in PIN_V}, PIN_V)
PIN_M = {'loadBackupHome': '184afbb4d2a813f0', 'backupSite': '58baf9f63a5b738b', 'restoreSite': 'e4d7021918debbf0', 'submitRestore': 'd7cf920244b33809', 'deleteBackup': '075fd2c4142518f4', 'backupDestinations': '4b26b38c9ef7ab02'}
check('six free manager methods are exactly as they were', {n: digest(MANAGER, manager[n]) if n in manager else None for n in PIN_M}, PIN_M)
PIN_S = {'startBackup': 'dd81af873ff7e687', 'git': '2b979f40b369c6eb', 'checkDiskUsage': '3bb45d8c960658bc', 'runAWSBackups': '4ea79d4095555020', 'CheckHostName': 'ebdb73362bf6f214', 'RemoteBackup': '1d488b4fc1326516'}
check('seven scheduler functions next to it are exactly as they were', {n: digest(SCHED, sched[n]) if n in sched else None for n in PIN_S}, PIN_S)
PIN_A = {'checkOwnership': '9e9360cd2f92abcb', 'checkUserOwnerShip': '0219b10f0d7410f8', 'loadedACL': '9d01fdde29fea284', 'currentContextPermission': '68b75d36517506e5'}
check('four access helpers are exactly as they were (the ACL field stays)', {n: digest(ACL, acl[n]) if n in acl else None for n in PIN_A}, PIN_A)
check('the ACL still carries the Google Drive permission field and the models stay', ('googleDrive' + 'Backups' in ACL, all(('class ' + c) in read('websiteFunctions/models.py') for c in ('GDrive', 'GDriveSites', 'GDriveJobLogs'))), (True, True))
check('the removed models are no longer named by the three modules', [(rel, n) for rel, src in (('backup/backupManager.py', MANAGER), ('plogical/IncScheduler.py', SCHED)) for n in ('GDrive', 'GDriveSites', 'GDriveJobLogs') if re.search(r'\b%s\b' % n, src)], [])

# the entry point the cron lines run
main_node = next(n for n in ast.parse(SCHED).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
MAIN = ast.get_source_segment(SCHED, main_node)
check('the entry point no longer names the runner', RUNNER in MAIN, False)


def run_main(code, period, with_runner=False, runner_fails=False):
    calls = []

    def rec(name):
        def f(*a, **k):
            calls.append(name)
        return staticmethod(f)

    def runner(*a, **k):
        calls.append('runner')
        if runner_fails:
            raise FileNotFoundError('machine address file')

    class Sched:
        def __init__(self, function, extra):
            calls.append('thread:' + function + ':' + extra['freq'])

        def start(self):
            calls.append('thread.start')

        def join(self):
            calls.append('thread.join')

    for n in ('CalculateAndUpdateDiskUsage', 'WPUpdates', 'FixMailSSL', 'startBackup', 'git', 'checkDiskUsage', 'startNormalBackups', 'runAWSBackups', 'CheckHostName', 'RemoteBackup', 'v2Backups', 'forceRunAWSBackup'):
        setattr(Sched, n, rec(n))
    if with_runner:
        setattr(Sched, RUNNER, staticmethod(runner))
    import argparse
    ns = {'argparse': argparse, 'IncScheduler': Sched}
    exec(code, ns)
    saved = sys.argv
    sys.argv = ['IncScheduler.py', period]
    try:
        ns['main']()
        return calls
    except BaseException as exc:
        return calls + ['RAISED ' + type(exc).__name__]
    finally:
        sys.argv = saved


DAILY = ['CalculateAndUpdateDiskUsage', 'WPUpdates', 'thread:startBackup:Daily', 'thread.start', 'startBackup', 'git', 'checkDiskUsage', 'startNormalBackups', 'runAWSBackups', 'CheckHostName', 'thread.join']
check('the entry point for a daily run calls exactly the free steps in the same order', run_main(MAIN, 'Daily'), DAILY)
check('the entry point for a weekly run adds only the mail certificate fix before the thread', run_main(MAIN, 'Weekly'),
      ['CalculateAndUpdateDiskUsage', 'WPUpdates', 'FixMailSSL', 'thread:startBackup:Weekly', 'thread.start', 'startBackup', 'git', 'checkDiskUsage', 'startNormalBackups', 'runAWSBackups', 'CheckHostName', 'thread.join'])
check('the entry point for the short periods runs the remote backup first and nothing from the removed runner', [c for c in run_main(MAIN, '1 Hour') if c != 'v2Backups'], ['RemoteBackup'])
check('the entry point for the disk usage refresh is unchanged', run_main(MAIN, 'UpdateDiskUsageForce'), ['CalculateAndUpdateDiskUsage'])
anchor = '    IncScheduler.startBackup(args.function)' + chr(10)
assert MAIN.count(anchor) == 1
OLD_MAIN = MAIN.replace(anchor, anchor + chr(10) + '    IncScheduler.' + RUNNER + '(args.function)' + chr(10))
check('control: the old entry point called the runner right after the free backup step', run_main(OLD_MAIN, 'Daily', with_runner=True), DAILY[:5] + ['runner'] + DAILY[5:])
check('control: the old entry point stopped before the other steps when the runner failed', run_main(OLD_MAIN, 'Daily', with_runner=True, runner_fails=True), DAILY[:5] + ['runner', 'RAISED FileNotFoundError'])


# routes and the rest of the tree
def routes(source):
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('path', 're_path'):
            view = n.args[1]
            out.append((view.attr if isinstance(view, ast.Attribute) else None, next((k.value.value for k in n.keywords if k.arg == 'name'), None)))
    return out


table = routes(URLS)
check('no route points at a view that does not exist', [r for r in table if r[0] not in views], [])
check('no route of the removed views is left and the free ones are kept', ([r for r in table if r[0] in REMOVED or r[1] in REMOVED], [n for n in ('loadBackupHome', 'backupSite', 'restoreSite', 'backupDestinations', 'scheduleBackup', 'remoteBackups', 'fetchNormalLogs') if n not in {r[1] for r in table}]), ([], []))
bad = URLS.replace("    re_path(r'^backupSite$'", "    re_path(r'^x$', views.%s, name='x'),\n    re_path(r'^backupSite$'" % G)
check('control: a route put back is reported as dangling', [r[0] for r in routes(bad) if r[0] not in views], [G])
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
defined = set()
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f == 'urls.py':
            defined |= {r[1] for r in routes(open(os.path.join(base, f), encoding='utf-8').read()) if r[1]}
leftovers, refs, templates = [], [], 0
TOKENS = ['/backup/' + n for n in REMOVED] + [RUNNER, OWNER, 'backup/google' + 'Drive.html']
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        rel = os.path.relpath(os.path.join(base, f), ROOT).replace(os.sep, '/')
        if f.endswith('.html') and '.bak' not in f:
            templates += 1
            for line in open(os.path.join(base, f), encoding='utf-8', errors='replace').read().split('\n'):
                if not line.lstrip().startswith('{#'):
                    leftovers += [(rel, m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) in REMOVED]
        if f.endswith(('.py', '.html', '.js')) and '.bak' not in f and not f.startswith('test_') and not f.endswith('.min.js'):
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            refs += [(rel, t) for t in TOKENS if t in text]
check('the removed route names exist nowhere', sorted(set(REMOVED) & defined), [])
check('no template reverses a removed route', leftovers, [])
check('the templates were scanned across the tree', templates > 100, True)
check('nothing in the tree names the removed endpoints, runner, helper or template', refs, [])
check('the template is gone', os.path.exists(os.path.join(ROOT, 'backup/templates/backup/google' + 'Drive.html')), False)
check('the sidebar has no entry and keeps its neighbours', (("url '" + G + "'") not in INDEX, "url 'scheduleBackup'" in INDEX, "url 'remoteBackups'" in INDEX), (True, True, True))
check('the site deletion still removes its rows from the removed add-on table (kept data hygiene)', 'GDriveSites.objects.filter(domain=websiteName).delete()' in read('websiteFunctions/website.py'), True)

controllers = re.findall(r"^app\.controller\('([A-Za-z]+)'", JS, flags=re.M)
check('the controller is gone and the free ones are kept', ([c for c in controllers if c == 'google' + 'Drive'], [c for c in ('backupWebsiteControl', 'restoreWebsiteControl', 'remoteBackupControl', 'backupLogsScheduled', 'backupDestinations', 'scheduleBackup') if c not in controllers]), ([], []))
node = shutil.which('node')
if node:
    check('backup.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'backup/static/backup/backup.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

for rel in ('backup/views.py', 'backup/urls.py', 'backup/backupManager.py', 'plogical/IncScheduler.py', 'plogical/acl.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar and has no carriage returns' % rel, (parsed, b'\r' in open(os.path.join(ROOT, rel), 'rb').read()), (True, False))

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
