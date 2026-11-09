"""Tests that the link that opened the external mail test page from the Create Email Account page is gone, the heading and the loading image beside it
stay, the rest of the page is unchanged in structure (anchors and the other tags keep their balance, the account form and its Postfix switch are still
there) and nothing else in the tree sends visitors to that page. Run: python3 CPScripts/test_email_delivery_test_link_removed.py"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REL = 'mailServer/templates/mailServer/createEmailAccount.html'

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def pairs(src, tags):
    return {t: (len(re.findall(r'<%s[\s>]' % t, src)), len(re.findall(r'</%s>' % t, src))) for t in tags}


SRC = open(os.path.join(ROOT, REL), encoding='utf-8').read()
HOST = 'platform.cyber' + 'persons'
PAGE = 'Mail' + 'Tester'
check('the link and its address are gone', (HOST in SRC, PAGE in SRC, 'Test Email Delivery' in SRC), (False, False, False))
head = re.search(r'<h3 class="content-box-header">(.*?)</h3>', SRC, re.S)
check('the heading keeps its title and the loading image', (bool(head), ' '.join(head.group(1).split()) if head else None),
      (True, '{% trans "Create Email Account" %} <img ng-hide="emailLoading" src="{% static \'images/loading.gif\' %}">'))
check('the loading image is still closed on its own and the anchors balance', (pairs(SRC, ('a', 'h3', 'h2', 'div'))['a'], pairs(SRC, ('h3',))['h3'], pairs(SRC, ('div',))['div']), ((1, 1), (2, 2), (24, 24)))
check('the Postfix switch and the account form controller are still on the page', ('managePostfix' in SRC, 'ng-controller="createEmailAccount"' in SRC), (True, True))
check('control: the anchor count sees a missing closing tag', pairs(SRC.replace('</a>', '', 1), ('a',))['a'], (1, 0))

SKIP = ('.git', 'node_modules', 'locale')
refs = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(('.py', '.js', '.html')) and not f.startswith('test_') and not f.endswith('.min.js'):
            if PAGE in open(os.path.join(base, f), encoding='utf-8', errors='replace').read():
                refs.append(os.path.relpath(os.path.join(base, f), ROOT).replace(os.sep, '/'))
check('nothing else sends visitors to that page', sorted(refs), [])
check('the page has no carriage returns', b'\r' in open(os.path.join(ROOT, REL), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
