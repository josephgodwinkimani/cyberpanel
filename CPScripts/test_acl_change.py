"""Tests changeACLFunc in userManagment/views.py: a user who is not an admin can only change the ACL of users they own and
can never assign an admin-level ACL, while admins keep full control. The real function and the real
ACLManager.checkUserOwnerShip are run with stand-ins for the models. Run: python3 CPScripts/test_acl_change.py"""
import ast
import json
import os
import sys
import textwrap
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, 'userManagment', 'views.py')
ACL_SOURCE = os.path.join(ROOT, 'plogical', 'acl.py')

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
node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'changeACLFunc')
raw = ast.get_source_segment(src, node)
test_marker = "if ACLManager.checkUserOwnerShip(currentACL, loggedUser, selectedUser) == 0 or selectedACL.adminStatus == 1:"
assert raw.count(test_marker) == 1
control_src = raw.replace(test_marker, 'if False:')

acl_src = open(ACL_SOURCE, encoding='utf-8').read()
acl_cls = next(n for n in ast.parse(acl_src).body if isinstance(n, ast.ClassDef) and n.name == 'ACLManager')
own = next(n for n in acl_cls.body if isinstance(n, ast.FunctionDef) and n.name == 'checkUserOwnerShip')
own_src = ast.get_source_segment(acl_src, own).replace('\n' + ' ' * own.col_offset, '\n')


class Admin:
    def __init__(self, pk, userName, owner=None):
        self.pk, self.userName, self.owner, self.acl = pk, userName, owner, None
        self.saves = 0

    def save(self):
        self.saves += 1


users = {
    1: Admin(1, 'root_admin'), 2: Admin(2, 'reseller_one', owner=1), 3: Admin(3, 'reseller_two', owner=1),
    4: Admin(4, 'client_of_one', owner=2), 5: Admin(5, 'client_of_two', owner=3), 6: Admin(6, 'plain_user', owner=1),
    7: Admin(7, 'admin'),
}
by_name = {u.userName: u for u in users.values()}
ACLS = {
    'admin': types.SimpleNamespace(name='admin', adminStatus=1), 'reseller': types.SimpleNamespace(name='reseller', adminStatus=0),
    'user': types.SimpleNamespace(name='user', adminStatus=0), 'superops': types.SimpleNamespace(name='superops', adminStatus=1),
}
PERMS = {1: {'admin': 1, 'changeUserACL': 0}, 2: {'admin': 0, 'changeUserACL': 1}, 3: {'admin': 0, 'changeUserACL': 1}, 6: {'admin': 0, 'changeUserACL': 0}}


class ACLManager:
    @staticmethod
    def loadedACL(uid):
        return PERMS[uid]

    @staticmethod
    def loadErrorJson(*a):
        return {'status': 0, 'errorMessage': 'You are not authorized to access this resource.'}


exec(own_src.replace('def checkUserOwnerShip', 'def _own'), {'__builtins__': __builtins__}, ns := {})
ACLManager.checkUserOwnerShip = staticmethod(ns['_own'])


def build(source):
    scope = {
        'json': json, 'HttpResponse': lambda b: json.loads(b), 'ACLManager': ACLManager,
        'ACL': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda name: ACLS[name])),
        'Administrator': types.SimpleNamespace(objects=types.SimpleNamespace(
            get=lambda **kw: users[kw['pk']] if 'pk' in kw else by_name[kw['userName']])),
    }
    exec(source, scope)
    return scope['changeACLFunc']


real, control = build(raw), build(control_src)


def change(fn, uid, target, acl):
    for u in users.values():
        u.acl, u.saves = None, 0
    req = types.SimpleNamespace(session={'userID': uid}, body=json.dumps({'selectedUser': target, 'selectedACL': acl}).encode())
    r = fn(req)
    return r, by_name[target].acl.name if by_name[target].acl else None, by_name[target].saves


DENIED = {'status': 0, 'errorMessage': 'You are not authorized to access this resource.'}

# admin: unchanged
check('admin changes any user to any ACL as before', change(real, 1, 'reseller_one', 'reseller')[0:2], ({'status': 1}, 'reseller'))
check('admin can still assign the admin ACL', change(real, 1, 'plain_user', 'admin')[0:2], ({'status': 1}, 'admin'))
r = change(real, 1, 'admin', 'user')[0]
check('the super user is still protected by name', (r['status'], 'can not be modified' in r['errorMessage']), (0, True))

# a non-admin with the permission
check('changeUserACL holder changes the ACL of a user they own', change(real, 2, 'client_of_one', 'reseller')[0:2], ({'status': 1}, 'reseller'))
check('changeUserACL holder can set a normal ACL on their own account (owner is the user)', change(real, 2, 'reseller_one', 'user')[0:2], ({'status': 1}, 'user'))
r, acl, saves = change(real, 2, 'client_of_one', 'admin')
check('changeUserACL holder cannot assign the admin ACL to a user they own', (r, acl, saves), (DENIED, None, 0))
r, acl, saves = change(real, 2, 'client_of_one', 'superops')
check('changeUserACL holder cannot assign a custom admin-level ACL', (r, acl, saves), (DENIED, None, 0))
r, acl, saves = change(real, 2, 'reseller_one', 'admin')
check('changeUserACL holder cannot make themselves an admin', (r, acl, saves), (DENIED, None, 0))
r, acl, saves = change(real, 2, 'client_of_two', 'user')
check("changeUserACL holder cannot change another reseller's user", (r, acl, saves), (DENIED, None, 0))
r, acl, saves = change(real, 2, 'plain_user', 'reseller')
check("changeUserACL holder cannot change a user owned by the super user", (r, acl, saves), (DENIED, None, 0))

# controls: the same function without the new test
check('control: without the check an admin ACL is assigned by a non-admin', change(control, 2, 'client_of_one', 'admin')[0:2], ({'status': 1}, 'admin'))
check("control: without the check another reseller's user is changed", change(control, 2, 'client_of_two', 'reseller')[0:2], ({'status': 1}, 'reseller'))

# nobody else
r = change(real, 6, 'client_of_one', 'user')
check('a user without the permission is refused as before', (r[0], r[1]), (DENIED, None))

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
