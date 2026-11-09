"""Tests BackupDatabases in plogical/backupUtilities.py: a failed database dump now fails the website backup.
The real method source is taken from the file and run with stubs for the panel database, the dump and the logger, so no
database is read and no file is written. Run: python3 CPScripts/test_backup_database_dump_failure.py"""
import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'plogical', 'backupUtilities.py')
src = open(SOURCE, encoding='utf-8').read()
node = next(n for c in ast.walk(ast.parse(src)) if isinstance(c, ast.ClassDef) for n in c.body
            if isinstance(n, ast.FunctionDef) and n.name == 'BackupDatabases')
func_src = ast.get_source_segment(src, node)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


dumps, commands, logged, written, sleeps = [], [], [], {}, []


class FakeFile:
    def __init__(self, path):
        self.path = path

    def write(self, text):
        written[self.path] = text

    def close(self):
        pass


class Item:
    def __init__(self, name, user):
        self.dbName, self.dbUser = name, user


class FakeDBUsers:
    class objects:
        @staticmethod
        def get(user):
            if user == 'missing':
                raise LookupError('no such user')
            return types.SimpleNamespace(password='pw-' + user)

        @staticmethod
        def all():
            return types.SimpleNamespace(filter=lambda user: [])


def run(items, results, fetchuser=lambda name: 0):
    dumps.clear(); commands.clear(); logged.clear(); written.clear(); sleeps.clear()
    results = list(results)

    def dump(name, path):
        dumps.append((name, path))
        r = results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    site = types.SimpleNamespace(domain='example.test', databases_set=types.SimpleNamespace(all=lambda: items))
    me = types.SimpleNamespace(BackupPath='/b/backup-1', website=site, CheckIfSleepNeeded=lambda: sleeps.append(1))
    ns = {
        'ProcessUtilities': types.SimpleNamespace(executioner=lambda c, *a, **k: commands.append(c)),
        'DBUsers': FakeDBUsers,
        'mysqlUtilities': types.SimpleNamespace(mysqlUtilities=types.SimpleNamespace(createDatabaseBackup=dump, fetchuser=fetchuser)),
        'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=lambda m: logged.append(m))),
        'open': lambda path, mode='r': FakeFile(path),
    }
    exec(func_src, ns)
    return ns['BackupDatabases'](me)


two = [Item('db_one', 'u1'), Item('db_two', 'u2')]
three = [Item('db_one', 'u1'), Item('db_two', 'u2'), Item('db_three', 'u3')]

# all dumps succeed: exactly as before
res = run(two, [1, 1])
check('all dumps ok: the backup step succeeds', res, (1, None))
check('all dumps ok: every database is dumped into the databases folder', dumps, [('db_one', '/b/backup-1/databases'), ('db_two', '/b/backup-1/databases')])
data = json.loads(written['/b/backup-1/databases.json'])
check('all dumps ok: databases.json lists both with their users', [(d['databaseName'], d['databaseUser']) for d in data['databases']], [('db_one', 'u1'), ('db_two', 'u2')])
check('all dumps ok: the sleep check runs as before (three times for two databases)', len(sleeps), 3)

# no databases
res = run([], [])
check('no databases: succeeds with an empty list', (res, json.loads(written['/b/backup-1/databases.json'])['databases']), ((1, None), []))

# a failed dump stops the backup
res = run(three, [1, 0, 1])
check('the second dump fails: the step fails', res[0], 0)
check('the failure message names the database', 'db_two' in res[1], True)
check('the failure is logged with the domain', (len(logged), 'example.test' in logged[0], 'db_two' in logged[0]), (1, True, True))
check('the third database is not attempted after a failure', [d[0] for d in dumps], ['db_one', 'db_two'])
check('databases.json is not written for a failed backup', written, {})

res = run(three, [0])
check('the first dump fails: the step fails at once', (res[0], [d[0] for d in dumps]), (0, ['db_one']))

# behaviour that must not change
res = run([Item('db_x', 'missing'), Item('db_two', 'u2')], [1], fetchuser=lambda name: 0)
check('a database whose user cannot be found is still skipped, not dumped', (res, [d[0] for d in dumps]), ((1, None), ['db_two']))

res = run(two, [RuntimeError('boom')])
check('an exception inside the dump still gives the error result', (res[0], res[1]), (0, 'boom'))

# the other result shapes: a tuple result (rustic) is not 0, so it does not trip the check
res = run(two, [(1, 'snap'), (1, 'snap')])
check('a tuple result is not mistaken for a failure', res, (1, None))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('backupUtilities.py parses with the Python 3.9 grammar', parsed, True)
check('backupUtilities.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
