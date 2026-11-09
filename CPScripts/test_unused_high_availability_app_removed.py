"""Tests that the unused high availability app is gone: its folder (it had no routes, no models and no tables, and only the removed Cloud API
imported it) and its entry in the list of installed apps, while every other installed app is still listed in the same order, every listed
app still has its folder, and nothing else in the tree imports or names it. Run: python3 CPScripts/test_unused_high_availability_app_removed.py"""
import ast
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


NAME = 'high' + 'Availability'
SET = open(os.path.join(ROOT, 'CyberCP/settings.py'), encoding='utf-8').read()
tree = ast.parse(SET)
apps = next([e.value for e in n.value.elts if isinstance(e, ast.Constant)] for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'INSTALLED_APPS')
check('the app folder is gone', os.path.exists(os.path.join(ROOT, NAME)), False)
check('the app is no longer listed', NAME in apps, False)
OLD = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'baseTemplate',
       'firewall', 'loginSystem', 'packages', 'websiteFunctions', 'tuning', 'serverStatus', 'dns', 'ftp', 'userManagment', 'databases', 'mailServer', 'serverLogs', 'backup', 'managePHP',
       'manageSSL', 'api', 'filemanager', 'manageServices', 'pluginHolder', 'emailPremium', 'emailMarketing', 'cloudAPI', 's3Backups', 'dockerManager', 'containerization',
       'CLManager', 'IncBackups']
check('every other installed app is still listed in the same order', [a for a in apps if a in OLD], [a for a in OLD if a in apps])
check('the list holds nothing besides those', sorted(set(apps) - set(OLD)), [])
at = apps.index('s3Backups')
with_app = apps[:at] + [NAME] + apps[at:]
check('control: with the app put back the list differs and the check sees it', (with_app != apps, NAME in with_app), (True, True))
missing = [a for a in apps if not a.startswith('django.') and not os.path.isdir(os.path.join(ROOT, a))]
check('every listed app still has its folder', missing, [])

SKIP = ('.git', 'node_modules', 'locale')
refs = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(('.py', '.js', '.html', '.sh', '.txt', '.md', '.cfg', '.conf', '.yml', '.yaml', '.json')) and not f.startswith('test_') and not f.endswith('.min.js'):
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            if re.search(r'\b%s\b|\bhaManager\b' % NAME, text):
                refs.append(rel.replace(os.sep, '/'))
check('nothing in the tree imports or names the app', sorted(refs), [])

# the cloud app that used to import it stays as an app and does not need it
check('the Cloud API app stays installed because the free site tools use its model', 'cloudAPI' in apps and os.path.isfile(os.path.join(ROOT, 'cloudAPI/models.py')), True)

try:
    ast.parse(open(os.path.join(ROOT, 'CyberCP/settings.py'), 'rb').read(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('CyberCP/settings.py parses with the Python 3.9 grammar', parsed, True)
check('CyberCP/settings.py has no carriage returns', b'\r' in open(os.path.join(ROOT, 'CyberCP/settings.py'), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
