"""Tests submitUserCreation in userManagment/views.py: a user who is not an admin can never create an admin-level account,
and every other path keeps working. The real function is run with stand-ins for the models, the access checks and the
password hashing. Run: python3 CPScripts/test_user_creation_acl.py"""
import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'userManagment', 'views.py')

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
node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'submitUserCreation')
raw = ast.get_source_segment(src, node)

guard_marker = "if selectedACL.adminStatus == 1:\n                    data_ret"
assert raw.count(guard_marker) == 1
control_src = raw.replace(guard_marker, "if False:\n                    data_ret")

sys.modules['validators'] = types.SimpleNamespace(email=lambda e: True)

saved = []


class Administrator:
    class objects:
        @staticmethod
        def get(pk):
            return types.SimpleNamespace(pk=pk)

    def __init__(self, **kw):
        self.kw = kw

    def save(self):
        saved.append(self.kw)


ACLS = {
    'admin': types.SimpleNamespace(name='admin', adminStatus=1),
    'reseller': types.SimpleNamespace(name='reseller', adminStatus=0),
    'user': types.SimpleNamespace(name='user', adminStatus=0),
    'superops': types.SimpleNamespace(name='superops', adminStatus=1),
}


class ACLModel:
    class objects:
        @staticmethod
        def get(name):
            return ACLS[name]


PERMS = {
    1: {'admin': 1, 'changeUserACL': 0, 'createNewUser': 0},
    2: {'admin': 0, 'changeUserACL': 1, 'createNewUser': 0},
    3: {'admin': 0, 'changeUserACL': 0, 'createNewUser': 1},
    4: {'admin': 0, 'changeUserACL': 0, 'createNewUser': 0},
}


class ACLManager:
    @staticmethod
    def loadedACL(uid):
        return PERMS[uid]

    @staticmethod
    def CheckRegEx(rx, value):
        return 1

    @staticmethod
    def websitesLimitCheck(admin, limit):
        return 1


def build(source):
    ns = {
        'json': json, 'HttpResponse': lambda b: json.loads(b), 'ACLManager': ACLManager, 'ACL': ACLModel,
        'Administrator': Administrator,
        'hashPassword': types.SimpleNamespace(generateToken=lambda u, p: 'tok', hash_password=lambda p: 'hashed'),
        'secMiddleware': types.SimpleNamespace(LOW=0, HIGH=1),
    }
    exec(source, ns)
    return ns['submitUserCreation']


real, control = build(raw), build(control_src)


def create(fn, uid, acl):
    del saved[:]
    request = {'userID': uid, 'firstName': 'Test', 'lastName': 'Person', 'email': 'a@b.example', 'userName': 'newuser',
               'password': 'pw', 'websitesLimit': 5, 'selectedACL': acl}
    return fn(request)


DENIED = {'status': 0, 'createStatus': 0, 'error_message': 'You are not authorized to access this resource.'}
CREATED = {'status': 1, 'createStatus': 1, 'error_message': 'None'}

# admin: unchanged, can create any account
r = create(real, 1, 'admin')
check('admin creates an admin account (type 1) as before', (r, [s['type'] for s in saved]), (CREATED, [1]))
r = create(real, 1, 'user')
check('admin creates a normal user (type 3) as before', (r, [s['type'] for s in saved]), (CREATED, [3]))
r = create(real, 1, 'superops')
check('admin creates a custom admin-level account as before', (r, len(saved)), (CREATED, 1))

# a non-admin with the change-ACL permission
r = create(real, 2, 'user')
check('changeUserACL holder creates a normal user as before', (r, [s['type'] for s in saved], saved[0]['owner']), (CREATED, [3], 2))
r = create(real, 2, 'reseller')
check('changeUserACL holder creates a reseller as before', (r, len(saved)), (CREATED, 1))
r = create(real, 2, 'admin')
check('changeUserACL holder can no longer create an admin account', (r, saved), (DENIED, []))
r = create(real, 2, 'superops')
check('changeUserACL holder can no longer create a custom admin-level account', (r, saved), (DENIED, []))
r = create(control, 2, 'admin')
check('control: without the guard the same request creates an admin (type 1)', (r, [s['type'] for s in saved]), (CREATED, [1]))

# a non-admin with only the create-user permission (already limited to the user ACL)
r = create(real, 3, 'user')
check('createNewUser holder creates a normal user as before', (r, len(saved)), (CREATED, 1))
check('createNewUser holder is still refused for the reseller ACL', (create(real, 3, 'reseller'), saved), (DENIED, []))
check('createNewUser holder is still refused for the admin ACL', (create(real, 3, 'admin'), saved), (DENIED, []))

# nobody else
check('a user with neither permission is refused as before', (create(real, 4, 'user'), saved), (DENIED, []))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('userManagment/views.py parses with the Python 3.9 grammar', parsed, True)
check('userManagment/views.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
