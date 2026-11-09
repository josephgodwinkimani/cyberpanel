"""Tests delete_backup, fetch_restore_points and restore_point in IncBackups/views.py: a job or snapshot id that belongs to
another website is refused even when the caller passes a domain they own. The real handlers are run against in-memory
stand-ins for the models (they resolve the same website__domain style lookups) and for the job runner.
Run: python3 CPScripts/test_incremental_backup_domain_scope.py"""
import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'IncBackups', 'views.py')

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
funcs = {n.name: ast.get_source_segment(src, n) for n in tree.body if isinstance(n, ast.FunctionDef)
         and n.name in ('delete_backup', 'fetch_restore_points', 'restore_point')}
assert len(funcs) == 3

# the same handlers with the new scoping taken out, as controls
unscoped = {
    'delete_backup': funcs['delete_backup'].replace('IncJob.objects.get(id=backup_id, website__domain=backup_domain)', 'IncJob.objects.get(id=backup_id)'),
    'fetch_restore_points': funcs['fetch_restore_points'].replace('IncJob.objects.get(id=job_id, website__domain=backup_domain)', 'IncJob.objects.get(id=job_id)'),
    'restore_point': funcs['restore_point'].replace("if not JobSnapshots.objects.filter(id=job_id, job__website__domain=backup_domain).exists():", 'if False:'),
}
for k in unscoped:
    assert unscoped[k] != funcs[k], k


class DoesNotExist(Exception):
    pass


def resolve(obj, path):
    for part in path.split('__'):
        obj = getattr(obj, part)
    return obj


class Manager:
    def __init__(self, rows):
        self.rows = rows

    def _match(self, **kw):
        for k, v in kw.items():
            if k == 'id' and isinstance(v, str) and not v.isdigit():
                raise ValueError("Field 'id' expected a number but got %r." % v)
        return [r for r in self.rows if all(resolve(r, k) == v for k, v in kw.items())]

    def get(self, **kw):
        found = self._match(**kw)
        if not found:
            raise DoesNotExist('matching query does not exist.')
        return found[0]

    def filter(self, **kw):
        found = self._match(**kw)
        return types.SimpleNamespace(exists=lambda: bool(found))


class Site:
    def __init__(self, domain):
        self.domain = domain


class Job:
    def __init__(self, id, site):
        self.id, self.website, self.deleted = id, site, False
        self.snaps = []

    @property
    def jobsnapshots_set(self):
        return types.SimpleNamespace(all=lambda: self.snaps)

    def delete(self):
        self.deleted = True


class Snap:
    def __init__(self, id, job, sid):
        self.id, self.job, self.snapshotid, self.type, self.destination = id, job, sid, 'data:/x', 'local'


site_a, site_b = Site('a.example'), Site('b.example')
job_a, job_b = Job(1, site_a), Job(2, site_b)
snap_a, snap_b = Snap(10, job_a, 'sa'), Snap(20, job_b, 'sb')
job_a.snaps.append(snap_a)
job_b.snaps.append(snap_b)

events = []


class IncJobs:
    def __init__(self, kind, args):
        self.kind, self.args = kind, args
        events.append(('IncJobs', kind, dict(args) if args else None))

    def DeleteSnapShot(self, job):
        events.append(('DeleteSnapShot', job.id))

    def start(self):
        events.append(('start', self.kind))


class ACL:
    owned = {'a.example'}

    @staticmethod
    def checkOwnership(domain, admin, acl):
        return 1 if domain in ACL.owned else 0

    @staticmethod
    def loadErrorJson(key, code):
        return ('ERRORJSON', key, code)


class Resp:
    def __init__(self, body):
        self.body = body


IncJobModel = types.SimpleNamespace(objects=None, DoesNotExist=DoesNotExist)


def build(source):
    inc = types.SimpleNamespace(objects=Manager([job_a, job_b]), DoesNotExist=DoesNotExist)
    snaps = types.SimpleNamespace(objects=Manager([snap_a, snap_b]))
    ns = {
        'json': json, 'HttpResponse': Resp, 'ACLManager': ACL, '_get_user_acl': lambda r: (1, None),
        'Administrator': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda pk: object())),
        'IncJob': inc, 'JobSnapshots': snaps, 'IncJobs': IncJobs,
        'Path': __import__('pathlib').Path, 'randint': lambda a, b: 1234, 'time': types.SimpleNamespace(sleep=lambda s: None),
        'logging': types.SimpleNamespace(writeToFile=lambda m: None),
    }
    exec(source, ns)
    return ns


real = {k: build(v)[k] for k, v in funcs.items()}
control = {k: build(v)[k] for k, v in unscoped.items()}


def call(fn, **body):
    del events[:]
    r = fn(types.SimpleNamespace(body=json.dumps(body).encode()))
    return r if isinstance(r, tuple) else json.loads(r.body)


def reset():
    job_a.deleted = job_b.deleted = False


# ---- delete_backup
reset()
r = call(real['delete_backup'], websiteToBeBacked='a.example', backupID=1)
check('delete_backup: the owner deletes their own job', (r['status'], events, job_a.deleted), (1, [('IncJobs', None, None), ('DeleteSnapShot', 1)], True))
reset()
r = call(real['delete_backup'], websiteToBeBacked='a.example', backupID=2)
check("delete_backup: another website's job id with an owned domain is refused", (r['destStatus'], events, job_b.deleted), (0, [], False))
reset()
r = call(real['delete_backup'], websiteToBeBacked='b.example', backupID=2)
check('delete_backup: a domain that is not owned is still refused first', (r, events), (('ERRORJSON', 'fetchStatus', 0), []))
reset()
r = call(real['delete_backup'], websiteToBeBacked='a.example', backupID=999)
check('delete_backup: a missing id gives the same error response as a wrong-website id', (r['destStatus'], 'does not exist' in r['error_message']), (0, True))
reset()
call(control['delete_backup'], websiteToBeBacked='a.example', backupID=2)
check("control: without the scoping the other website's job is deleted", (events, job_b.deleted), ([('IncJobs', None, None), ('DeleteSnapShot', 2)], True))

# ---- fetch_restore_points
r = call(real['fetch_restore_points'], websiteToBeBacked='a.example', id=1)
check('fetch_restore_points: the owner lists their own restore points', (r['status'], [d['snapshotid'] for d in r['data']]), (1, ['sa']))
r = call(real['fetch_restore_points'], websiteToBeBacked='a.example', id=2)
check("fetch_restore_points: another website's job id is refused and nothing is listed", (r['status'], 'data' in r), (0, False))
r = call(control['fetch_restore_points'], websiteToBeBacked='a.example', id=2)
check("control: without the scoping the other website's restore points are listed", [d['snapshotid'] for d in r['data']], ['sb'])

# ---- restore_point
r = call(real['restore_point'], websiteToBeBacked='a.example', jobid=10, reconstruct='local')
check('restore_point (local): the owner restores their own snapshot', (r['status'], [e[0] for e in events], events[0][2]['jobid']), (1, ['IncJobs', 'start'], 10))
r = call(real['restore_point'], websiteToBeBacked='a.example', jobid=20, reconstruct='local')
check("restore_point (local): another website's snapshot id is refused and no job starts", (r, events), (('ERRORJSON', 'metaStatus', 0), []))
r = call(real['restore_point'], websiteToBeBacked='a.example', jobid='abc', reconstruct='local')
check('restore_point (local): a non-numeric id ends in the handler error response', (r['status'], events), (0, []))
r = call(real['restore_point'], websiteToBeBacked='a.example', jobid='1a2b3c4d', reconstruct='remote', backupDestinations='sftp:192.0.2.1', password='p', path='/p')
check('restore_point (remote): a remote snapshot id is not looked up in the database and proceeds as before', (r['status'], [e[0] for e in events], events[0][2]['jobid']), (1, ['IncJobs', 'start'], '1a2b3c4d'))
r = call(real['restore_point'], websiteToBeBacked='b.example', jobid=20, reconstruct='local')
check('restore_point: a domain that is not owned is still refused first', (r, events), (('ERRORJSON', 'metaStatus', 0), []))
r = call(control['restore_point'], websiteToBeBacked='a.example', jobid=20, reconstruct='local')
check("control: without the check another website's snapshot would be restored", (r['status'], events[0][2]['jobid']), (1, 20))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('IncBackups/views.py parses with the Python 3.9 grammar', parsed, True)
check('IncBackups/views.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
