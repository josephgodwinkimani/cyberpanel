"""Tests that Upgrade.installDNS_CyberPanelACMEFile (plogical/upgrade.py) creates the folder /root/.acme.sh when it is missing. The function copied a file
into that folder without creating it, so on a server that never issued a certificate through the panel the copy failed at the end of the upgrade and the
whole script took its restore path. The real function is cut out of the source and run with its paths moved into a temporary folder: nothing outside it is
touched. Run: python3 CPScripts/test_upgrade_acme_folder_created.py"""
import ast
import os
import shutil
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


def run(source, preexisting_folder):
    """Run the function of the given source with /root/.acme.sh and /usr/local/CyberCP moved into a temporary folder. Returns (error or None, state)."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Upgrade')
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'installDNS_CyberPanelACMEFile')
    func.decorator_list = []
    tmp = tempfile.mkdtemp()
    acme = os.path.join(tmp, 'root', '.acme.sh')
    panel = os.path.join(tmp, 'CyberCP', 'install')
    os.makedirs(panel)
    open(os.path.join(panel, 'dns_cyberpanel.sh'), 'w').write('#!/bin/sh\necho dns\n')
    if preexisting_folder:
        os.makedirs(acme)
        open(os.path.join(acme, 'dns_cyberpanel.sh'), 'w').write('old copy')
    commands = []

    class FakeUpgrade:
        @staticmethod
        def executioner(command, *args):
            commands.append(command)

    posix = lambda path: path.replace(chr(92), '/')
    source_text = ast.get_source_segment(source, func).replace('/root/.acme.sh', posix(acme)).replace('/usr/local/CyberCP', posix(os.path.join(tmp, 'CyberCP')))
    ns = {'os': os, 'shutil': shutil, 'Upgrade': FakeUpgrade}
    code = '\n'.join(l[4:] if l.startswith('    ') else l for l in source_text.splitlines())
    exec(compile(code, '<func>', 'exec'), ns)
    error = None
    try:
        ns['installDNS_CyberPanelACMEFile']()
    except BaseException as exc:
        error = type(exc).__name__
    copied = os.path.exists(os.path.join(acme, 'dns_cyberpanel.sh'))
    content = open(os.path.join(acme, 'dns_cyberpanel.sh')).read() if copied else None
    shutil.rmtree(tmp)
    return error, (copied, content, len(commands))


error, state = run(SRC, preexisting_folder=False)
check('the folder is missing: the file is still installed and no error', (error, state[0], state[1]), (None, True, '#!/bin/sh\necho dns\n'))
error, state = run(SRC, preexisting_folder=True)
check('the folder exists with an old copy: the old copy is replaced as before', (error, state[1]), (None, '#!/bin/sh\necho dns\n'))
check('both runs make the file executable through the same command', (state[2],), (1,))
old_source = SRC.replace("        os.makedirs(os.path.dirname(filePath), exist_ok=True)\n", '')
error, state = run(old_source, preexisting_folder=False)
check('control: without the new line a missing folder fails the copy', error, 'FileNotFoundError')
check('plogical/upgrade.py has no carriage returns', b'\r' in open(PATH, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
