"""Tests that the toolbar on the right of the page header in the base template holds only the Logout button: the YouTube, Community and Support buttons
are gone while the logo, the sidebar toggle, the Logout button (with its address and id) and the Community entry of the sidebar are still there, and the
markup stays balanced. The template is only read. Run: python3 CPScripts/test_header_toolbar_buttons.py"""
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
    for t in ('a', 'i', 'span'):
        out[t] = len(re.findall(r'<%s[\s>]' % t, src)) == len(re.findall(r'</%s>' % t, src))
    return out


def toolbar(src):
    """The text of the toolbar div (from its opening tag to the closing comment), or ''."""
    m = re.search(r'<div ng-controller="loadAvg" id="header-nav-right">(.*?)<!-- #header-nav-right -->', src, re.S)
    return m.group(1) if m else ''


def buttons(src):
    """Header buttons outside template comments: a list of (id, href)."""
    text = re.sub(r'{%\s*comment\s*%}.*?{%\s*endcomment\s*%}', '', toolbar(src), flags=re.S)
    return [(m.group(1) or '', m.group(2)) for m in re.finditer(r'<a class="header-btn"(?: id="([^"]*)")?[^>]*?href="([^"]+)"', text, re.S)]


SRC = open(os.path.join(ROOT, REL), encoding='utf-8').read()
check('the toolbar exists', toolbar(SRC) != '', True)
check('the toolbar holds the Logout button only', buttons(SRC), [('logout-btn', "{% url 'logout' %}")])
check('no YouTube, support or Community address is in the toolbar', [w for w in ('youtube', 'go.cyberpanel.net', 'github.com') if w in toolbar(SRC)], [])
check('no toolbar icon of the removed buttons is left', [w for w in ('icon-youtube', 'icon-support', 'icon-comments"') if w in toolbar(SRC)], [])
check('the Logout button keeps its icon and title', ('icon-power-off' in toolbar(SRC), "trans 'Logout'" in toolbar(SRC)), (True, True))
check('the logo stays (big and small) and the sidebar toggle stays', (SRC.count('class="logo-content-big"'), SRC.count('class="logo-content-small"'), 'id="nav-toggle"' in SRC), (1, 2, True))
check('the sidebar Community entry stays and opens the wiki of the fork', re.search(r'id="sidebar-menu-item-community"[^>]*?href="https://github.com/josephgodwinkimani/cyberpanel/wiki"', SRC, re.S) is not None, True)
check('the markup is balanced', balance(SRC), {'a': True, 'i': True, 'span': True})
check('the template has no carriage returns', b'\r' in open(os.path.join(ROOT, REL), 'rb').read(), False)

# controls: damaged copies must be reported
extra = SRC.replace('<a class="header-btn" id="logout-btn"', '<a class="header-btn" target="_blank" href="https://go.cyberpanel.net/support" title="Support"><i class="glyph-icon icon-support"></i></a>\n<a class="header-btn" id="logout-btn"', 1)
check('control: a Support button put back is reported', len(buttons(extra)), 2)
check('control: a missing Logout button is reported', buttons(SRC.replace('id="logout-btn"', 'id="x"', 1)) == [('logout-btn', "{% url 'logout' %}")], False)
check('control: the balance check sees a missing closing tag', balance(SRC.replace('</span>', '', 1))['span'], False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
