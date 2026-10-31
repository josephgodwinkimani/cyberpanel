"""Tests that the two website manager methods that only the removed Cloud API and the removed Apache page called (the Apache backend status
and the switch between the Apache backend and plain OpenLiteSpeed for one site) are gone, while the command line switch of the virtual
host utilities that the backup restore still uses stays, the server constants of the manager stay, and every other manager method is byte
for byte what it was (pinned by hash where no other change touches it). Run: python3 CPScripts/test_apache_switch_methods_removed.py"""
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


GONE = ['getSwitchStatus', 'switchServer']
WEB = read('websiteFunctions/website.py')
tree = ast.parse(WEB)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'WebsiteManager')
methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
check('neither method is left in the website manager', sorted(set(GONE) & set(methods)), [])
PIN = {'wordpressInstall': 'f2624f59552d444c', 'installWordpress': 'f592559693c97c85', 'installWordpressStatus': '296117642d2d981e', 'joomlaInstall': '11647ae95dc29b98',
       'installJoomla': 'd772d41772d7c3fa', 'setupStaging': 'ce60260109e3803f', 'startCloning': 'eefe6c6ec4954b28', 'syncToMaster': '310d922b418e1c9e',
       'startSync': 'e65dc2c1a643f8ca', 'modifyWebsite': 'f98ea286e109201c', 'deleteWebsite': '1da24203f6703c00', 'siteState': '45f14b6a44524f93',
       'listWebsites': '0d7686a9cc11d6dd', 'listChildDomains': 'c6f772ec5dcc4f48', 'listCron': 'f9a2f508142358ae', 'domainAlias': 'ec4ccd935ba44e34',
       'fetchDomains': 'a12c84cba4776767', 'searchWebsites': '67cf4e44745f5f78', 'fetchWebsitesList': 'fd243b2a429d90e7', 'loadDomainHome': '45cbc150dd5b15e7',
       'installPrestaShop': '55add7b751c8f6fb', 'installMagento': 'eb9b2b870c9eb6bc', 'installMautic': '322db19e6e1c3f55', 'setupGit': '33a0bc44ec563a20',
       'changePHP': '7b51bb3ca9dddb72', 'saveSSL': 'a2ba409814a65ea6', 'sshAccess': '04191e026039a761'}
check('the other manager methods untouched by any other change are exactly as they were', {n: fp(ast.get_source_segment(WEB, methods[n])) if n in methods else None for n in PIN}, PIN)
consts = {t.id: n.value.value for n in cls.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(n.value, ast.Constant)}
check('the manager keeps its three server constants', {k: consts.get(k) for k in ('apache', 'ols', 'lsws')}, {'apache': 1, 'ols': 2, 'lsws': 3})

# nothing calls them
SKIP = ('.git', 'node_modules', 'static', 'public', 'locale')
callers = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(('.py', '.js', '.html', '.sh')) and not f.startswith('test_') and '.bak' not in f and not f.endswith('.min.js'):
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            for line in text.split('\n'):
                if re.search(r'\b(wm|WebsiteManager\(\))\.(getSwitchStatus|switchServer)\b', line) or re.search(r"['\"/](getSwitchStatus)['\"]", line) or '/websites/switchServer' in line or '/websites/getSwitchStatus' in line:
                    callers.append(rel)
check('no code, route or script calls either method', sorted(set(callers)), [])
vh = read('plogical/virtualHostUtilities.py')
bk = read('plogical/backupUtilities.py')
check('the command line switch of the virtual host utilities stays and the restore still uses it',
      ('def switchServer(virtualHostName, phpVersion, server, tempStatusPath)' in vh, "args.function == 'switchServer'" in vh, bk.count('virtualHostUtilities.switchServer(')), (True, True, 2))
urls = read('websiteFunctions/urls.py')
views = read('websiteFunctions/views.py')
check('the website routes and views no longer name them', ('getSwitchStatus' in urls or 'switchServer' in urls, 'def getSwitchStatus' in views or 'def switchServer' in views), (False, False))

for rel in ('websiteFunctions/website.py',):
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
