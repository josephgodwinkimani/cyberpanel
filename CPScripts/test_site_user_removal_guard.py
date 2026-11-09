"""Tests the guard in plogical/vhost.py that decides whether the Linux account of a deleted website may be removed. Deleting a website ran
userdel -r -f on the account stored for it, and for an account like nobody (home directory /) that deleted the system's own folders (it can remove folders
such as /lib64). vhost.IsSiteUserSafeToRemove now allows only an ordinary website account, and both places that run userdel use it. The real function is
cut out of the source and run against a fake account database: nothing is deleted. Run: python3 CPScripts/test_site_user_removal_guard.py"""
import ast
import os
import sys
import types
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATH = os.path.join(ROOT, 'plogical', 'vhost.py')
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


def load(source, accounts):
    """The class attribute and the method of class vhost, run against a fake pwd holding the accounts {name: (uid, home)}."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'vhost')
    keep = [n for n in cls.body if (isinstance(n, ast.FunctionDef) and n.name == 'IsSiteUserSafeToRemove') or (isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'PROTECTED_SITE_USERS')]
    module = ast.Module(body=[ast.ClassDef(name='vhost', bases=[], keywords=[], body=keep, decorator_list=[])], type_ignores=[])
    ast.fix_missing_locations(module)

    def getpwnam(name):
        if name not in accounts:
            raise KeyError(name)
        uid, home = accounts[name]
        return types.SimpleNamespace(pw_uid=uid, pw_dir=home)

    ns = {'pwd': types.SimpleNamespace(getpwnam=getpwnam)}
    exec(compile(module, '<vhost>', 'exec'), ns)
    return ns['vhost']


ACCOUNTS = {'cresg8986': (1004, '/home/example.com'), 'siteuser': (1001, '/home/siteuser.org'), 'oldrange': (501, '/home/old.example'),
            'nobody': (65534, '/'), 'root': (0, '/root'), 'daemon': (2, '/sbin'), 'mysql': (27, '/var/lib/mysql'), 'lsadm': (996, '/usr/local/lsws'),
            'tricky': (1005, '/'), 'tricky2': (1006, '/home'), 'tricky3': (1007, '/home/../etc'), 'highid': (70000, '/home/high.example')}
V = load(SRC, ACCOUNTS)
safe = V.IsSiteUserSafeToRemove
check('ordinary website accounts may be removed', [safe(u) for u in ('cresg8986', 'siteuser', 'oldrange')], [True, True, True])
check('nobody and root and daemon and mysql and lsadm are never removed', [safe(u) for u in ('nobody', 'root', 'daemon', 'mysql', 'lsadm')], [False] * 5)
check('an account whose home is / or /home or leaves /home is not removed', [safe(u) for u in ('tricky', 'tricky2', 'tricky3')], [False, False, False])
check('an account with the id of nobody or above is not removed', safe('highid'), False)
check('an empty name and a missing account are not removed', (safe(''), safe(None), safe('doesnotexist')), (False, False, False))
check('names with spaces or options or slashes are not removed', [safe(x) for x in ('a b', '-f', 'a;b', '../x', 'A', 'x' * 40)], [False] * 6)
check('both places that run userdel go through the guard', (SRC.count("userdel -r -f %s' % (externalApp)"), SRC.count('if vhost.IsSiteUserSafeToRemove(externalApp):')), (2, 2))
check('the groupdel is inside the guard too', SRC.count("groupdel %s' % (externalApp)"), 2)

# control: the guard would let nobody through if the home check and the name list were removed
loose = SRC.replace("return 0 < entry.pw_uid < 65534 and home.startswith('/home/') and home != '/home'", 'return True').replace("if userName in vhost.PROTECTED_SITE_USERS:", "if False:")
check('control: a guard without the checks would allow nobody', load(loose, ACCOUNTS).IsSiteUserSafeToRemove('nobody'), True)
check('plogical/vhost.py has no carriage returns', b'\r' in open(PATH, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
