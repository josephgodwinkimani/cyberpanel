"""Tests that the whole-server file manager page (a paid add-on) is removed without touching the free per-site File Manager: its page
view, download view, two routes, template, sidebar entry and the script function only that page called are gone, no route or template
points at them, and the free views are byte for byte what they were (pinned by hash), including the admin only rule of the shared
controller. Needs node for the script syntax check (reported as skipped when it is missing).
Run: python3 CPScripts/test_file_manager_server_page_removed.py"""
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


PAGE_VIEW = 'FileManager' + 'Root'
DOWNLOAD = 'Root' + 'DownloadFile'
ROUTE = 'File' + 'manager'
TEMPLATE = 'baseTemplate/' + 'FileManager.html'
SIDEBAR_ID = 'sidebar-menu-item-' + 'root-file-' + 'manager'
VIEWS, URLS, JS, INDEX = read('filemanager/views.py'), read('filemanager/urls.py'), read('filemanager/static/filemanager/js/fileManager.js'), read('baseTemplate/templates/baseTemplate/index.html')

tree = ast.parse(VIEWS)
funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
check('the page view and the download view are gone', sorted({PAGE_VIEW, DOWNLOAD} & set(funcs)), [])
PINNED = {'loadFileManagerHome': '4a9a79ccc2065809', 'changePermissions': '02b6e9c6386d14f7', 'controller': 'cc1a314b497f1dd1',
          'upload': '275a5563d607c099', 'editFile': 'a277871a376e566c', 'downloadFile': 'b6c3479ebb77c1bb'}
got = {n: hashlib.sha256(ast.get_source_segment(VIEWS, funcs[n]).encode()).hexdigest()[:16] if n in funcs else None for n in PINNED}
check('the six free file manager views are exactly as they were', got, PINNED)
controller = ast.get_source_segment(VIEWS, funcs['controller'])
check('the shared controller still limits the empty domain name mode to administrators', ("if domainName == '':" in controller, "currentACL['admin'] == 1" in controller, "'FilemanagerAdmin'" in controller), (True, True, True))


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
check('the free routes are kept in their order with the per-site catch-all last', [r[2] for r in table], ['upload', 'changePermissions', 'controller', 'downloadFile', 'editFile', 'loadFileManagerHome'])
bad = URLS.replace("    path('<domain>'", "    path('x', views.%s, name='x'),\n    path('<domain>'" % PAGE_VIEW)
check('control: a route put back is reported as dangling', [r[1] for r in routes(bad) if r[1] not in funcs], [PAGE_VIEW])

# the rest of the tree
URL_TAG = re.compile(r"\{%\s*url\s+['\"]([A-Za-z0-9_:.-]+)['\"]")
defined = set()
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f == 'urls.py':
            defined |= {r[2] for r in routes(open(os.path.join(base, f), encoding='utf-8').read()) if r[2]}
check('the removed route names exist nowhere', ([n for n in (ROUTE, DOWNLOAD) if n in defined]), [])
leftovers, refs, templates = [], [], 0
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        rel = os.path.relpath(os.path.join(base, f), ROOT)
        if f.endswith('.html') and '.bak' not in f:
            templates += 1
            for line in open(os.path.join(base, f), encoding='utf-8', errors='replace').read().split('\n'):
                if not line.lstrip().startswith('{#'):
                    leftovers += [(rel, m.group(1)) for m in URL_TAG.finditer(line) if m.group(1) in (ROUTE, DOWNLOAD)]
        if f.endswith(('.py', '.html', '.js')) and '.bak' not in f and not f.startswith('test_') and not f.endswith('.min.js'):
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            for pat in (DOWNLOAD, '/filemanager/' + ROUTE, PAGE_VIEW):
                if pat in text:
                    refs.append((rel, pat))
check('no template reverses a removed route', leftovers, [])
check('the templates were scanned across the tree', templates > 100, True)
check('nothing names the removed endpoints, page view or download function (the Cloud API is removed in its own change)', [r for r in refs if not r[0].startswith('cloudAPI')], [])
name_refs = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f.endswith(('.py', '.html')) and '.bak' not in f and not f.startswith('test_'):
            if TEMPLATE in open(os.path.join(base, f), encoding='utf-8', errors='replace').read():
                name_refs.append(os.path.relpath(os.path.join(base, f), ROOT))
check('the removed template is named only by the database manager (a dead string handled in its own change)', name_refs, ['databases/databaseManager.py'])
check('the removed template is gone and the free per-site template is kept', (os.path.exists(os.path.join(ROOT, 'baseTemplate/templates/' + TEMPLATE)), os.path.exists(os.path.join(ROOT, 'filemanager/templates/filemanager/index.html'))), (False, True))
free_index = read('filemanager/templates/filemanager/index.html')
check('the free page uses the kept download function and nothing removed', ('downloadFile()' in free_index, DOWNLOAD in free_index), (True, False))

# sidebar
check('the sidebar has no entry for the page and keeps the neighbouring entries', (SIDEBAR_ID not in INDEX, ("url '" + ROUTE + "'") not in INDEX, "url 'MysqlManager'" in INDEX, 'sidebar-menu-item-cloudlinux' in INDEX), (True, True, True, True))
sample = "<a href=\"{% url '" + ROUTE + "' %}\">x</a>"
check('control: the template check would report a left-over reverse', [m.group(1) for m in URL_TAG.finditer(sample) if m.group(1) == ROUTE], [ROUTE])

# script
check('the script function only the removed page called is gone and the free ones are kept', (DOWNLOAD not in JS, '$scope.downloadFile = function' in JS, '$scope.changePermissions' in JS or 'changePermissionsLoading' in JS), (True, True, True))
node = shutil.which('node')
if node:
    check('fileManager.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'filemanager/static/filemanager/js/fileManager.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

for rel in ('filemanager/views.py', 'filemanager/urls.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
for rel in ('filemanager/views.py', 'filemanager/urls.py', 'filemanager/static/filemanager/js/fileManager.js', 'baseTemplate/templates/baseTemplate/index.html'):
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
