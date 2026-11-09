"""Tests that plogical/upgrade.py never upgrades an installed package while it installs the prerequisites of lscpd and Fail2Ban.
A plain yum or apt install of an installed package upgrades it (glibc, openssl, curl, gcc and fail2ban were upgraded on an older installation
that way) and the panel upgrade must not update operating system packages. Upgrade.install_missing_packages installs only the packages that
are not installed yet. The real functions are cut out of the source and run against a fake package database and a fake command runner:
no package tool is started and nothing is installed.
Run: python3 CPScripts/test_upgrade_install_missing_packages.py"""
import ast
import os
import sys
import types
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = open(os.path.join(ROOT, 'plogical', 'upgrade.py'), encoding='utf-8').read()

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


with warnings.catch_warnings():
    warnings.simplefilter('ignore')  # the file holds old regular expressions with plain backslashes, not part of this check
    TREE = ast.parse(SOURCE)

FUNCS = {}
for node in ast.walk(TREE):
    if isinstance(node, ast.ClassDef) and node.name == 'Upgrade':
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name in ('package_installed', 'install_missing_packages'):
                FUNCS[item.name] = item
check('both functions exist in the Upgrade class', sorted(FUNCS), ['install_missing_packages', 'package_installed'])

def static_problems(src):
    """Problems in the call sites of the source text (empty list when fine)."""
    out = []
    for old in ("command = 'yum -y install gcc gcc-c++ make autoconf glibc rcs'",
                "command = 'yum -y install pcre-devel openssl-devel expat-devel geoip-devel zlib-devel udns-devel which curl'",
                "command = 'yum -y install fail2ban'",
                "command = 'DEBIAN_FRONTEND=noninteractive apt-get -y install fail2ban'"):
        if old in src:
            out.append('still there: ' + old)
    for new in ("Upgrade.install_missing_packages('gcc gcc-c++ make autoconf glibc rcs', 'LSCPD Pre-reqs [one]')",
                "Upgrade.install_missing_packages('pcre-devel openssl-devel expat-devel geoip-devel zlib-devel udns-devel which curl',",
                "Upgrade.install_missing_packages('fail2ban', 'Install Fail2Ban')",
                "apt-get -y install --no-upgrade')"):
        if new not in src:
            out.append('missing: ' + new)
    return out



if len(FUNCS) != 2:
    check('the four unguarded install commands are gone and the helper is used', static_problems(SOURCE), [])
    print('----')
    print('%d of %d checks passed (the functions are missing, the behaviour checks were not run)' % (ok, total))
    sys.exit(1)



def make_upgrade(installed, install_ok=True):
    """Build a fake Upgrade class that holds the two real functions. installed is the set of package names the fake database knows."""
    log = {'commands': [], 'messages': [], 'queries': []}

    def fake_call(command, shell=False, stdout=None, stderr=None):
        log['queries'].append(command)
        kind, name = command.split()[0], command.split()[-1]
        if kind == 'rpm' and name in installed:
            return 0
        return 1  # dpkg is not there, and an unknown package is not installed

    fake_subprocess = types.SimpleNamespace(call=fake_call, DEVNULL=None)

    class Upgrade:
        @staticmethod
        def executioner(command, component, do_exit=0, shell=False):
            log['commands'].append((command, component))
            return install_ok

        @staticmethod
        def stdOut(message, do_exit=0):
            log['messages'].append(message)

    namespace = {'subprocess': fake_subprocess, 'Upgrade': Upgrade}
    for name in ('package_installed', 'install_missing_packages'):
        func = FUNCS[name]
        module = ast.Module(body=[ast.FunctionDef(name=func.name, args=func.args, body=func.body, decorator_list=[], returns=None, lineno=1, col_offset=0)], type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, '<' + name + '>', 'exec'), namespace)
        setattr(Upgrade, name, staticmethod(namespace[name]))
    return Upgrade, log


PRE_ONE = 'gcc gcc-c++ make autoconf glibc rcs'
PRE_TWO = 'pcre-devel openssl-devel expat-devel geoip-devel zlib-devel udns-devel which curl'

# everything installed: no install command, so nothing can be upgraded
U, log = make_upgrade(set(PRE_ONE.split()))
result = U.install_missing_packages(PRE_ONE, 'LSCPD Pre-reqs [one]')
check('all installed: no install command is run', log['commands'], [])
check('all installed: it reports success', result, True)
check('all installed: it says so', any('nothing to install' in m for m in log['messages']), True)

# one missing: only that one is passed on, the installed ones (glibc, gcc) never appear in the command
U, log = make_upgrade(set('gcc gcc-c++ make autoconf glibc'.split()))
U.install_missing_packages(PRE_ONE, 'LSCPD Pre-reqs [one]')
check('one missing: only the missing package is installed', log['commands'], [('yum -y install rcs', 'LSCPD Pre-reqs [one]')])

# several missing: they keep the order of the list
U, log = make_upgrade({'gcc', 'glibc', 'make'})
U.install_missing_packages(PRE_ONE, 'x')
check('several missing: the order of the list is kept and installed packages are left out', log['commands'][0][0], 'yum -y install gcc-c++ autoconf rcs')

# nothing installed: everything is installed
U, log = make_upgrade(set())
U.install_missing_packages(PRE_TWO, 'LSCPD Pre-reqs [two]')
check('nothing installed: the whole list is installed', log['commands'][0][0], 'yum -y install ' + PRE_TWO)

# the second list on an installation that has everything but one development package
U, log = make_upgrade(set(PRE_TWO.split()) - {'udns-devel'})
U.install_missing_packages(PRE_TWO, 'LSCPD Pre-reqs [two]')
check('second list: openssl-devel curl and which are not touched, udns-devel is installed', log['commands'], [('yum -y install udns-devel', 'LSCPD Pre-reqs [two]')])

# the failure of the install is reported
U, log = make_upgrade(set(), install_ok=False)
check('a failed install returns False', U.install_missing_packages('fail2ban', 'Install Fail2Ban'), False)

# an other package manager command
U, log = make_upgrade(set())
U.install_missing_packages('fail2ban', 'Install Fail2Ban', 'DEBIAN_FRONTEND=noninteractive apt-get -y install --no-upgrade')
check('the apt command keeps --no-upgrade', log['commands'][0][0], 'DEBIAN_FRONTEND=noninteractive apt-get -y install --no-upgrade fail2ban')

# the names are looked up as installed packages or provided names
U, log = make_upgrade({'glibc'})
U.install_missing_packages('glibc', 'x')
check('the installed check asks rpm for the name or what provides it', log['queries'][0], 'rpm -q --whatprovides glibc')


check('the four unguarded install commands are gone and the helper is used', static_problems(SOURCE), [])
mutated = SOURCE.replace("Upgrade.install_missing_packages('fail2ban', 'Install Fail2Ban')", "command = 'yum -y install fail2ban'")
check('control: putting the plain fail2ban install back is reported', len(static_problems(mutated)) > 0, True)
mutated = SOURCE.replace("Upgrade.install_missing_packages('gcc gcc-c++ make autoconf glibc rcs', 'LSCPD Pre-reqs [one]')", "command = 'yum -y install gcc gcc-c++ make autoconf glibc rcs'")
check('control: putting the plain install of glibc back is reported', len(static_problems(mutated)) > 0, True)

raw = open(os.path.join(ROOT, 'plogical', 'upgrade.py'), 'rb').read()
check('plogical/upgrade.py has no carriage returns', b'\r' in raw, False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
