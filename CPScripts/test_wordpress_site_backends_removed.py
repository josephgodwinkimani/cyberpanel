"""Tests that the backend code of the paid WordPress site manager is removed without touching the free one click installers: the 10 installer
methods and their dispatch entries (create from the manager, plugin and theme update and delete and status, staging, deploy to live, backup and
restore), the 4 scheduler functions of its remote backups and automatic updates with their two calls in the cron entry point, and the two ACL
helpers only the manager used are gone, nothing calls them, the cron entry point still exits cleanly for every period and runs the same
daily work (the real main() is executed with recorders, and an old form control proves the check sees a removed call), and every other
installer, scheduler and ACL function is byte for byte what it was (pinned by hash where no other change touches it). The Cloud API deploy
function and the models stay. Run: python3 CPScripts/test_wordpress_site_backends_removed.py"""
import argparse
import ast
import hashlib
import os
import re
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


INSTALLER = ['wordpressInstallNew', 'UpdateWPTheme', 'UpdateWPPlugin', 'DeleteThemes', 'DeletePlugins', 'ChangeStatusThemes', 'CreateStagingNow',
             'DeploytoProduction', 'WPCreateBackup', 'RestoreWPbackupNow']
SCHEDULER = ['WPUpdates', 'RemoteBackup', 'SendTORemote', 'SendToS3Cloud']
ACL = ['GetALLWPObjects', 'CheckIPBackupObjectOwner']
AI_SRC, SCHED_SRC, ACL_SRC = read('plogical/applicationInstaller.py'), read('plogical/IncScheduler.py'), read('plogical/acl.py')


def methods_of(src, cls):
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}, node


def pins(src, table, methods):
    return {n: fp(ast.get_source_segment(src, methods[n])) if n in methods else None for n in table}


# installer
ai, ai_cls = methods_of(AI_SRC, 'ApplicationInstaller')
check('none of the 10 installer methods is left', sorted(set(INSTALLER) & set(ai)), [])
AIPIN = {'__init__': '3dd45b418e91863f', 'UpgradeCP': 'c0b4457d48defe43', 'setupComposer': '69c9df5715e9f7ff', 'InstallNodeJS': 'fb61f16bccff7990',
         'installMautic': '376e9f39ae25d721', 'updatePackage': 'fe4da74c0fda0a93', 'convertDomainToSite': '3a43a1283df42d26', 'installWPCLI': 'd82e2631f88c275c',
         'dataLossCheck': '72cab2ed76469dfd', 'installGit': '9132888dbc94f520', 'dbCreation': '4f5eeca8ec157740', 'installWordPress': '0a1a9c94b9d9aece',
         'installPrestaShop': 'af99a79aa0d55217', 'installJoomla': 'cc323de6ff4f8e6e', 'DeployWordPress': 'a338729188158ba7', 'installWhmcs': '1efac8da48234506',
         'UpdateDownloadStatus': '096bbcc4521be386'}
check('the free installers and shared helpers untouched by any other change are exactly as they were', pins(AI_SRC, AIPIN, ai), AIPIN)
run = ast.get_source_segment(AI_SRC, ai['run'])
keys = re.findall(r"self\.installApp == '([A-Za-z]+)'", run)
check('the dispatch has no entry for a removed method and keeps the free ones', ([k for k in keys if k in INSTALLER], [k for k in keys if k != 'StartOCRestore']),
      ([], ['wordpress', 'joomla', 'prestashop', 'magento', 'convertDomainToSite', 'updatePackage', 'mautic', 'UpgradeCP']))
check('every kept dispatch entry calls a method that exists (the magento entry has none in the base too)', [k for k in re.findall(r"self\.([A-Za-z]+)\(\)", run) if k not in ai], ['installMagento'])
inner = []
for name, node in ai.items():
    seg = ast.get_source_segment(AI_SRC, node)
    inner += [(name, n) for n in INSTALLER if re.search(r'self\.' + n + r'\b', seg)]
check('no remaining installer method calls a removed one', inner, [])
check('the Cloud API deploy entry of the command line is kept', ('args.function == "DeployWordPress"' in AI_SRC, 'ai.DeployWordPress()' in AI_SRC), (True, True))

# scheduler
sm, sched_cls = methods_of(SCHED_SRC, 'IncScheduler')
check('none of the 4 scheduler functions is left', sorted(set(SCHEDULER) & set(sm)), [])
SPIN = {'__init__': '7be5422e7bef748a', 'run': '44327be44b35b35e', 'startBackup': 'dd81af873ff7e687', 'git': '2b979f40b369c6eb', 'checkDiskUsage': '3bb45d8c960658bc',
        'fetchAWSKeys': '36e48c6039798fa2', 'forceRunAWSBackup': 'b043d334bcdcabf9', 'runAWSBackups': '4ea79d4095555020', 'CalculateAndUpdateDiskUsage': '064a98e5ca369591',
        'CheckHostName': 'ebdb73362bf6f214'}
check('the other scheduler functions untouched by any other change are exactly as they were', pins(SCHED_SRC, SPIN, sm), SPIN)
check('the scheduler names none of the removed functions or the removed models', [t for t in SCHEDULER + ['RemoteBackupSchedule', 'RemoteBackupsites', 'WPSites'] if re.search(r'\b' + t + r'\b', SCHED_SRC)], [])
main_node = next(n for n in ast.parse(SCHED_SRC).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
MAIN = ast.get_source_segment(SCHED_SRC, main_node)
ALL = ['CalculateAndUpdateDiskUsage', 'FixMailSSL', 'startBackup', 'git', 'checkDiskUsage', 'startNormalBackups', 'runAWSBackups', 'CheckHostName', 'forceRunAWSBackup'] + SCHEDULER


def run_main(code, period):
    calls = []

    class Meta(type):
        def __getattr__(cls, name):
            if name.startswith('__'):
                raise AttributeError(name)
            return lambda *a, **k: calls.append(name)

    class Sched(metaclass=Meta):
        def __init__(self, function, extra):
            calls.append('thread:' + extra['freq'])

        def start(self):
            calls.append('thread.start')

        def join(self):
            calls.append('thread.join')

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
check('every short period cron line still exits 0 and runs nothing', {p: run_main(MAIN, p) for p in SHORT}, {p: ([], 0) for p in SHORT})
ANCHOR = '        # IncScheduler.refresh_access_token()\n'
check('the short period branch is found once', MAIN.count(ANCHOR), 1)
OLD = MAIN.replace(ANCHOR, ANCHOR + '        IncScheduler.RemoteBackup(args.function)\n')
check('control: the old form of main() makes the removed call and the check sees it', run_main(OLD, '1 Hour'), (['RemoteBackup'], 0))
daily, rc = run_main(MAIN, 'Daily')
check('Daily keeps the disk usage work and makes none of the removed calls', ([c for c in daily if c in SCHEDULER], 'CalculateAndUpdateDiskUsage' in daily, rc), ([], True, None))
weekly, rc = run_main(MAIN, 'Weekly')
check('Weekly keeps its work and makes none of the removed calls', ([c for c in weekly if c in SCHEDULER], 'FixMailSSL' in weekly, 'CalculateAndUpdateDiskUsage' in weekly), ([], True, True))
check('the disk usage and AWS entries are unchanged', (run_main(MAIN, 'UpdateDiskUsageForce'), run_main(MAIN, 'forceRunAWSBackup')), ((['CalculateAndUpdateDiskUsage'], 0), (['forceRunAWSBackup'], 0)))

# ACL
am, acl_cls = methods_of(ACL_SRC, 'ACLManager')
check('the two ACL helpers are gone', sorted(set(ACL) & set(am)), [])
APIN = {'loadedACL': '9d01fdde29fea284', 'checkOwnership': '9e9360cd2f92abcb', 'findAllSites': '560c4d17518939c0', 'currentContextPermission': '68b75d36517506e5',
        'loadError': '935f599a486ce998', 'loadAllUsers': '1fd917c7b357eab1', 'GetServerIP': 'fe182f4839056536', 'findWebsiteObjects': 'db20bad6dcf57d2a',
        'CheckStatusFilleLoc': '5bf014d8e0bdde57'}
check('the neighbouring ACL helpers are exactly as they were', pins(ACL_SRC, APIN, am), APIN)

# tree-wide
SKIP = ('.git', 'node_modules', 'static', 'public', 'locale')
callers = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if not f.endswith(('.py', '.html', '.js')) or '.bak' in f or f.startswith('test_') or f.endswith('.min.js'):
            continue
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
        for n in INSTALLER:
            if re.search(r"ApplicationInstaller\(\s*['\"]" + n + r"['\"]", text) or re.search(r'\b(background|ai)\.' + n + r'\(', text):
                callers.append((rel, n))
        for n in SCHEDULER:
            if re.search(r'IncScheduler\.' + n + r'\b', text):
                callers.append((rel, n))
        for n in ACL:
            if re.search(r'\b' + n + r'\b', text):
                callers.append((rel, n))
check('nothing calls a removed installer, scheduler or ACL function', callers, [])
check('control: a call of a removed installer function would be reported', bool(re.search(r"ApplicationInstaller\(\s*['\"]" + INSTALLER[0] + r"['\"]", "ApplicationInstaller('wordpressInstallNew', extraArgs)")), True)
models = read('websiteFunctions/models.py')
check('the models stay so no upgrade drops data', [m for m in ('WPSites', 'WPStaging', 'WPSitesBackup', 'wpplugins', 'RemoteBackupConfig', 'RemoteBackupSchedule', 'RemoteBackupsites') if 'class ' + m + '(' in models],
      ['WPSites', 'WPStaging', 'WPSitesBackup', 'wpplugins', 'RemoteBackupConfig', 'RemoteBackupSchedule', 'RemoteBackupsites'])

for rel in ('plogical/applicationInstaller.py', 'plogical/IncScheduler.py', 'plogical/acl.py'):
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
