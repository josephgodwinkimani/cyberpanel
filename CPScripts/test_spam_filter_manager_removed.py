"""Tests that the spam filter manager page of the e-mail app (a paid add-on) is removed without touching the free e-mail pages: its twelve
views, twelve routes, template, JavaScript controller, sidebar entry and the seven helper functions with their log path constants and
command line branches are gone, nothing that remains points at them, and the free views and helpers are byte for byte what they were
(pinned by hash). The names are built here so this file does not name the add-on. Needs node for the script syntax check (reported as
skipped when it is missing).
Run: python3 CPScripts/test_spam_filter_manager_removed.py"""
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


X = 'Rsp' + 'amd'
VIEWS_REMOVED = [X, 'install' + X, 'installStatus' + X, 'fetch' + X + 'Settings', 'save' + X + 'Configurations', 'savepostfixConfigurations',
                 'saveRedisConfigurations', 'saveclamavConfigurations', 'unistall' + X, 'uninstallStatus' + X, 'Fetch' + X + 'Log', 'Restart' + X]
HELPERS_REMOVED = ['install' + X, 'uninstall' + X, 'change' + X + 'Config', 'changePostfixConfig', 'changeRedisxConfig', 'changeclamavConfig', 'checkIf' + X + 'Installed']
CONSTANTS = [X + 'InstallLogPath', X + 'UnInstallLogPath', 'R' + 'Spamd' + 'LogPath']
VIEWS, URLS, UTILS = read('emailPremium/views.py'), read('emailPremium/urls.py'), read('plogical/mailUtilities.py')
JS, INDEX = read('emailPremium/static/emailPremium/emailPremium.js'), read('baseTemplate/templates/baseTemplate/index.html')


def funcs(src, scope=None):
    tree = ast.parse(src)
    body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == scope).body if scope else tree.body
    return {n.name: n for n in body if isinstance(n, ast.FunctionDef)}


def digest(src, node):
    return hashlib.sha256(ast.get_source_segment(src, node).encode()).hexdigest()[:16]


views, utils = funcs(VIEWS), funcs(UTILS, 'mailUtilities')
check('the twelve views are gone', sorted(set(VIEWS_REMOVED) & set(views)), [])
check('the seven helper functions are gone', sorted(set(HELPERS_REMOVED) & set(utils)), [])
check('the three log path constants are gone', [c for c in CONSTANTS if c in UTILS], [])
main_src = UTILS.split('def main')[1]
check('the command line has no branch for the removed helpers', [h for h in HELPERS_REMOVED if h in main_src], [])
PINNED_VIEWS = {'emailPolicyServer': 'f254e418ab87561d', 'listDomains': 'e84f77efd036f672', 'spamAssassinHome': '8e101d3b86e29f5f', 'installSpamAssassin': 'fc95cb05a2657111',
                'mailQueue': 'd086c5c4ba73c241', 'MailScanner': '709fae863484d565', 'installMailScanner': '2c43a05751b7179e', 'statusFunc': 'de859b27004753e3'}
check('eight free views are exactly as they were', {n: digest(VIEWS, views[n]) if n in views else None for n in PINNED_VIEWS}, PINNED_VIEWS)
PINNED_UTILS = {'installSpamAssassin': '25a5a756a4577cba', 'installMailScanner': 'a977e63900564ff9', 'saveSpamAssassinConfigs': 'c915a5cfc5d8a0b2', 'createEmailAccount': '5e0cb34608cc590f'}
check('four free mail helpers are exactly as they were', {n: digest(UTILS, utils[n]) if n in utils else None for n in PINNED_UTILS}, PINNED_UTILS)
check('the free command line branches are kept', [b for b in ('installSpamAssassin', 'installMailScanner', 'AfterEffects', 'ResetEmailConfigurations') if ("args.function == '%s'" % b) not in main_src and ('args.function == "%s"' % b) not in main_src], [])


# routes
def routes(source):
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('path', 're_path'):
            view = n.args[1]
            out.append((view.attr if isinstance(view, ast.Attribute) else None, next((k.value.value for k in n.keywords if k.arg == 'name'), None)))
    return out


table = routes(URLS)
check('no route points at a view that does not exist', [r for r in table if r[0] not in views], [])
check('no route of the removed views is left', [r for r in table if r[0] in VIEWS_REMOVED or r[1] in VIEWS_REMOVED], [])
check('the free routes are kept and the catch-all is last', ([n for n in ('emailPolicyServer', 'listDomains', 'SpamAssassin', 'mailQueue', 'MailScanner', 'statusFunc') if n not in {r[1] for r in table}], table[-1][1]), ([], 'emailLimits'))
bad = URLS.replace("    path('statusFunc',", "    path('x', views.%s, name='x'),\n    path('statusFunc'," % X)
check('control: a route put back is reported as dangling', [r[0] for r in routes(bad) if r[0] not in views], [X])

# the rest of the tree
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
defined = set()
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f == 'urls.py':
            defined |= {r[1] for r in routes(open(os.path.join(base, f), encoding='utf-8').read()) if r[1]}
check('the removed route names exist nowhere', sorted(set(VIEWS_REMOVED) & defined), [])
leftovers, refs, templates = [], [], 0
TOKENS = HELPERS_REMOVED + CONSTANTS + ['/emailPremium/' + v for v in VIEWS_REMOVED] + ['emailPremium/' + X + '.html']
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        if f.endswith('.html') and '.bak' not in f:
            templates += 1
            for line in open(os.path.join(base, f), encoding='utf-8', errors='replace').read().split('\n'):
                if not line.lstrip().startswith('{#'):
                    leftovers += [(rel, m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) in VIEWS_REMOVED]
        if f.endswith(('.py', '.html', '.js')) and '.bak' not in f and not f.startswith('test_') and not f.endswith('.min.js'):
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            refs += [(rel, t) for t in TOKENS if t in text]
check('no template reverses a removed route', leftovers, [])
check('the templates were scanned across the tree', templates > 100, True)
check('nothing in the tree names the removed helpers, constants, endpoints or template', refs, [])
check('the template is gone', os.path.exists(os.path.join(ROOT, 'emailPremium/templates/emailPremium/' + X + '.html')), False)
check('the sidebar has no entry for it and keeps its neighbours', (("url '" + X + "'") not in INDEX, "url 'MailScanner'" in INDEX, "url 'SpamAssassin'" in INDEX, "url 'mailQueue'" in INDEX, "url 'emailMarketing'" in INDEX), (True, True, True, True, True))
sample = "<li><a href=\"{% url '" + X + "' %}\">x</a></li>"
check('control: the template check would report a left-over reverse', [m.group(1) for m in URL_TAG.finditer(sample) if m.group(1) in VIEWS_REMOVED], [X])

# script
controllers = re.findall(r"^app\.controller\('([A-Za-z]+)'", JS, flags=re.M)
check('the controller is gone and the other email controllers are kept', ([c for c in controllers if c == X], sorted(set(controllers) & {'listDomains', 'emailDomainPage', 'emailPage', 'SpamAssassin', 'policyServer', 'mailQueue', 'MailScanner'})),
      ([], sorted(['listDomains', 'emailDomainPage', 'emailPage', 'SpamAssassin', 'policyServer', 'mailQueue', 'MailScanner'])))
node = shutil.which('node')
if node:
    check('emailPremium.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'emailPremium/static/emailPremium/emailPremium.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

for rel in ('emailPremium/views.py', 'emailPremium/urls.py', 'plogical/mailUtilities.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
for rel in ('emailPremium/views.py', 'emailPremium/urls.py', 'emailPremium/static/emailPremium/emailPremium.js', 'baseTemplate/templates/baseTemplate/index.html', 'plogical/mailUtilities.py'):
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
