"""Tests that the wildcard SSL add-on is removed without breaking the free SSL pages and the free SSL issuing path: its page and issue views,
two routes, template, JavaScript controller, sidebar entry, issue step with its command line branch, module and the acme set up helper
that opened the DNS server web API on every address are gone. The free issuing function used to import the add-on module at its top, so
the important checks are that nothing in the tree imports that module any more and that the free function runs when the module cannot be
imported. The free views and helpers are pinned by hash. Names are built here so this file does not name the add-on. Needs node for the
script syntax check (reported as skipped when it is missing).
Run: python3 CPScripts/test_wildcard_ssl_addon_removed.py"""
import ast
import hashlib
import importlib.abc
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


MOD = 'ssl' + 'v2'
V2_VIEWS = ['v2Manage' + 'SSL', 'v2Issue' + 'SSL']
VIEWS, URLS, JS, INDEX = read('manageSSL/views.py'), read('manageSSL/urls.py'), read('manageSSL/static/manageSSL/manageSSL.js'), read('baseTemplate/templates/baseTemplate/index.html')
SSLU, VHU, DNSU = read('plogical/sslUtilities.py'), read('plogical/virtualHostUtilities.py'), read('plogical/dnsUtilities.py')


def funcs(src, scope=None):
    tree = ast.parse(src)
    body = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == scope).body if scope else tree.body
    return {n.name: n for n in body if isinstance(n, ast.FunctionDef)}


def digest(src, node):
    return hashlib.sha256(ast.get_source_segment(src, node).encode()).hexdigest()[:16]


views = funcs(VIEWS)
check('the two add-on views are gone', sorted(set(V2_VIEWS) & set(views)), [])
PINNED = {'loadSSLHome': '470166a0f8a1d91f', 'manageSSL': '9b43c037a9f98508', 'issueSSL': '7cd4282bb54325ad', 'sslForHostName': 'f5d89b045b6239b5',
          'obtainHostNameSSL': 'a89203c4f4c3f01c', 'sslForMailServer': 'f2bce11a858bf327', 'obtainMailServerSSL': '321c4efa3e87466e'}
check('the seven free SSL views are exactly as they were', {n: digest(VIEWS, views[n]) if n in views else None for n in PINNED}, PINNED)


# routes
def routes(source):
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ('path', 're_path'):
            view = n.args[1]
            out.append((n.args[0].value, view.attr if isinstance(view, ast.Attribute) else None))
    return out


table = routes(URLS)
check('no route points at a view that does not exist', [r for r in table if r[1] not in views], [])
check('the seven free routes are kept in their order', [r[0] for r in table], ['', 'manageSSL', 'issueSSL', 'sslForHostName', 'obtainHostNameSSL', 'sslForMailServer', 'obtainMailServerSSL'])
bad = URLS.replace("    path('manageSSL'", "    path('x', views.%s, name='x'),\n    path('manageSSL'" % V2_VIEWS[0])
check('control: a route put back is reported as dangling', [r[1] for r in routes(bad) if r[1] not in views], [V2_VIEWS[0]])

# the add-on module is gone and nothing imports it
check('the add-on module is gone', os.path.exists(os.path.join(ROOT, 'plogical/' + MOD + '.py')), False)


def importers(source):
    found = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            found += [a.name for a in n.names if a.name in ('plogical.' + MOD, MOD)]
        if isinstance(n, ast.ImportFrom):
            if n.module in ('plogical.' + MOD, MOD):
                found.append(n.module)
            if n.module == 'plogical' and any(a.name == MOD for a in n.names):
                found.append('plogical.' + MOD)
    return found


hits, scanned = [], 0
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f.endswith('.py') and '.bak' not in f:
            scanned += 1
            try:
                got = importers(open(os.path.join(base, f), encoding='utf-8', errors='replace').read())
            except SyntaxError:
                continue
            hits += [(os.path.relpath(os.path.join(base, f), ROOT), g) for g in got]
check('python files were scanned across the tree', scanned > 300, True)
check('no python file imports the removed module (a leftover import would break the free issuing path)', hits, [])
check('control: the import scan reports an import inside a function', importers('def f():\n    from plogical.%s import sslUtilities as x\n' % MOD), ['plogical.' + MOD])

# the free issuing function runs when the removed module cannot be imported
sslu = funcs(SSLU, 'sslUtilities')
node = sslu['obtainSSLForADomain']
source = ast.get_source_segment(SSLU, node).replace('\n' + ' ' * node.col_offset, '\n')


class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == 'plogical.' + MOD:
            raise ImportError('module removed: ' + name)
        return None


def run_free(code):
    plogical = types.ModuleType('plogical')
    plogical.__path__ = []
    acl = types.ModuleType('plogical.acl')
    acl.ACLManager = type('ACLManager', (), {})
    saved = {k: sys.modules.get(k) for k in ('plogical', 'plogical.acl')}
    sys.modules['plogical'], sys.modules['plogical.acl'] = plogical, acl
    sys.meta_path.insert(0, Blocker())
    try:
        ns = {'sslUtilities': types.SimpleNamespace(CheckIfSSLNeedsToBeIssued=lambda v: 0, ISSUE_SSL=1)}
        exec(code, ns)
        return ns['obtainSSLForADomain']('example.test', 'a@example.test', '/x')
    except BaseException as exc:
        return '%s: %s' % (type(exc).__name__, exc)
    finally:
        sys.meta_path.pop(0)
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


check('the free issuing function runs and returns 1 for a domain that already has SSL while the removed module cannot be imported', run_free(source), 1)
old_import = '    from plogical.%s import sslUtilities as x\n' % MOD
anchor = '    from plogical.acl import ACLManager\n'
assert source.count(anchor) == 1
check('control: with the import put back the same function fails exactly like this', run_free(source.replace(anchor, anchor + old_import)), 'ImportError: module removed: plogical.' + MOD)
check('the free issuing function and its neighbours are as expected (pinned)', {n: digest(SSLU, sslu[n]) for n in ('obtainSSLForADomain', 'CheckIfSSLNeedsToBeIssued', 'installSSLForDomain', 'PatchVhostConf')},
      {'obtainSSLForADomain': '23d4c2165ea10bbe', 'CheckIfSSLNeedsToBeIssued': 'b7bc80f7ff6199a1', 'installSSLForDomain': '20460231345ab085', 'PatchVhostConf': '15befce10a855c4b'})

# the issue step, the command line and the DNS server set up
vhu = funcs(VHU, 'virtualHostUtilities')
check('the add-on issue step is gone and the free one is unchanged', ('issue' + 'SSL' + 'v2' in vhu, digest(VHU, vhu['issueSSL'])), (False, '8c8a6b0f35c1bc0f'))
main_src = VHU.split('def main')[1]
check('the command line has no branch for the add-on step and keeps the free one', (('issue' + 'SSL' + 'v2') in main_src, 'args.function == "issueSSL"' in main_src), (False, True))
dns = funcs(DNSU, 'DNS')
check('the acme set up of the DNS server web API is gone and the free DNS helpers are kept', ('ConfigurePowerDNSIn' + 'Acme' in dns, [n for n in ('createDNSRecord', 'getDNSZones', 'deleteDNSRecord') if n not in dns]), (False, []))
check('no python file writes the open web API settings of the DNS server any more', [], [os.path.relpath(os.path.join(b, f), ROOT) for b, ds, fs in os.walk(ROOT) for f in fs
      if f.endswith('.py') and '.bak' not in f and not f.startswith('test_') and 'webserver-allow' + '-from' in open(os.path.join(b, f), encoding='utf-8', errors='replace').read() and '.git' not in b])

# the rest of the tree
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
defined = set()
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f == 'urls.py':
            defined |= {r[1] for r in routes(open(os.path.join(base, f), encoding='utf-8').read()) if r[1]}
        # the free per-site SSL page keeps its own names
leftovers, templates = [], 0
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f.endswith('.html') and '.bak' not in f:
            templates += 1
            for line in open(os.path.join(base, f), encoding='utf-8', errors='replace').read().split('\n'):
                if not line.lstrip().startswith('{#'):
                    leftovers += [(os.path.relpath(os.path.join(base, f), ROOT), m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) in V2_VIEWS]
check('the removed route names exist nowhere', sorted(set(V2_VIEWS) & defined), [])
check('no template reverses a removed route', leftovers, [])
check('the templates were scanned across the tree', templates > 100, True)
check('the add-on template is gone and the free ones are kept', (os.path.exists(os.path.join(ROOT, 'manageSSL/templates/manageSSL/' + V2_VIEWS[0] + '.html')), os.path.exists(os.path.join(ROOT, 'manageSSL/templates/manageSSL/manageSSL.html'))), (False, True))
check('the sidebar has no entry for the add-on and keeps the free SSL entries', ((V2_VIEWS[0]) not in INDEX, "url 'manageSSL'" in INDEX, "url 'sslForHostName'" in INDEX, "url 'sslForMailServer'" in INDEX), (True, True, True, True))
sample = "<a href=\"{% url '" + V2_VIEWS[0] + "' %}\">x</a>"
check('control: the template check would report a left-over reverse', [m.group(1) for m in URL_TAG.finditer(sample) if m.group(1) in V2_VIEWS], [V2_VIEWS[0]])

# script
controllers = re.findall(r"^app\.controller\('([A-Za-z]+)'", JS, flags=re.M)
check('the add-on controller is gone and the three free ones are kept', sorted(controllers), ['sslIssueCtrl', 'sslIssueForHostNameCtrl', 'sslIssueForMailServer'])
check('the script no longer calls the removed endpoint', ('/manageSSL/' + V2_VIEWS[1]) in JS, False)
node_bin = shutil.which('node')
if node_bin:
    check('manageSSL.js is valid JavaScript', subprocess.run([node_bin, '--check', os.path.join(ROOT, 'manageSSL/static/manageSSL/manageSSL.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

for rel in ('manageSSL/views.py', 'manageSSL/urls.py', 'plogical/virtualHostUtilities.py', 'plogical/sslUtilities.py', 'plogical/dnsUtilities.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar and has no carriage returns' % rel, (parsed, b'\r' in open(os.path.join(ROOT, rel), 'rb').read()), (True, False))

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
