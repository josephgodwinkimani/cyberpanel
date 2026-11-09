"""Tests saveModifications in userManagment/views.py: a blank or missing password field keeps the current password.
The real function source is taken from the file and run with stubs for the database, the ACL and the hashing, so no
account is touched. Run: python3 CPScripts/test_user_modify_password.py"""
import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'userManagment', 'views.py')
src = open(SOURCE, encoding='utf-8').read()
node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'saveModifications')
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


class FakeUser:
    def __init__(self, pk, name, owner=0):
        self.pk, self.userName, self.owner = pk, name, owner
        self.firstName = self.lastName = self.email = 'old'
        self.password, self.token = 'OLDHASH', 'OLDTOKEN'
        self.type, self.twoFA, self.securityLevel = 1, 0, 9
        self.saved = 0

    def save(self):
        self.saved += 1


USERS = {}
FILES = {}
ACL = {'admin': 0}


class FakeAdministrator:
    class objects:
        @staticmethod
        def get(**kw):
            for u in USERS.values():
                if all(getattr(u, k) == v for k, v in kw.items()):
                    return u
            raise LookupError('no such user')


class FakeACLManager:
    @staticmethod
    def loadedACL(user_id):
        return dict(ACL)


class FakeHash:
    @staticmethod
    def hash_password(password):
        return 'HASH(%s)' % password

    @staticmethod
    def generateToken(user, password):
        return 'TOKEN(%s:%s)' % (user, password)


class FakeFile:
    def __init__(self, path):
        self.path = path

    def write(self, text):
        FILES[self.path] = text

    def close(self):
        pass


class FakeResponse:
    def __init__(self, content):
        self.content = content


ns = {
    'json': json, 'HttpResponse': FakeResponse, 'Administrator': FakeAdministrator, 'ACLManager': FakeACLManager,
    'hashPassword': FakeHash, 'secMiddleware': types.SimpleNamespace(LOW=1, HIGH=0),
    'open': lambda path, mode='r': FakeFile(path),
}
exec(func_src, ns)
save = ns['saveModifications']


def setup(admin=0):
    USERS.clear()
    FILES.clear()
    ACL['admin'] = admin
    USERS[1] = FakeUser(1, 'actor')
    USERS[2] = FakeUser(2, 'target', owner=1)
    USERS[3] = FakeUser(3, 'stranger', owner=99)
    USERS[4] = FakeUser(4, 'admin')


def call(account, extra, logged_in=1, as_dict=False):
    data = {'accountUsername': account, 'firstName': 'New', 'lastName': 'Name', 'email': 'new@example.test'}
    data.update(extra)
    if as_dict:
        data['userID'] = logged_in
        result = save(data)
    else:
        result = save(types.SimpleNamespace(session={'userID': logged_in}, body=json.dumps(data).encode()))
    return json.loads(result.content)


# 1 a new password is applied exactly as before
setup(admin=1)
out = call('target', {'passwordByPass': 's3cret-Pass'})
u = USERS[2]
check('a typed password is hashed and stored', (out['saveStatus'], u.password, u.token), (1, 'HASH(s3cret-Pass)', 'TOKEN(target:s3cret-Pass)'))
check('the other fields are saved too', (u.firstName, u.lastName, u.email, u.saved), ('New', 'Name', 'new@example.test', 1))
call('target', {'passwordByPass': ' pad '})
check('surrounding spaces in a real password are kept', USERS[2].password, 'HASH( pad )')

# 2 blank, missing, whitespace and null keep the current password and still save the rest
for label, extra in (('an empty string', {'passwordByPass': ''}), ('a missing field', {}), ('only spaces', {'passwordByPass': '   '}),
                     ('a tab and newline', {'passwordByPass': '\t\n'}), ('null', {'passwordByPass': None})):
    setup(admin=1)
    out = call('target', extra)
    u = USERS[2]
    check('%s keeps the current password and token' % label, (u.password, u.token), ('OLDHASH', 'OLDTOKEN'))
    check('%s still saves the other fields' % label, (out['saveStatus'], u.firstName, u.email, u.saved), (1, 'New', 'new@example.test', 1))

# 3 authorisation is unchanged
setup(admin=0)
out = call('stranger', {'passwordByPass': 'x'})
check('a non administrator cannot change a stranger', (out.get('error_message'), USERS[3].password, USERS[3].saved), ('Un-authorized access.', 'OLDHASH', 0))
setup(admin=0)
out = call('target', {'passwordByPass': 'x'})
check('an owner can change the password of an account they own', (out['saveStatus'], USERS[2].password), (1, 'HASH(x)'))
setup(admin=0)
out = call('actor', {'passwordByPass': 'mine'})
check('a user can change their own password', (out['saveStatus'], USERS[1].password), (1, 'HASH(mine)'))
setup(admin=0)
out = call('actor', {'passwordByPass': ''})
check('a user saving their own profile with a blank field keeps their password', (out['saveStatus'], USERS[1].password), (1, 'OLDHASH'))

# 4 the admin address file is still written
setup(admin=1)
call('admin', {'passwordByPass': ''})
check('saving the admin account still writes the admin email file', FILES.get('/home/cyberpanel/adminEmail'), 'new@example.test')

# 5 other settings are unchanged
setup(admin=1)
call('target', {'passwordByPass': '', 'securityLevel': 'LOW', 'twofa': '1'})
check('security level LOW and two factor are still applied', (USERS[2].securityLevel, USERS[2].twoFA, USERS[2].type), (1, 1, 0))
setup(admin=1)
call('target', {'passwordByPass': ''})
check('without a security level HIGH is used as before', USERS[2].securityLevel, 0)

# 6 the dict style call used by command line code
setup(admin=1)
out = call('target', {'passwordByPass': ''}, as_dict=True)
check('a dict style request with a blank password keeps the password', (out['saveStatus'], USERS[2].password), (1, 'OLDHASH'))
setup(admin=1)
out = call('target', {'passwordByPass': 'cli-pass'}, as_dict=True)
check('a dict style request with a password sets it', (out['saveStatus'], USERS[2].password), (1, 'HASH(cli-pass)'))

# 7 errors keep their shape
setup(admin=1)
out = call('nobody', {'passwordByPass': 'x'})
check('an unknown account gives the error response', (out['saveStatus'], 'error_message' in out), (0, True))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('views.py parses with the Python 3.9 grammar', parsed, True)
check('views.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
