"""Tests BackupManager.cancelBackupCreation in backup/backupManager.py: only the owner of the domain can cancel a backup,
the backup name must be a plain name (never a path or extra arguments) and only that website's backup record is removed.
The real method is run with stand-ins for the access checks, the models and the subprocess call.
Run: python3 CPScripts/test_backup_cancel_ownership.py"""
import ast
import json
import os
import shlex
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'backup', 'backupManager.py')

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


src = open(SOURCE, encoding='utf-8').read()
tree = ast.parse(src)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BackupManager')
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'cancelBackupCreation')
raw = ast.get_source_segment(src, node)
dedent = lambda text: text.replace('\n' + ' ' * node.col_offset, '\n')
func_src = dedent(raw)

# controls: the same method without the new checks
own_if = next(n for n in ast.walk(node) if isinstance(n, ast.If) and 'checkOwnership' in ast.get_source_segment(src, n.test))
name_if = next(n for n in ast.walk(node) if isinstance(n, ast.If) and 'isinstance(fileName, str)' in ast.get_source_segment(src, n.test))
no_checks = dedent(raw.replace(ast.get_source_segment(src, own_if.test), 'False').replace(ast.get_source_segment(src, name_if.test), 'False'))
unscoped = func_src.replace('Backups.objects.get(fileName=fileName, website__domain=backupCancellationDomain)', 'Backups.objects.get(fileName=fileName)')
assert no_checks != func_src and unscoped != func_src


class DoesNotExist(Exception):
    pass


def resolve(obj, path):
    for part in path.split('__'):
        obj = getattr(obj, part)
    return obj


class Site:
    def __init__(self, domain):
        self.domain = domain


class Row:
    def __init__(self, site, fileName):
        self.website, self.fileName, self.deleted = site, fileName, False

    def delete(self):
        self.deleted = True


site_a, site_b = Site('a.example'), Site('b.example')
NAME = 'backup-a.example-' + time.strftime('%m.%d.%Y_%H-%M-%S')
row_a, row_b = Row(site_a, NAME), Row(site_b, 'backup-b.example-01.01.2026_00-00-00')
rows = [row_a, row_b]
calls = []


class BackupsModel:
    class objects:
        @staticmethod
        def get(**kw):
            found = [r for r in rows if all(resolve(r, k) == v for k, v in kw.items())]
            if not found:
                raise DoesNotExist('matching query does not exist.')
            return found[0]


class ACL:
    owned = {'a.example'}

    @staticmethod
    def loadedACL(uid):
        return {'admin': 0}

    @staticmethod
    def checkOwnership(domain, admin, acl):
        if domain not in ('a.example', 'b.example'):
            raise DoesNotExist('no such website')
        return 1 if domain in ACL.owned else None

    @staticmethod
    def loadErrorJson(key=None, code=None):
        return ('ERRORJSON', key, code)


class Resp:
    def __init__(self, body):
        self.body = body


def build(source):
    ns = {
        'json': json, 'HttpResponse': Resp, 'ACLManager': ACL, 'Backups': BackupsModel, 'shlex': shlex,
        'Administrator': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda pk: object())),
        'virtualHostUtilities': types.SimpleNamespace(cyberPanel='/usr/local/CyberCP'),
        'subprocess': types.SimpleNamespace(call=lambda args: calls.append(list(args))),
        'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=lambda m: None)),
    }
    exec(source, ns)
    return lambda data: ns['cancelBackupCreation'](None, 1, data)


real, no_check_fn, unscoped_fn = build(func_src), build(no_checks), build(unscoped)


def reset():
    del calls[:]
    row_a.deleted = row_b.deleted = False


def cancel(fn, domain, name):
    reset()
    r = fn({'backupCancellationDomain': domain, 'fileName': name})
    return r if isinstance(r, tuple) else json.loads(r.body)


# the owner
r = cancel(real, 'a.example', NAME)
check('the owner can cancel their backup', (r['abortStatus'], row_a.deleted, row_b.deleted), (1, True, False))
check('the worker is started with exactly the same arguments as before', calls,
      [['/usr/local/CyberCP/bin/python', '/usr/local/CyberCP/plogical/backupUtilities.py', 'cancelBackupCreation',
        '--backupCancellationDomain', 'a.example', '--fileName', NAME]])

# someone who does not own the domain
r = cancel(real, 'b.example', row_b.fileName)
check("another website's domain is refused with nothing started or deleted", (r, calls, row_b.deleted), (('ERRORJSON', 'abortStatus', 0), [], False))
r = cancel(real, 'unknown.example', NAME)
check('an unknown domain ends in the handler error response and starts nothing', (r['abortStatus'], calls), (0, []))
cancel(no_check_fn, 'b.example', row_b.fileName)
check("control: without the ownership check another website's backup is cancelled and its record deleted", (len(calls), row_b.deleted), (1, True))

# names that are paths or carry extra arguments
bad = {
    'parent folder': '../../../etc/cron.d/x',
    'sibling website': '../b.example/backup/x',
    'absolute path': '/etc/passwd',
    'extra argument': 'x --backupCancellationDomain b.example',
    'space': 'backup a',
    'semicolon': 'x;id',
    'dots only': '..',
    'single dot': '.',
    'embedded double dot': 'a..b',
    'empty': '',
    'non-ascii digit': 'backup-٣',
    'a list': [NAME],
    'null': None,
}
for label, name in bad.items():
    r = cancel(real, 'a.example', name)
    check('name with %s: refused and nothing started' % label, (r, calls), (('ERRORJSON', 'abortStatus', 0), []))
cancel(no_check_fn, 'a.example', '../../../etc/cron.d/x')
check('control: without the name check a path name reaches the worker', calls[0][-1], '../../../etc/cron.d/x')
cancel(no_check_fn, 'a.example', 'x --backupCancellationDomain b.example')
check('control: without the name check extra arguments reach the worker', 'b.example' in calls[0], True)

# names the panel really produces
for good in (NAME, 'backup-example.co.ke-10.30.2026_22-46-16', 'backup-my-site.example.com-01.02.2026_03-04-05'):
    r = cancel(real, 'a.example', good)
    check('real-format name accepted: %s' % good, (r['abortStatus'], len(calls)), (1, 1))

# the record that is removed belongs to the domain
other = Row(site_b, 'shared-name')
rows.append(other)
r = cancel(real, 'a.example', 'shared-name')
check("a record with the same name on another website is not deleted", (r['abortStatus'], other.deleted), (1, False))
cancel(unscoped_fn, 'a.example', 'shared-name')
check("control: without the scoping the other website's record is deleted", other.deleted, True)
rows.remove(other)

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('backupManager.py parses with the Python 3.9 grammar', parsed, True)
check('backupManager.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
