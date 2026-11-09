"""Tests that the sidebar link that opened the external platform site is gone from the base template while every other sidebar entry that no other
change touches is still there (the Community link next to it keeps its address), the page markup stays balanced (anchors, list items, lists, icons,
spans and the template block tags) and nothing else in the tree refers to the removed entry. Run: python3 CPScripts/test_connect_sidebar_link_removed.py"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REL = 'baseTemplate/templates/baseTemplate/index.html'

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def balance(src):
    out = {}
    for t in ('a', 'li', 'ul', 'i', 'span'):
        out[t] = (len(re.findall(r'<%s[\s>]' % t, src)), len(re.findall(r'</%s>' % t, src)))
    for t in ('if', 'block', 'with'):
        out['{% ' + t + ' %}'] = (len(re.findall(r'{%\s*' + t + r'\b', src)), len(re.findall(r'{%\s*end' + t + r'\b', src)))
    return {k: v[0] == v[1] for k, v in out.items()}


SRC = open(os.path.join(ROOT, REL), encoding='utf-8').read()
HOST = 'platform.cyber' + 'persons'
ID = 'sidebar-menu-item-' + 'connect'
check('the entry and its address are gone from the base template', (ID in SRC, HOST in SRC), (False, False))
ids = re.findall(r'id="(sidebar-menu-item-[a-z0-9-]+)"', SRC)
KEEP = ['server-ip-address', 'dashboard', 'version-management', 'design', 'community', 'users', 'websites', 'packages', 'databases', 'dns', 'email', 'ftp', 'tuning',
        'server-status', 'php', 'logs', 'security', 'mail-settings', 'manage-services', 'plugins']
check('every other sidebar entry that no other change touches is still there', [k for k in KEEP if 'sidebar-menu-item-' + k not in ids], [])
check('the entries keep their order around the removed one', [i for i in ids if i in ('sidebar-menu-item-design', 'sidebar-menu-item-community', 'sidebar-menu-item-users')],
      ['sidebar-menu-item-design', 'sidebar-menu-item-community', 'sidebar-menu-item-users'])
check('the Community link still opens its own address', 'href="https://go.cyberpanel.net/community"' in SRC, True)
check('the markup is balanced', balance(SRC), {'a': True, 'li': True, 'ul': True, 'i': True, 'span': True, '{% if %}': True, '{% block %}': True, '{% with %}': True})
check('control: the balance check sees a missing closing tag', balance(SRC.replace('</span>', '', 1))['span'], False)

SKIP = ('.git', 'node_modules', 'locale')
refs = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(('.py', '.js', '.css', '.html')) and not f.startswith('test_') and not f.endswith('.min.js') and not f.endswith('.min.css'):
            if ID in open(os.path.join(base, f), encoding='utf-8', errors='replace').read():
                refs.append(os.path.relpath(os.path.join(base, f), ROOT).replace(os.sep, '/'))
check('no script or style names the removed entry', sorted(refs), [])
check('the base template has no carriage returns', b'\r' in open(os.path.join(ROOT, REL), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
