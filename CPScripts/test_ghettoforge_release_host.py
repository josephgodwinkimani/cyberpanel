"""Tests that the mail server installers fetch the GhettoForge release package for AlmaLinux 8 and 9 from mirror.ghettoforge.net.
The old host mirror.ghettoforge.org no longer serves packages and the pinned AlmaLinux 8 path does not exist on the new host, so the
AlmaLinux 8 command in mailServer/mailserverManager.py uses the gf-release-latest name the other installers use. Only the commands that
download the package change: the CentOS 7 command and everything around these lines stay as they were.
Run: python3 CPScripts/test_ghettoforge_release_host.py"""
import ast
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


def lines_with(path, needle):
    text = open(os.path.join(ROOT, path), encoding='utf-8').read()
    return [l.strip() for l in text.splitlines() if needle in l]


NEW = 'https://mirror.ghettoforge.net/distributions/gf/gf-release-latest.gf.%s.noarch.rpm'
EL9 = "command = 'dnf --nogpg install -y " + NEW % 'el9' + "'"
EL8 = "command = 'dnf --nogpg install -y " + NEW % 'el8' + "'"
EL7 = "command = 'yum --nogpg install https://mirror.ghettoforge.org/distributions/gf/gf-release-latest.gf.el7.noarch.rpm -y'"

check('install/install.py downloads the el9 and el8 release packages from the new host', lines_with('install/install.py', 'ghettoforge'), [EL9, EL8])
check('plogical/mailUtilities.py downloads the el9 and el8 packages from the new host and leaves the CentOS 7 command as it was',
      lines_with('plogical/mailUtilities.py', 'ghettoforge'), [EL7, EL9, EL8])
check('mailServer/mailserverManager.py downloads the el8 package under the latest name from the new host', lines_with('mailServer/mailserverManager.py', 'ghettoforge'), [EL8])

pattern = re.compile(r"^command = 'dnf --nogpg install -y https://mirror[.]ghettoforge[.]net/distributions/gf/gf-release-latest[.]gf[.](el[89])[.]noarch[.]rpm'$")
found = [l for p in ('install/install.py', 'plogical/mailUtilities.py', 'mailServer/mailserverManager.py') for l in lines_with(p, 'ghettoforge.net')]
check('every changed command has the same shape: dnf, el8 or el9, the latest package name, the new host', all(pattern.match(l) for l in found), True)
check('five commands now use the new host', len(found), 5)

remaining = {p: len(lines_with(p, 'mirror.ghettoforge.org')) for p in ('install/install.py', 'plogical/mailUtilities.py', 'mailServer/mailserverManager.py')}
check('the old host remains only in the CentOS 7 command of mailUtilities.py', remaining, {'install/install.py': 0, 'plogical/mailUtilities.py': 1, 'mailServer/mailserverManager.py': 0})

# the three files still hold the same installer logic around the changed lines
for path, anchors in (('install/install.py', ("command = 'dnf install --enablerepo=gf-plus postfix3 postfix3-mysql -y'",)),
                      ('plogical/mailUtilities.py', ("command = 'dnf install --enablerepo=gf-plus postfix3 postfix3-mysql -y'", "command = 'yum install --enablerepo=gf-plus -y postfix3 postfix3-ldap postfix3-mysql postfix3-pcre'")),
                      ('mailServer/mailserverManager.py', ("command = 'dnf install --enablerepo=gf-plus postfix3 postfix3-mysql -y'",))):
    text = open(os.path.join(ROOT, path), encoding='utf-8').read()
    check('%s still installs postfix3 from the gf-plus repository after the release package' % path, all(a in text for a in anchors), True)

# control: the old commands would fail the checks above
old_lines = [l.replace('mirror.ghettoforge.net', 'mirror.ghettoforge.org') for l in found]
check('control: with the old host the shape check would fail', all(pattern.match(l) for l in old_lines), False)
old_pinned = "https://mirror.ghettoforge.org/distributions/gf/el/8/gf/x86_64/gf-release-8-11.gf.el8.noarch.rpm"
check('control: the old pinned el8 path is no longer present anywhere in the three files',
      any(old_pinned in open(os.path.join(ROOT, p), encoding='utf-8').read() for p in ('install/install.py', 'plogical/mailUtilities.py', 'mailServer/mailserverManager.py')), False)

for path in ('install/install.py', 'plogical/mailUtilities.py', 'mailServer/mailserverManager.py'):
    raw = open(os.path.join(ROOT, path), 'rb').read()
    try:
        ast.parse(raw, feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar and has no carriage returns' % path, (parsed, b'\r' in raw), (True, False))

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
