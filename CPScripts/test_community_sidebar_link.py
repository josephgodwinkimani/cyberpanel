"""Tests that the Community entry of the sidebar in the base template opens the wiki of the fork and nothing else changed around it: the entry still
opens in a new tab, keeps its id, icon and label, and no link to the old address is left. (The page header has no Community button any more, see test_header_toolbar_buttons.py.)
The template is only read. Run: python3 CPScripts/test_community_sidebar_link.py"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REL = 'baseTemplate/templates/baseTemplate/index.html'
WIKI = 'https://github.com/josephgodwinkimani/cyberpanel/wiki'
OLD = 'https://go.cyberpanel.net/community'

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def sidebar_anchor(src):
    """The opening tag of the sidebar entry (attributes only), or None."""
    m = re.search(r'<a id="sidebar-menu-item-community"([^>]*)>', src)
    return m.group(1) if m else None


def problems(src):
    out = []
    tag = sidebar_anchor(src)
    if tag is None:
        return ['the sidebar entry is missing']
    if 'href="%s"' % WIKI not in tag:
        out.append('the sidebar entry does not open the wiki')
    if 'target="_blank"' not in tag:
        out.append('the sidebar entry does not open in a new tab')
    return out


SRC = open(os.path.join(ROOT, REL), encoding='utf-8').read()
check('the sidebar Community entry opens the wiki of the fork in a new tab', problems(SRC), [])
check('the sidebar entry keeps its icon and label', all(x in SRC for x in ('icon-comments-o', '<span>{% trans "Community" %}</span>')), True)
check('exactly one sidebar Community entry', len(re.findall(r'id="sidebar-menu-item-community"', SRC)), 1)
check('the old address is not in the template any more', OLD in SRC, False)
check('the template has no carriage returns', b'\r' in open(os.path.join(ROOT, REL), 'rb').read(), False)
check('control: the old address on the sidebar entry is reported', len(problems(SRC.replace(WIKI, OLD, 1))) > 0, True)
check('control: a missing new tab target is reported', len(problems(SRC.replace('id="sidebar-menu-item-community" target="_blank"', 'id="sidebar-menu-item-community"', 1))) > 0, True)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
