"""Tests mysqlUtilities.deleteDatabase in plogical/mysqlUtilities.py: it no longer runs a shell command (the old rm -rf of a
.git folder built from the database name) and otherwise issues the same SQL as before.
The real function source is taken from the file and run with a fake connection and a command recorder.
Run: python3 CPScripts/test_database_delete_no_rm.py"""
import ast
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'plogical', 'mysqlUtilities.py')
src = open(SOURCE, encoding='utf-8').read()
cls = next(c for c in ast.parse(src).body if isinstance(c, ast.ClassDef) and c.name == 'mysqlUtilities')
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'deleteDatabase')
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


commands, statements, logged = [], [], []


class FakeCursor:
    def __init__(self, users, fail_on=None):
        self.users, self.fail_on = users, fail_on

    def execute(self, sql):
        statements.append(sql)
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError('boom: ' + sql)

    def fetchall(self):
        return self.users


class FakeConnection:
    closed = 0

    def close(self):
        FakeConnection.closed += 1


def run(name, user='u', users=(), connection_ok=True, fail_on=None):
    commands.clear()
    statements.clear()
    logged.clear()
    FakeConnection.closed = 0
    holder = types.SimpleNamespace()
    holder.setupConnection = lambda: (FakeConnection(), FakeCursor(list(users), fail_on)) if connection_ok else (0, 0)
    ns = {
        'mysqlUtilities': holder,
        'ProcessUtilities': types.SimpleNamespace(executioner=lambda c, *a, **k: commands.append(c)),
        'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=lambda m: logged.append(m))),
    }
    exec(func_src.replace('@staticmethod\n', ''), ns)
    return ns['deleteDatabase'](name, user)


# the defect is gone: no command of any kind runs
check('a normal delete returns 1', run('shop_db'), 1)
check('a normal delete runs no shell command', commands, [])
check('a normal delete issues the same SQL as before', statements, ["DROP DATABASE `shop_db`", "select user,host from mysql.db where db='shop_db'"])
check('the connection is closed', FakeConnection.closed, 1)

run('shop_db', users=[('app', 'localhost'), ('app2', '%')])
check('the users of the database are dropped as before', statements[2:], ["DROP USER 'app'@'localhost'", "DROP USER 'app2'@'%'"])
check('no shell command with users either', commands, [])

for odd in ('../../home/x', 'a b', '*', 'x/../..', '', '$(id)', 'name with spaces/.git'):
    run(odd)
    check('no shell command for the name %r' % odd, commands, [])

# behaviour that must not change
check('no connection returns 0 and runs nothing', (run('shop_db', connection_ok=False), commands, statements), (0, [], []))
result = run('shop_db', fail_on='DROP DATABASE')
check('an SQL error returns the message and is logged', (result.startswith('boom: DROP DATABASE'), len(logged), logged[0].endswith('[deleteDatabase]')), (True, 1, True))
check('a failed drop runs no shell command', commands, [])

# the function text itself
check('the function no longer mentions rm or ProcessUtilities', ('rm -rf' in func_src, 'ProcessUtilities' in func_src), (False, False))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('mysqlUtilities.py parses with the Python 3.9 grammar', parsed, True)
check('mysqlUtilities.py has no carriage returns', '\r' in src, False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
