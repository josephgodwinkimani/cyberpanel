"""Tests that Upgrade.upgrade_fail2ban (plogical/upgrade.py) never replaces an existing /etc/fail2ban/jail.local. The upgrade wrote its own jail.local over the
file of the administrator on every run (with a ban time and an ssh port of its own), which discarded custom jails and ports. A jail.local that does not exist
yet is still created with the same text as before. The real function is cut out of the source and run with /etc/fail2ban moved into a temporary folder and
fake package and service commands: nothing outside the folder is touched. Run: python3 CPScripts/test_upgrade_keeps_jail_local.py"""
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


def run(source, jail_text):
    """Run upgrade_fail2ban with /etc/fail2ban installed (jail_text None: no jail.local yet). Returns (jail.local text or None, log of fake commands)."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Upgrade')
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'upgrade_fail2ban')
    tmp = tempfile.mkdtemp()
    folder = os.path.join(tmp, 'fail2ban')
    os.makedirs(folder)
    jail = os.path.join(folder, 'jail.local')
    if jail_text is not None:
        open(jail, 'w').write(jail_text)
    log = []

    class FakeUpgrade:
        @staticmethod
        def stdOut(message, *a): log.append('out')

        @staticmethod
        def FindOperatingSytem(): return 'centos7'

        @staticmethod
        def executioner(command, *a): log.append(command)

        @staticmethod
        def install_missing_packages(*a): log.append('install_missing ' + a[0])

    fake_os = type('FakeOs', (), {'path': os.path, 'system': staticmethod(lambda c: log.append(c))})
    text = ast.get_source_segment(source, func).replace('/etc/fail2ban', folder.replace(chr(92), '/'))
    text = 'class Holder:' + chr(10) + '    @staticmethod' + chr(10) + '    ' + text + chr(10)
    ns = {'os': fake_os, 'Upgrade': FakeUpgrade, 'CENTOS7': 'centos7', 'CENTOS8': 'centos8'}
    exec(compile(text, '<func>', 'exec'), ns)
    ns['Holder'].upgrade_fail2ban()
    result = open(jail).read() if os.path.exists(jail) else None
    shutil.rmtree(tmp)
    return result, log


CUSTOM = '[DEFAULT]\nbantime = 24h\n\n[sshd]\nenabled = true\nport = 8123\n\n[nginx-http-auth]\nenabled = true\n'
result, log = run(SRC, CUSTOM)
check('an existing jail.local is left exactly as it is', result, CUSTOM)
check('the services are still enabled and started and the prerequisite check still runs', (any('enable fail2ban' in c for c in log), any('start fail2ban' in c for c in log), any(c.startswith('install_missing') for c in log)), (True, True, True))

result, log = run(SRC, None)
WRITTEN = '[DEFAULT]\n                bantime = 1h\n                findtime = 10m\n                maxretry = 5\n\n                [sshd]\n                enabled = true\n                port = 2200\n                '
check('a missing jail.local is created with the same text as before', result, WRITTEN)

old = SRC.replace("                if not os.path.exists('/etc/fail2ban/jail.local'):\n                    with open('/etc/fail2ban/jail.local', 'w') as config_file:\n                        config_file.write(", "                if True:\n                    with open('/etc/fail2ban/jail.local', 'w') as config_file:\n                        config_file.write(")
result, log = run(old, CUSTOM)
check('control: without the guard the custom file is replaced', result == CUSTOM, False)
check('plogical/upgrade.py has no carriage returns', b'\r' in open(PATH, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
