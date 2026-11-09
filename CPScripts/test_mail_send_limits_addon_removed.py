"""Tests that the per-address send limits add-on of the mail app is removed without leaving anything dangling: its two views, two
routes, template, JavaScript controller, sidebar entry, two manager methods and two helper functions with their command line
branches are gone. The free pages keep working: creating an e-mail account no longer runs any limit step and the account list
no longer reads a limit file for every row (a command per row). The real handlers are run with stand-ins (nothing is written or run).
Needs node for the script syntax check (reported as skipped when it is missing).
Run: python3 CPScripts/test_mail_send_limits_addon_removed.py"""
import ast
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


PAGE = 'Email' + 'Limits'
SAVE = 'SaveEmail' + 'LimitsNew'
SETUP = 'SetupEmail' + 'Limits'
CONTROLLER = 'EmailLimits' + 'New'
VIEWS, URLS, MANAGER, UTILS = (read(p) for p in ('mailServer/views.py', 'mailServer/urls.py', 'mailServer/mailserverManager.py', 'plogical/mailUtilities.py'))
JS, INDEX = read('mailServer/static/mailServer/mailServer.js'), read('baseTemplate/templates/baseTemplate/index.html')


def defs(src, scope=None):
    tree = ast.parse(src)
    body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == scope).body if scope else tree.body
    return {n.name: n for n in body if isinstance(n, ast.FunctionDef)}


views, manager, utils = defs(VIEWS), defs(MANAGER, 'MailServerManager'), defs(UTILS, 'mailUtilities')
check('the two views are gone', sorted({PAGE, SAVE} & set(views)), [])
check('the two manager methods are gone', sorted({PAGE, SAVE} & set(manager)), [])
check('the two helper functions are gone', sorted({SETUP, SAVE} & set(utils)), [])
check('the free mail views are kept', [n for n in ('fetchEmails', 'getEmailsForDomain', 'submitEmailCreation', 'fixMailSSL', 'emailForwarding') if n not in views and n not in {m for m in manager}], [])
check('the free manager methods are kept', [n for n in ('submitEmailCreation', 'getEmailsForDomain', 'fetchEmails', 'fixMailSSL', 'emailForwarding') if n not in manager], [])
check('the free helper functions are kept', [n for n in ('createEmailAccount', 'deleteEmailAccount', 'saveSpamAssassinConfigs') if n not in utils], [])
check('the command line has no branch for the removed helpers', (SETUP in UTILS.split('def main')[1], SAVE in UTILS.split('def main')[1]), (False, False))
check('the command line keeps the shared temporary path option', "'--tempConfigPath'" in UTILS, True)
check('nothing in the mail files names the removed rate limit files any more', [w for w in ('bad' + 'users', 'ratelimit', 'custom_ratelimit') if w in MANAGER or w in VIEWS], [])


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
check('no route of the removed views is left', [r for r in table if r[0] in (PAGE, SAVE) or r[1] in (PAGE, SAVE)], [])
check('the free mail routes are kept', [n for n in ('fetchEmails', 'getEmailsForDomain', 'emailForwarding', 'fixMailSSL') if n not in {r[1] for r in table}], [])
bad = URLS.replace("    re_path(r'^generateDKIMKeys$'", "    re_path(r'^%s$', views.%s, name='%s'),\n    re_path(r'^generateDKIMKeys$'" % (PAGE, PAGE, PAGE))
check('control: a route put back is reported as dangling', [r[0] for r in routes(bad) if r[0] not in views], [PAGE])

# templates, sidebar and the rest of the tree
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
defined = set()
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f == 'urls.py':
            defined |= {r[1] for r in routes(open(os.path.join(base, f), encoding='utf-8').read()) if r[1]}
check('the route name no longer exists anywhere (the free per-domain limits page uses a different, lower case name)', (PAGE in defined, 'emailLimits' in defined), (False, True))
leftovers, templates, refs = [], 0, []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        if f.endswith('.html') and '.bak' not in f:
            templates += 1
            for line in open(os.path.join(base, f), encoding='utf-8', errors='replace').read().split('\n'):
                if not line.lstrip().startswith('{#'):
                    leftovers += [(rel, m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) == PAGE]
        if f.endswith(('.py', '.html', '.js')) and '.bak' not in f and not f.startswith('test_') and not f.endswith('.min.js') and not rel.startswith('cloudAPI'):
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            for pat in ('mailServer/' + PAGE + '.html', '/email/' + SAVE, SETUP, SAVE, 'ng-controller="' + CONTROLLER + '"'):
                if pat in text:
                    refs.append((rel, pat))
check('no template reverses the removed route', leftovers, [])
check('the templates were scanned across the tree', templates > 100, True)
check('nothing outside the Cloud API names the removed template, endpoint, helpers or controller', refs, [])
check('the template is gone', os.path.exists(os.path.join(ROOT, 'mailServer/templates/mailServer/' + PAGE + '.html')), False)
check('the sidebar has no limits entry and keeps its neighbours', (("url '%s'" % PAGE) not in INDEX, "url 'emailForwarding'" in INDEX, "url 'deleteEmailAccount'" in INDEX, "url 'changeEmailAccountPassword'" in INDEX), (True, True, True, True))
sample = "<li><a href=\"{% url '" + PAGE + "' %}\">x</a></li>"
check('control: the template check would report a left-over reverse', [m.group(1) for m in URL_TAG.finditer(sample) if m.group(1) == PAGE], [PAGE])

# script
controllers = re.findall(r"^app\.controller\('([A-Za-z]+)'", JS, flags=re.M)
check('the controller is gone and the six others are kept', ([c for c in controllers if c == CONTROLLER], sorted(controllers)),
      ([], sorted(['createEmailAccount', 'deleteEmailAccount', 'changeEmailPassword', 'dkimManager', 'emailForwarding', 'listEmails'])))
node = shutil.which('node')
if node:
    check('mailServer.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'mailServer/static/mailServer/mailServer.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')


# behaviour of the two free handlers
def method_source(name):
    node = defs(MANAGER, 'MailServerManager')[name]
    return ast.get_source_segment(MANAGER, node).replace('\n' + ' ' * node.col_offset, '\n')


def build(name, source, body):
    ran, opened = [], []
    acl = types.SimpleNamespace(loadedACL=lambda u: {}, currentContextPermission=lambda a, p: 1, checkOwnership=lambda d, ad, c: 1,
                                loadErrorJson=lambda *a: {'status': 0, 'errorMessage': 'denied'})

    class Emails(list):
        def count(self):
            return len(self)

    domain = types.SimpleNamespace(eusers_set=types.SimpleNamespace(all=lambda: Emails([types.SimpleNamespace(email='a@example.test', DiskUsage='5'), types.SimpleNamespace(email='b@example.test', DiskUsage='7')])))
    ns = {'json': json, 'HttpResponse': lambda b: json.loads(b), 'ACLManager': acl, 'Administrator': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda pk: object())),
          'Domains': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda domain: domain_obj)),
          'mailUtilities': types.SimpleNamespace(createEmailAccount=lambda d, u, p: (1, 'None')),
          'ProcessUtilities': types.SimpleNamespace(outputExecutioner=lambda *a, **k: ran.append(a) or '', executioner=lambda *a, **k: ran.append(a)),
          'randint': lambda a, b: 123456, 'open': lambda *a, **k: opened.append(a) or types.SimpleNamespace(write=lambda t: None, close=lambda: None),
          'virtualHostUtilities': types.SimpleNamespace(cyberPanel='/x')}
    domain_obj = domain
    exec(source, ns)
    me = types.SimpleNamespace(request=types.SimpleNamespace(session={'userID': 1}, body=json.dumps(body)))
    return (lambda: ns[name](me)), ran, opened


for extra, label in (({}, 'without a limit'), ({'EmailLimits': 5}, 'with a limit field in the request')):
    body = {'domain': 'example.test', 'username': 'User', 'passwordByPass': 'x'}
    body.update(extra)
    fn, ran, opened = build('submitEmailCreation', method_source('submitEmailCreation'), body)
    result = fn()
    check('submitEmailCreation %s creates the account and runs and writes nothing else' % label, (result, ran, opened), ({'status': 1, 'createEmailStatus': 1, 'error_message': 'None'}, [], []))

fn, ran, opened = build('getEmailsForDomain', method_source('getEmailsForDomain'), {'domain': 'example.test'})
result = fn()
rows = json.loads(result['data'])
check('getEmailsForDomain lists every account with id, address and disk use', (result['status'], [sorted(r) for r in rows], [r['email'] for r in rows]), (1, [['DiskUsage', 'email', 'id']] * 2, ['a@example.test', 'b@example.test']))
check('getEmailsForDomain runs no command for the rows', ran, [])

# controls: the old limit step, put back, would be caught
OLD_STEP = ("            EmailLimits = data.get('EmailLimits', -1)\n            if EmailLimits != -1:\n"
            "                ProcessUtilities.outputExecutioner('limit step')\n")
src = method_source('submitEmailCreation')
anchor = "        if result[0] == 1:\n"
assert src.count(anchor) == 1
fn, ran, opened = build('submitEmailCreation', src.replace(anchor, anchor + OLD_STEP), {'domain': 'example.test', 'username': 'User', 'passwordByPass': 'x', 'EmailLimits': 5})
fn()
check('control: with a limit step put back the harness sees the command', ran, [('limit step',)])
src = method_source('getEmailsForDomain')
anchor = "        for items in emails:\n"
assert src.count(anchor) == 1
fn, ran, opened = build('getEmailsForDomain', src.replace(anchor, anchor + "            ProcessUtilities.outputExecutioner('row command')\n"), {'domain': 'example.test'})
fn()
check('control: with a per row command put back the harness sees one per row', len(ran), 2)

for rel in ('mailServer/views.py', 'mailServer/urls.py', 'mailServer/mailserverManager.py', 'plogical/mailUtilities.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar and has no carriage returns' % rel, (parsed, b'\r' in open(os.path.join(ROOT, rel), 'rb').read()), (True, False))

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
