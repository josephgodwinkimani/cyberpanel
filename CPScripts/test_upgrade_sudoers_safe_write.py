"""Tests how the panel upgrade (plogical/upgrade.py) edits /etc/sudoers. The old code truncated the file, matched every line that contained the word wheel
(comments and restricted rules too, because the second part of its test was always true), and rewrote the file on every run. The new code removes only the
active default group rules, keeps comments and restricted rules, writes nothing when nothing changes and replaces the file in one step only after visudo has
accepted the new text. The real functions are cut out of the source and run on files in a temporary folder with a fake visudo: the real sudoers file is never
touched. Run: python3 CPScripts/test_upgrade_sudoers_safe_write.py"""
import ast
import os
import subprocess
import sys
import tempfile
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATH = os.path.join(ROOT, 'plogical', 'upgrade.py')
SRC = open(PATH, encoding='utf-8').read()
NL = chr(10)
TAB = chr(9)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + NL + '        wanted: %r' % (want,) + NL + '        got:    %r' % (got,))


def load(source, visudo_ok=True, ubuntu=False, record=None):
    """The three functions in a class, with visudo and the Ubuntu marker faked. Returns the class."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Upgrade')
    names = ('write_sudoers_checked', 'sudoers_without_default_rules', 'fixSudoers')
    funcs = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    module = ast.Module(body=[ast.ClassDef(name='Upgrade', bases=[], keywords=[], body=funcs, decorator_list=[])], type_ignores=[])
    ast.fix_missing_locations(module)
    record = record if record is not None else []

    class FakeSubprocess:
        DEVNULL = None

        @staticmethod
        def call(command, **kwargs):
            record.append(tuple(command))
            return 0 if visudo_ok else 1

    class FakeOs:
        path = type('P', (), {'exists': staticmethod(lambda p: ubuntu if p == '/etc/lsb-release' else os.path.exists(p))})
        chmod = staticmethod(lambda path, mode: None)  # a read only file cannot be removed on Windows, where this test may run
        remove = staticmethod(os.remove)
        replace = staticmethod(os.replace)

    ns = {'os': FakeOs, 'subprocess': FakeSubprocess}
    exec(compile(module, '<upgrade>', 'exec'), ns)
    cls_obj = ns['Upgrade']
    cls_obj.stdOut = staticmethod(lambda message, *a: record.append(message))
    cls_obj.executioner = staticmethod(lambda command, *a: record.append(command))
    return cls_obj


def run_fix(source, text, **kwargs):
    """Run fixSudoers on a temporary sudoers file holding text. Returns (file text after, record, replaced?)."""
    tmp = tempfile.mkdtemp()
    sudoers = os.path.join(tmp, 'sudoers')
    open(sudoers, 'w').write(text)
    before = os.stat(sudoers).st_ino
    record = []
    U = load(source.replace("path = '/etc/sudoers'", "path = %r" % sudoers.replace(chr(92), '/')), record=record, **kwargs)
    U.fixSudoers()
    after = open(sudoers).read()
    replaced = os.stat(sudoers).st_ino != before
    leftovers = os.listdir(tmp)
    return after, record, replaced, leftovers


SAMPLE = NL.join(['Defaults requiretty', '## Allow root to run any commands anywhere', 'root' + TAB + 'ALL=(ALL) ' + TAB + 'ALL', '',
                  '## Allows people in group wheel to run all commands', '%wheel' + TAB + 'ALL=(ALL)' + TAB + 'ALL', '## Same thing without a password',
                  '# %wheel' + TAB + 'ALL=(ALL)' + TAB + 'NOPASSWD: ALL', '%wheel ALL=(root) /usr/bin/systemctl status *', 'deploy ALL=(ALL) NOPASSWD: /usr/bin/rsync', '']) 
WANT = NL.join(['Defaults requiretty', '## Allow root to run any commands anywhere', 'root' + TAB + 'ALL=(ALL:ALL) ' + TAB + 'ALL', '',
                '## Allows people in group wheel to run all commands', '## Same thing without a password', '# %wheel' + TAB + 'ALL=(ALL)' + TAB + 'NOPASSWD: ALL',
                '%wheel ALL=(root) /usr/bin/systemctl status *', 'deploy ALL=(ALL) NOPASSWD: /usr/bin/rsync', ''])

# the sample file is read with readlines so every line keeps its newline: build the text accordingly
SAMPLE_TEXT, WANT_TEXT = SAMPLE, WANT
after, record, replaced, left = run_fix(SRC, SAMPLE_TEXT)
check('the active default wheel rule is removed, the root rule is written in the long form, everything else stays', after, WANT_TEXT)
check('visudo was asked to check the new text and the chsh command still runs', (any(c[:2] == ('visudo', '-cf') for c in record if isinstance(c, tuple)), 'chsh -s /bin/false cyberpanel' in record), (True, True))
check('no temporary file is left behind', left, ['sudoers'])

after2, record2, replaced2, left2 = run_fix(SRC, WANT_TEXT)
check('a second run on the result writes nothing (the file is not replaced, visudo is not needed)', (after2, replaced2, any(isinstance(c, tuple) for c in record2)), (WANT_TEXT, False, False))

after3, record3, replaced3, left3 = run_fix(SRC, SAMPLE_TEXT, visudo_ok=False)
check('when visudo refuses the new text the file stays exactly as it was', after3, SAMPLE_TEXT)
check('and nothing is left behind', left3, ['sudoers'])

UBUNTU = NL.join(['root ALL=(ALL:ALL) ALL', '%admin ALL=(ALL) ALL', '%sudo ALL=(ALL:ALL) ALL', '']) 
after4, record4, replaced4, left4 = run_fix(SRC, UBUNTU, ubuntu=True)
check('Ubuntu: only the sudo group rule is removed', after4, NL.join(['root ALL=(ALL:ALL) ALL', '%admin ALL=(ALL) ALL', '']))

# control: the old code removed every line that mentions wheel, comments and the restricted rule included
OLD_CONDITION = lambda line: line.find('wheel') > -1 and line.find('ALL=(ALL)')
removed_by_old = [l for l in SAMPLE_TEXT.split(NL) if OLD_CONDITION(l)]
check('control: the old condition would also have removed the comments and the restricted wheel rule', len(removed_by_old), 4)
FIX_SEGMENT = ast.get_source_segment(SRC, next(n for c in ast.parse(SRC).body if isinstance(c, ast.ClassDef) and c.name == 'Upgrade' for n in c.body if isinstance(n, ast.FunctionDef) and n.name == 'fixSudoers'))
check('fixSudoers no longer opens the sudoers file for writing', "'w')" in FIX_SEGMENT, False)
check('plogical/upgrade.py has no carriage returns', b'\r' in open(PATH, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
