"""Tests that the mail debugger add-on is removed from the panel without leaving anything dangling: its six views, six routes, template,
two JavaScript controllers and sidebar entry are gone, the status route that the free Onboarding page polls stays, and no route,
template or script that remains points at something that was removed (a leftover reverse in the base template would break every page).
Needs node for the script syntax check (reported as skipped when it is missing).
Run: python3 CPScripts/test_mail_debug_addon_removed.py"""
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


ED = 'Email' + 'Debugger'
REMOVED = (ED, 'RunServerLevelEmailChecks', 'ResetEmailConfigurations', 'ReadReport', 'debugEmailForSite', 'fixMailSSL')
views_src = read('emailPremium/views.py')
urls_src = read('emailPremium/urls.py')
js_src = read('emailPremium/static/emailPremium/emailPremium.js')
index_src = read('baseTemplate/templates/baseTemplate/index.html')

# views
tree = ast.parse(views_src)
funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
check('the six debugger views are gone', sorted(set(REMOVED) & set(funcs)), [])
check('the status view the Onboarding page polls is kept and unchanged',
      hashlib.sha256(ast.get_source_segment(views_src, funcs['statusFunc']).encode()).hexdigest()[:16] if 'statusFunc' in funcs else None, 'de859b27004753e3')
free = ('emailPolicyServer', 'listDomains', 'getFurtherDomains', 'emailLimits', 'emailPage', 'getEmailStats', 'spamAssassinHome', 'mailQueue', 'MailScanner')
check('the free email pages keep their views', [n for n in free if n not in funcs], [])


# routes: every route points at a view that exists, none points at a removed one
def routes(source):
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('path', 're_path'):
            view = n.args[1]
            name = next((k.value.value for k in n.keywords if k.arg == 'name'), None)
            out.append((n.args[0].value, view.attr if isinstance(view, ast.Attribute) else None, name))
    return out


def dangling(source, views):
    return [r for r in routes(source) if r[1] not in views]


table = routes(urls_src)
check('no route points at a view that does not exist', dangling(urls_src, funcs), [])
check('no debugger route is left', [r for r in table if r[1] in REMOVED or r[2] in REMOVED], [])
check('the status route is kept and the catch-all is still last', ([r for r in table if r[2] == 'statusFunc'], table[-1][2]), ([('statusFunc', 'statusFunc', 'statusFunc')], 'emailLimits'))
check('the routes of the free email pages are still there',
      [n for n in ('emailPolicyServer', 'listDomains', 'getFurtherDomains', 'emailPage', 'getEmailStats', 'SpamAssassin', 'mailQueue', 'MailScanner', 'emailLimits') if n not in {r[2] for r in table}], [])

# control: the check would catch a route left behind
bad = urls_src.replace("    path('statusFunc',", "    path('ReadReport', views.ReadReport, name='ReadReport'),\n    path('statusFunc',")
check('control: a debugger route put back is reported as dangling', [r[1] for r in dangling(bad, funcs)], ['ReadReport'])

# templates and scripts anywhere in the tree
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
defined = set()
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f == 'urls.py':
            defined |= {r[2] for r in routes(open(os.path.join(base, f), encoding='utf-8').read()) if r[2]}
gone = [n for n in REMOVED if n not in defined]
check('five of the six route names no longer exist anywhere (fixMailSSL is still the free mail page route)',
      (sorted(set(REMOVED) - {'fixMailSSL'} - set(gone)), 'fixMailSSL' in defined), ([], True))

leftovers, templates = [], 0
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f.endswith('.html') and '.bak' not in f:
            templates += 1
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            for line in text.split('\n'):
                if line.lstrip().startswith('{#'):
                    continue
                for m in URL_TAG.finditer(line):
                    if m.group(1) in gone:
                        leftovers.append((os.path.relpath(os.path.join(base, f), ROOT), m.group(1)))
check('no template reverses a route that no longer exists', leftovers, [])
check('the template was scanned across the tree', templates > 100, True)
check('the base template has no debugger entry and keeps its neighbours', (('Email' + ' Debugger') not in index_src, "url 'mailQueue'" in index_src, "url 'SpamAssassin'" in index_src, "url 'MailScanner'" in index_src), (True, True, True, True))
check('the debugger template is gone', os.path.exists(os.path.join(ROOT, 'emailPremium/templates/emailPremium/' + ED + '.html')), False)

# control: the template check reports a reverse that was left behind
sample = '<li><a href="{% url ' + chr(39) + ED + chr(39) + ' %}">x</a></li>'
check('control: the template check would report a left-over reverse', [m.group(1) for m in URL_TAG.finditer(sample) if m.group(1) in gone], [ED])

# nothing renders or calls the removed pieces any more
refs = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f.endswith(('.py', '.html', '.js')) and '.bak' not in f and not f.startswith('test_') and not f.endswith('.min.js'):
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            if rel.startswith('cloudAPI') or rel in ('plogical/mailUtilities.py', 'mailServer/mailserverManager.py'):
                continue  # the Cloud API and the helper classes are removed in their own change
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            for pat in ('emailPremium/' + ED + '.html', "/emailPremium/RunServerLevelEmailChecks", "/emailPremium/ResetEmailConfigurations", "/emailPremium/ReadReport", "/emailPremium/debugEmailForSite", "/emailPremium/fixMailSSL", 'url ' + chr(39) + ED + chr(39)):
                if pat in text:
                    refs.append((rel, pat))
check('nothing outside the Cloud API and the helper classes names the removed template or endpoints', refs, [])
check('the Onboarding script still polls the kept status route', '"/emailPremium/statusFunc"' in read('baseTemplate/static/baseTemplate/custom-js/system-status.js'), True)

# script
controllers = re.findall(r"^app\.controller\('([A-Za-z]+)'", js_src, flags=re.M)
check('both debugger controllers are gone', [c for c in controllers if c in ('EmailDebuuger', 'email' + 'DebuggerDomainLevel')], [])
check('the other email controllers are kept', [c for c in ('listDomains', 'emailDomainPage', 'emailPage', 'SpamAssassin', 'policyServer', 'mailQueue', 'MailScanner') if c not in controllers], [])
node = shutil.which('node')
if node:
    check('emailPremium.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'emailPremium/static/emailPremium/emailPremium.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

for rel in ('emailPremium/views.py', 'emailPremium/urls.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
for rel in ('emailPremium/views.py', 'emailPremium/urls.py', 'emailPremium/static/emailPremium/emailPremium.js', 'baseTemplate/templates/baseTemplate/index.html'):
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
