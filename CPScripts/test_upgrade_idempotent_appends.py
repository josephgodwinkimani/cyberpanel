"""Tests that the panel upgrade (plogical/upgrade.py) no longer appends the same lines to /etc/fstab and /usr/lib/sysctl.d/50-default.conf every time it
runs. It used to add another proc line with hidepid=2 to fstab and two more fs.protected_* lines to the sysctl file on every run. The three helpers are cut
out of the source and run on files in a temporary folder; nothing outside it is touched. Run: python3 CPScripts/test_upgrade_idempotent_appends.py"""
import ast
import os
import sys
import tempfile
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATH = os.path.join(ROOT, 'plogical', 'upgrade.py')
SRC = open(PATH, encoding='utf-8').read()

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def load(source):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Upgrade')
    names = ('fstab_has_proc_hidepid', 'sysctl_has_setting', 'append_line_unless')
    funcs = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    module = ast.Module(body=[ast.ClassDef(name='Upgrade', bases=[], keywords=[], body=funcs, decorator_list=[])], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, '<upgrade>', 'exec'), ns)
    return ns['Upgrade'], sorted(f.name for f in funcs)


U, found = load(SRC)
check('the three helpers exist', found, ['append_line_unless', 'fstab_has_proc_hidepid', 'sysctl_has_setting'])

PROC = 'proc    /proc        proc        defaults,hidepid=2    0 0\n'
FSTAB = '/dev/sda1 / ext4 defaults 0 1\nUUID=abc /boot ext4 defaults 0 2\n'

tmp = tempfile.mkdtemp()
fstab = os.path.join(tmp, 'fstab')
open(fstab, 'w').write(FSTAB)
first = U.append_line_unless(fstab, PROC, U.fstab_has_proc_hidepid)
second = U.append_line_unless(fstab, PROC, U.fstab_has_proc_hidepid)
third = U.append_line_unless(fstab, PROC, U.fstab_has_proc_hidepid)
check('fstab: the proc line is added once and never again', (first, second, third, open(fstab).read().count('hidepid=2')), (True, False, False, 1))
check('fstab: the other lines are untouched and the new line is last', open(fstab).read(), FSTAB + PROC)

nofinal = os.path.join(tmp, 'fstab2')
open(nofinal, 'w').write('/dev/sda1 / ext4 defaults 0 1')
U.append_line_unless(nofinal, PROC, U.fstab_has_proc_hidepid)
check('fstab: a file without a final newline does not get its last line glued to the new one', open(nofinal).read(), '/dev/sda1 / ext4 defaults 0 1\n' + PROC)

for text, want, name in ((PROC, True, 'a hidepid proc line'), ('proc /proc proc defaults,hidepid=2 0 0', True, 'a hidepid proc line with single spaces and no newline'),
                         ('# proc /proc proc hidepid=2 0 0\n', False, 'a commented proc line'), ('proc /proc proc defaults 0 0\n', False, 'a proc line without hidepid'),
                         ('tmpfs /tmp tmpfs hidepid=2 0 0\n', False, 'hidepid on another mount'), ('', False, 'an empty file')):
    check('fstab test: ' + name, U.fstab_has_proc_hidepid(text), want)

sysctl = os.path.join(tmp, '50-default.conf')
open(sysctl, 'w').write('kernel.sysrq = 16\nfs.protected_hardlinks = 1\n')
for key in ('fs.protected_hardlinks', 'fs.protected_symlinks'):
    U.append_line_unless(sysctl, '%s = 1\n' % key, lambda text, k=key: U.sysctl_has_setting(text, k, '1'))
for key in ('fs.protected_hardlinks', 'fs.protected_symlinks'):
    U.append_line_unless(sysctl, '%s = 1\n' % key, lambda text, k=key: U.sysctl_has_setting(text, k, '1'))
check('sysctl: only the missing setting is added and a second run adds nothing', open(sysctl).read(), 'kernel.sysrq = 16\nfs.protected_hardlinks = 1\nfs.protected_symlinks = 1\n')
check('sysctl test: spaces, comments and a different value', (U.sysctl_has_setting('fs.protected_hardlinks=1\n', 'fs.protected_hardlinks', '1'), U.sysctl_has_setting('# fs.protected_hardlinks = 1\n', 'fs.protected_hardlinks', '1'),
      U.sysctl_has_setting('fs.protected_hardlinks = 0\n', 'fs.protected_hardlinks', '1'), U.sysctl_has_setting('fs.protected_hardlinks = 1 # on\n', 'fs.protected_hardlinks', '1')), (True, False, False, True))
missing = os.path.join(tmp, 'new.conf')
U.append_line_unless(missing, 'fs.protected_symlinks = 1\n', lambda text: False)
check('a file that does not exist yet is created', open(missing).read(), 'fs.protected_symlinks = 1\n')

# the code of the upgrade uses the helpers and no longer appends blindly
check('the upgrade no longer opens fstab or the sysctl file for appending', ("open('/etc/fstab', 'a')" in SRC, "open('/usr/lib/sysctl.d/50-default.conf', 'a')" in SRC), (False, False))
check('the upgrade appends through the helper in two places (fstab and the sysctl loop)', SRC.count('Upgrade.append_line_unless('), 2)
check('control: the old way (append every time) would add a second line', (lambda p: (open(p, 'w').write(FSTAB + PROC), open(p, 'a').write(PROC), open(p).read().count('hidepid=2'))[2])(os.path.join(tmp, 'old')), 2)
check('plogical/upgrade.py has no carriage returns', b'\r' in open(PATH, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
