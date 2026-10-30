"""Tests Upgrade.FixCurrentQuoatasSystem and Upgrade.rootMountHasQuotas in plogical/upgrade.py.
The real function sources are taken from the file, their paths are pointed at temp files and every external action
(package install, fstab edit, remount, chattr, setquota) is replaced by a recorder. Nothing real is read or written.
Run: python3 CPScripts/test_quota_skip.py"""
import ast
import hashlib
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'plogical', 'upgrade.py')
SRC = open(SOURCE, encoding='utf-8').read()
TREE = ast.parse(SRC)
CLS = next(c for c in ast.walk(TREE) if isinstance(c, ast.ClassDef) and c.name == 'Upgrade')
SEG = {n.name: ast.get_source_segment(SRC, n) for n in CLS.body if isinstance(n, ast.FunctionDef)}

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def build(fstab, mounts, install_result=0, sites=()):
    """Returns (FixCurrentQuoatasSystem, calls) wired to temp files and recorders."""
    tmp = tempfile.mkdtemp()
    fstab_path = os.path.join(tmp, 'fstab')
    mounts_path = os.path.join(tmp, 'mounts')
    open(fstab_path, 'w').write(fstab)
    if mounts is not None:
        open(mounts_path, 'w').write(mounts)
    calls = []

    def load(name):
        text = SEG[name].replace("'/etc/fstab'", repr(fstab_path)).replace("'/proc/mounts'", repr(mounts_path))
        literals = [n.value for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        assert '/etc/fstab' not in literals and '/proc/mounts' not in literals, name
        ns = {}
        exec(text, ns)
        return ns[name]

    class Upgrade:
        pass

    Upgrade.rootMountHasQuotas = staticmethod(load('rootMountHasQuotas'))
    Upgrade.installQuota = staticmethod(lambda: calls.append('installQuota') or install_result)
    Upgrade.executioner = staticmethod(lambda command, *rest: calls.append(command))
    fix_text = SEG['FixCurrentQuoatasSystem'].replace("'/etc/fstab'", repr(fstab_path))
    ns = {'Upgrade': Upgrade}
    exec(fix_text, ns)

    class Site:
        def __init__(self, domain, app, enforce, space):
            self.domain, self.externalApp = domain, app
            self.package = types.SimpleNamespace(enforceDiskLimits=enforce, diskSpace=space)

    fake_models = types.ModuleType('websiteFunctions.models')
    fake_models.Websites = types.SimpleNamespace(objects=types.SimpleNamespace(all=lambda: [Site(*s) for s in sites]))
    sys.modules['websiteFunctions'] = types.ModuleType('websiteFunctions')
    sys.modules['websiteFunctions.models'] = fake_models
    return ns['FixCurrentQuoatasSystem'], calls, Upgrade


EXT4_FSTAB = '#\nUUID=aaaa\t/\text4\tdefaults,noatime,usrquota,grpquota\t1\t0\nUUID=bbbb /boot ext4 defaults 1 0\n'
PLAIN_FSTAB = '#\nUUID=aaaa\t/\text4\tdefaults,noatime\t1\t0\n'
XFS_FSTAB = '#\nUUID=aaaa\t/\txfs\tdefaults,uquota\t0\t0\n'
MOUNT_ON = 'proc /proc proc rw 0 0\n/dev/sda3 / ext4 rw,noatime,quota,usrquota,grpquota 0 0\n'
MOUNT_OFF = 'proc /proc proc rw 0 0\n/dev/sda3 / ext4 rw,noatime 0 0\n'

# the untouched functions are byte-identical to the base (hashes taken from fork v2.3.9)
for name, want in (('installQuota', '3e9baff8722f28c1'), ('edit_fstab', '87481f92e9d6b940')):
    check('%s is unchanged' % name, hashlib.sha256(SEG[name].encode()).hexdigest()[:16], want)

# 1 fstab asks for quotas and the live root mount has them: nothing is set up
fix, calls, _ = build(EXT4_FSTAB, MOUNT_ON, install_result=1, sites=[('example.test', 'u1', True, 100)])
fix()
check('quotas enabled and active: no setup, no install, no per-site work', calls, [])

# 2 fstab asks for quotas but the live mount does not have them: the old setup still runs
fix, calls, _ = build(EXT4_FSTAB, MOUNT_OFF, install_result=0)
fix()
check('fstab has quotas but the mount does not: installQuota still runs', calls, ['installQuota'])

# 3 fstab has no quota options: the old setup runs
fix, calls, _ = build(PLAIN_FSTAB, MOUNT_ON, install_result=0)
fix()
check('no quota options in fstab: installQuota runs', calls, ['installQuota'])

# 4 xfs spelling
fix, calls, _ = build(XFS_FSTAB, MOUNT_ON, install_result=1, sites=[('example.test', 'u1', True, 100)])
fix()
check('xfs uquota in fstab and usrquota live: nothing is set up', calls, [])

# 5 the live mount cannot be read: the old behaviour
fix, calls, _ = build(EXT4_FSTAB, None, install_result=0)
fix()
check('unreadable /proc/mounts: falls back to installQuota', calls, ['installQuota'])

# 6 several entries for /: the last one decides
fix, calls, _ = build(EXT4_FSTAB, 'rootfs / rootfs rw 0 0\n' + MOUNT_ON, install_result=0)
fix()
check('the last / entry decides (quotas on): nothing runs', calls, [])
fix, calls, _ = build(EXT4_FSTAB, MOUNT_ON + 'overlay / overlay rw 0 0\n', install_result=0)
fix()
check('the last / entry decides (quotas off): installQuota runs', calls, ['installQuota'])

# 7 a mount of another path with the option does not count
fix, calls, _ = build(EXT4_FSTAB, '/dev/sdb1 /data ext4 rw,usrquota 0 0\n/dev/sda3 / ext4 rw 0 0\n', install_result=0)
fix()
check('usrquota on another mount does not count', calls, ['installQuota'])

# 8 when installQuota succeeds the per-site work is exactly what it was
sites = [('a.test', 'ua', True, 50), ('b.test', 'ub', False, 70)]
fix, calls, _ = build(PLAIN_FSTAB, MOUNT_OFF, install_result=1, sites=sites)
fix()
check('installQuota ok: chattr for every site and setquota only where limits are enforced', calls,
      ['installQuota', 'chattr -R -i /home/a.test/', 'setquota -u ua 50M 50M 0 0 /', 'chattr -R -i /home/b.test/'])

# 9 rootMountHasQuotas on its own
_, _, Up = build(EXT4_FSTAB, 'x / ext4 rw,usrquota,grpquota 0 0\n')
check('rootMountHasQuotas: usrquota present', Up.rootMountHasQuotas(), True)
_, _, Up = build(EXT4_FSTAB, 'x / ext4 rw,grpquota 0 0\n')
check('rootMountHasQuotas: grpquota alone is not enough', Up.rootMountHasQuotas(), False)
_, _, Up = build(EXT4_FSTAB, 'garbage\n\n')
check('rootMountHasQuotas: malformed content is False', Up.rootMountHasQuotas(), False)

# 10 file hygiene
try:
    ast.parse(SRC.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('upgrade.py parses with the Python 3.9 grammar', parsed, True)
check('upgrade.py has no carriage returns', '\r' in SRC, False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
