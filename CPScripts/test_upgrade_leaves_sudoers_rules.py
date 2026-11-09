"""Tests that a panel upgrade (plogical/upgrade.py) leaves the sudo rules of an existing server alone. The upgrade removed the wheel group rules from
/etc/sudoers on every run, which takes away access an administrator may have granted since the installation. Upgrade.fixSudoers(editRules=False), the way
the upgrade now calls it, does not read or change the file but still runs the chsh command; the default (used by tests and any caller that asks for the
hardening) still edits it. The real function is cut out of the source and run on a temporary file: the real sudoers file is never touched.
Run: python3 CPScripts/test_upgrade_leaves_sudoers_rules.py"""
import ast
import os
import re
import sys
import tempfile
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATH = os.path.join(ROOT, 'plogical', 'upgrade.py')
SRC = open(PATH, encoding='utf-8').read()
NL = chr(10)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + NL + '        wanted: %r' % (want,) + NL + '        got:    %r' % (got,))


def run(arguments):
    """Run fixSudoers(*arguments) on a temporary sudoers file with a wheel rule. Returns (text of the file afterwards, record of fake commands, original text)."""
    tmp = tempfile.mkdtemp()
    sudoers = os.path.join(tmp, 'sudoers')
    original = NL.join(['root ALL=(ALL) ALL', '%wheel ALL=(ALL) ALL', ''])
    open(sudoers, 'w').write(original)
    record = []
    patched = SRC.replace("path = '/etc/sudoers'", 'path = %r' % sudoers.replace(chr(92), '/'))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(patched)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Upgrade')
    names = ('write_sudoers_checked', 'sudoers_without_default_rules', 'fixSudoers')
    funcs = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    module = ast.Module(body=[ast.ClassDef(name='Upgrade', bases=[], keywords=[], body=funcs, decorator_list=[])], type_ignores=[])
    ast.fix_missing_locations(module)

    class FakeSubprocess:
        DEVNULL = None

        @staticmethod
        def call(command, **kwargs):
            record.append(tuple(command))
            return 0

    class FakeOs:
        path = type('P', (), {'exists': staticmethod(lambda p: False if p == '/etc/lsb-release' else os.path.exists(p))})
        chmod = staticmethod(lambda path, mode: None)
        remove = staticmethod(os.remove)
        replace = staticmethod(os.replace)

    ns = {'os': FakeOs, 'subprocess': FakeSubprocess}
    exec(compile(module, '<upgrade>', 'exec'), ns)
    U = ns['Upgrade']
    U.stdOut = staticmethod(lambda message, *a: record.append(message))
    U.executioner = staticmethod(lambda command, *a: record.append(command))
    U.fixSudoers(*arguments)
    return open(sudoers).read(), record, original


after, record, original = run((False,))
check('with editRules=False the sudoers file is untouched', after, original)
check('and visudo is not run, but the chsh command still is', (any(isinstance(c, tuple) for c in record), 'chsh -s /bin/false cyberpanel' in record), (False, True))
after, record, original = run(())
check('the default still removes the active wheel rule (the hardening for a caller that asks for it)', after, NL.join(['root' + chr(9) + 'ALL=(ALL:ALL) ' + chr(9) + 'ALL', '']))
check('the upgrade calls it with editRules=False', SRC.count('Upgrade.fixSudoers(editRules=False)'), 1)
check('no other call of Upgrade.fixSudoers exists in the upgrade', len(re.findall(r'Upgrade\.fixSudoers\(', SRC)), 1)
check('plogical/upgrade.py has no carriage returns', b'\r' in open(PATH, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
