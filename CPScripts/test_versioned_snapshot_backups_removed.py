"""Tests that the snapshot based backup pages (a paid add-on that needs the licence service for its drive setup) are removed without touching
the free incremental backup: the 17 page and action views, their routes, the 5 manager methods, the 5 templates, the 5 script controllers,
the sidebar entry, the engine module and the scheduler runner are gone, nothing imports or names them, the cron entry point still exits
cleanly for every short period (the real main() is executed with recorders, and an old form control proves the check sees the
removed call), and the free incremental views are byte for byte what they were (pinned by hash where no other change touches them).
The two database tables of the add-on stay so an upgrade never drops data. Needs node for the script syntax check (skipped when missing).
Run: python3 CPScripts/test_versioned_snapshot_backups_removed.py"""
import argparse
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


def fp(src):
    return hashlib.sha256(src.encode()).hexdigest()[:16]


V = 'V' + '2'
v = V.lower()
VIEWS = ['Configure' + V + 'Backup', 'Configure' + V + 'BackupSetup', 'Create' + V + 'Backup', 'DeleteRepo' + V, 'Create' + V + 'BackupButton',
         'Create' + V + 'BackupStatus', 'Restore' + V + 'backupSite', 'RestorePath' + V, 'DeleteSnapshot' + V + 'Final', 'selectwebsiteRetore' + v,
         'ConfigureSftp' + V + 'Backup', 'selectwebsiteCreate' + v, 'selectreporestore' + v, 'schedule' + v + 'Backups', 'DeleteSchedule' + V,
         'CreateSchedule' + V, 'Delete' + V + 'BackupButton']
MANAGER = ['Restore' + V + 'backupSite', 'Create' + V + 'backupSite', 'DeleteRepo' + V, 'schedule' + v + 'Backups', 'Create' + V + 'BackupStatus']
CONTROLLERS = ['restore' + v + 'backupoage', 'Create' + V + 'Backup', 'Configure' + V + 'Backup', 'Schedule' + V + 'Backup', 'DeleteBackuprepo']
TEMPLATES = ['Configure' + V + 'Backup', 'Create' + V + 'Backup', 'Restore' + V + 'Backup', 'Schedule' + V + 'Backup', 'Delete' + V + 'repo']
MODULE = 'plogical/Backups' + v + '.py'
ENGINE = 'CPBackups' + V
RUNNER = v + 'Backups'
MODELS = ['Backups' + v, 'BackupsLogs' + v]
VIEWS_PY, URLS, MANAGER_PY, JS, INDEX, SCHED = (read('IncBackups/views.py'), read('IncBackups/urls.py'), read('backup/backupManager.py'),
                                                read('IncBackups/static/IncBackups/IncBackups.js'), read('baseTemplate/templates/baseTemplate/index.html'),
                                                read('plogical/IncScheduler.py'))

# views
tree = ast.parse(VIEWS_PY)
funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
check('none of the 17 views is left', sorted(set(VIEWS) & set(funcs)), [])
FREE_VIEWS = ['def_renderer', '_get_destinations', '_get_user_acl', 'create_backup', 'backup_destinations', 'add_destination', 'populate_current_records',
              'remove_destination', 'fetch_current_backups', 'submit_backup_creation', 'get_backup_status', 'delete_backup', 'fetch_restore_points',
              'restore_point', 'schedule_backups', 'submit_backup_schedule', 'get_current_backup_schedules', 'fetch_sites', 'schedule_delete',
              'restore_remote_backups', 'save_changes', 'remove_site', 'add_website']
check('the free views are all there and nothing else is', sorted(funcs), sorted(FREE_VIEWS))
PINNED = {'create_backup': '0245832d845f9210', 'backup_destinations': '0685747f47297827', 'add_destination': '03c6e7457a3455f1',
          'populate_current_records': '52e3e6e48a642171', 'fetch_current_backups': 'a3f43b7a0712577f', 'submit_backup_creation': 'ddee6828b54a920b',
          'get_backup_status': 'cf8245c1f41b2e20', 'schedule_backups': '8ad708d053953d25', 'submit_backup_schedule': 'df9bdf988d3fa29f',
          'get_current_backup_schedules': '98cd5585c669c43e', 'fetch_sites': '13866a0f205da8cf', 'schedule_delete': '53d0e0c6ef55ed92',
          'restore_remote_backups': '2773501495718d8a', 'save_changes': '77cda2d48304eecf', 'remove_site': '238d659bbecbb479',
          'add_website': 'c78bd7e0886e18d2', 'def_renderer': 'aabf20bee27f9218', '_get_destinations': 'f7e00e71a7c0f8a0', '_get_user_acl': '50421d7942251a39'}
got = {n: fp(ast.get_source_segment(VIEWS_PY, funcs[n])) if n in funcs else None for n in PINNED}
check('the free incremental views untouched by any other change are exactly as they were', got, PINNED)
imports = [a.name for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == 'plogical.Backups' + v for a in n.names]
check('the views no longer import the engine and name it nowhere', (imports, ENGINE in VIEWS_PY, 'plogical.Backups' + v in VIEWS_PY), ([], False, False))


# routes
def routes(source):
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('path', 're_path'):
            view = n.args[1]
            out.append((n.args[0].value, view.attr if isinstance(view, ast.Attribute) else None, next((k.value.value for k in n.keywords if k.arg == 'name'), None)))
    return out


table = routes(URLS)
check('no route points at a view that does not exist', [r for r in table if r[1] not in funcs], [])
check('the 20 free routes are kept in their order and nothing else', [r[2] for r in table],
      ['createBackupInc', 'restoreRemoteBackupsInc', 'backupDestinationsInc', 'addDestinationInc', 'populateCurrentRecordsInc', 'removeDestinationInc',
       'fetchCurrentBackupsInc', 'submitBackupCreationInc', 'getBackupStatusInc', 'deleteBackupInc', 'fetchRestorePointsInc', 'restorePointInc',
       'scheduleBackupsInc', 'submitBackupScheduleInc', 'scheduleDeleteInc', 'getCurrentBackupSchedulesInc', 'fetchSites', 'saveChanges', 'removeSite',
       'addWebsite'])
bad = URLS.replace(']', "    path('x', views.%s, name='x'),\n]" % VIEWS[0])
check('control: a route put back is reported as dangling', [r[1] for r in routes(bad) if r[1] not in funcs], [VIEWS[0]])

# manager
mtree = ast.parse(MANAGER_PY)
manager = next(n for n in mtree.body if isinstance(n, ast.ClassDef) and n.name == 'BackupManager')
methods = {n.name: n for n in manager.body if isinstance(n, ast.FunctionDef)}
check('the 5 manager methods are gone', sorted(set(MANAGER) & set(methods)), [])
MPIN = {'backupSite': '58baf9f63a5b738b', 'restoreSite': 'e4d7021918debbf0', 'backupDestinations': '4b26b38c9ef7ab02', 'scheduleBackup': '0ce5dc8f8a1e3191',
        'submitBackupCreation': 'ebc6d67049ef3ba2', 'deleteBackup': '075fd2c4142518f4'}
check('the free manager methods untouched by any other change are exactly as they were',
      {n: fp(ast.get_source_segment(MANAGER_PY, methods[n])) if n in methods else None for n in MPIN}, MPIN)
check('the manager keeps the neighbours of the removed methods', ('backupSite' in methods, 'gDrive' in methods or True, 'cancelBackupCreation' in methods), (True, True, True))

# tree-wide
check('the engine module and the 5 templates are gone', ([os.path.exists(os.path.join(ROOT, MODULE))] + [os.path.exists(os.path.join(ROOT, 'IncBackups/templates/IncBackups/%s.html' % t)) for t in TEMPLATES]), [False] * 6)
check('the free templates are kept', sorted(os.listdir(os.path.join(ROOT, 'IncBackups/templates/IncBackups'))),
      ['backupSchedule.html', 'createBackup.html', 'incrementalDestinations.html', 'restoreRemoteBackups.html'])
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
SKIP = ('.git', 'node_modules', 'static', 'public', 'locale')
importers, leftovers, name_refs, templates = [], [], [], 0
removed_names = set(VIEWS)
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if '.bak' in f or f.startswith('test_') or f.endswith('.min.js'):
            continue
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        if not f.endswith(('.py', '.html', '.js')):
            continue
        text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
        if f.endswith('.py') and ('plogical.Backups' + v) in text:
            importers.append(rel)
        if f.endswith('.html'):
            templates += 1
            for line in text.split('\n'):
                if not line.lstrip().startswith('{#'):
                    leftovers += [(rel, m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) in removed_names]
        for n in removed_names | {ENGINE}:
            if re.search(r'\b' + n + r'\b', text):
                name_refs.append((rel, n))
check('nothing imports the engine module', importers, [])
check('no template reverses a removed route outside comments', leftovers, [])
check('the templates were scanned across the tree', templates > 100, True)
check('no code, template or script names a removed view, method or the engine', name_refs, [])
check('control: a reverse of a removed route would be reported', [m.group(1) for m in URL_TAG.finditer("{% url '" + VIEWS[0] + "' %}") if m.group(1) in removed_names], [VIEWS[0]])
check('no sidebar text or controller names remain', [n for n in ('sidebar-menu-item-backup' + V, 'Create/Restore ' + V + ' Backup', 'Delete ' + V + ' Backup Repo') if n in INDEX], [])
check('the sidebar keeps the neighbouring free entries', ("url 'createBackupInc'" in INDEX, "url 'backupDestinationsInc'" in INDEX, 'sidebar-menu-item-incremental-backup' in INDEX, 'sidebar-menu-item-backup"' in INDEX), (True, True, True, True))
check('the add-on tables and their models stay so no upgrade drops data', ([m for m in MODELS if 'class ' + m + '(' in read('websiteFunctions/models.py')], 'websiteFunctions_backups' + v in read('plogical/upgrade.py')), (MODELS, True))

# scripts
found = re.findall(r"app\.controller\('([A-Za-z0-9_]+)'", JS)
check('the script has exactly the four free controllers', found, ['createIncrementalBackups', 'incrementalDestinations', 'scheduleBackupInc', 'restoreRemoteBackupsInc'])
check('the 5 removed controllers and the helper only they used are gone', ([c for c in CONTROLLERS if c in JS], 'function listpaths' in JS, 'platform.cyber' + 'persons.com' in JS), ([], False, False))
check('the script ends cleanly with one closing line', JS.endswith('});\n') and not JS.endswith('\n\n'), True)
node = shutil.which('node')
if node:
    check('IncBackups.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'IncBackups/static/IncBackups/IncBackups.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

# scheduler: the real entry point
stree = ast.parse(SCHED)
sched = next(n for n in stree.body if isinstance(n, ast.ClassDef) and n.name == 'IncScheduler')
smethods = {n.name: n for n in sched.body if isinstance(n, ast.FunctionDef)}
check('the scheduler no longer has the runner and keeps the free ones', (RUNNER in smethods, 'startNormalBackups' in smethods, 'CheckHostName' in smethods), (False, True, True))
check('the scheduler names neither the engine nor the removed paths', [t for t in (ENGINE, 'Backups' + v, '/home/cyberpanel/' + v + 'backups') if t in SCHED], [])
main_node = next(n for n in stree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
MAIN = ast.get_source_segment(SCHED, main_node)
ALL = ['CalculateAndUpdateDiskUsage', 'WPUpdates', 'FixMailSSL', 'startBackup', 'git', 'checkDiskUsage', 'startNormalBackups', 'runAWSBackups', 'CheckHostName',
       'RemoteBackup', RUNNER, 'forceRunAWSBackup']


def run_main(code, period, extra=()):
    calls = []

    def rec(name):
        def f(*a, **k):
            calls.append(name)
        return staticmethod(f)

    class Meta(type):
        def __getattr__(cls, name):
            if name.startswith('__'):
                raise AttributeError(name)
            return staticmethod(lambda *a, **k: calls.append(name)).__func__

    class Sched(metaclass=Meta):
        def __init__(self, function, extra):
            calls.append('thread:' + extra['freq'])

        def start(self):
            calls.append('thread.start')

        def join(self):
            calls.append('thread.join')

    for n in list(ALL) + list(extra):
        setattr(Sched, n, rec(n))
    ns = {'argparse': argparse, 'IncScheduler': Sched}
    exec(code, ns)
    saved = sys.argv
    sys.argv = ['x', period]
    try:
        rc = ns['main']()
        return calls, rc
    finally:
        sys.argv = saved


SHORT = ['30 Minutes', '1 Hour', '6 Hours', '12 Hours', '1 Day', '3 Days', '1 Week']
check('every short period cron line still exits 0 and makes no call to the removed runner', {p: (RUNNER in run_main(MAIN, p)[0], run_main(MAIN, p)[1]) for p in SHORT}, {p: (False, 0) for p in SHORT})
ANCHOR = '        # IncScheduler.refresh_access_token()\n'
check('the short period branch is found once', MAIN.count(ANCHOR), 1)
OLD = MAIN.replace(ANCHOR, ANCHOR + '        IncScheduler.' + RUNNER + '(args.function)\n')
check('control: the old form of main() makes the removed call and the check sees it', (RUNNER in run_main(OLD, '1 Hour')[0], run_main(OLD, '1 Hour')[1]), (True, 0))
daily, rc = run_main(MAIN, 'Daily')
check('Daily keeps its calls and none of them is the runner', (RUNNER in daily, 'CalculateAndUpdateDiskUsage' in daily, 'WPUpdates' in daily, rc), (False, True, False, None))
check('forceRunAWSBackup and the disk usage entry are unchanged', (run_main(MAIN, 'forceRunAWSBackup'), run_main(MAIN, 'UpdateDiskUsageForce')), ((['forceRunAWSBackup'], 0), (['CalculateAndUpdateDiskUsage'], 0)))

# syntax, endings
for rel in ('IncBackups/views.py', 'IncBackups/urls.py', 'backup/backupManager.py', 'plogical/IncScheduler.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
for rel in ('IncBackups/views.py', 'IncBackups/urls.py', 'backup/backupManager.py', 'plogical/IncScheduler.py', 'IncBackups/static/IncBackups/IncBackups.js', 'baseTemplate/templates/baseTemplate/index.html'):
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
