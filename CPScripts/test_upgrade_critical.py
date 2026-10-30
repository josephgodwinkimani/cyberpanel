"""Tests plogical/upgradeCritical.py: the nightly package upgrade runs only when the marker file exists.
The real module is loaded from the file and its executioner is replaced by a recorder, so no package command runs
and no real path under /etc is touched. Run: python3 CPScripts/test_upgrade_critical.py"""
import ast
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'plogical', 'upgradeCritical.py')

spec = importlib.util.spec_from_file_location('upgrade_critical_under_test', SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
UC = mod.UpgradeCritical

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


recorded = []
UC.executioner = staticmethod(lambda command: recorded.append(command) or 1)

real_exists = os.path.exists
state = {'debian': False}


def fake_exists(path):
    if path == '/etc/lsb-release':
        return state['debian']
    return real_exists(path)


mod.os.path.exists = fake_exists

with tempfile.TemporaryDirectory() as tmp:
    marker = os.path.join(tmp, 'auto_upgrade_critical')
    check('the marker path is /etc/cyberpanel/auto_upgrade_critical', UC.AutoUpgradeMarker, '/etc/cyberpanel/auto_upgrade_critical')
    UC.AutoUpgradeMarker = marker

    # no marker: nothing runs on either family of systems
    for debian in (False, True):
        state['debian'] = debian
        recorded.clear()
        UC.UpgradeImportantPackages()
        check('no marker (%s): no command runs' % ('apt' if debian else 'yum'), recorded, [])

    recorded.clear()
    state['debian'] = False
    mod.main()
    check('main() without the marker runs no command', recorded, [])

    # marker present: the same commands as before run
    open(marker, 'w').close()
    state['debian'] = False
    recorded.clear()
    UC.UpgradeImportantPackages()
    check('marker present (yum): two commands in the original order', [c.split(' ')[:2] for c in recorded], [['yum', 'update'], ['yum', '-y']])
    check('marker present (yum): the package list is unchanged', recorded[1], 'yum -y upgrade pdns pdns-backend-mysql pure-ftpd postfix dovecot dovecot-mysql')

    state['debian'] = True
    recorded.clear()
    UC.UpgradeImportantPackages()
    check('marker present (apt): one command', len(recorded), 1)
    check('marker present (apt): it is the original apt-get only-upgrade command', recorded[0].startswith('DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade pdns-server pdns-backend-mysql'), True)

    # removing the marker turns it off again
    os.remove(marker)
    recorded.clear()
    UC.UpgradeImportantPackages()
    check('marker removed again: no command runs', recorded, [])

    # any existing path counts, including an empty directory (documented behaviour)
    os.mkdir(marker)
    recorded.clear()
    state['debian'] = False
    UC.UpgradeImportantPackages()
    check('a directory at the marker path also enables it', len(recorded), 2)

mod.os.path.exists = real_exists

with open(SOURCE, 'rb') as handle:
    source_bytes = handle.read()
try:
    ast.parse(source_bytes, feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('the module parses with the Python 3.9 grammar', parsed, True)
check('the file has no carriage returns', b'\r' in source_bytes, False)
check('the real marker path is not created by this test', real_exists('/etc/cyberpanel/auto_upgrade_critical') and 'unexpected', False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
