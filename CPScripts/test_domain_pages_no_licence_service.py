"""Tests WebsiteManager in websiteFunctions/website.py: Create Website, Create Child Domain and the website and domain create and
delete handlers no longer call the add-on licence service or the test domain service. A request library that fails on any call stands
in for the network. The pages keep their inputs and outputs: the Apache backend option is enabled only on LiteSpeed Enterprise as
before and is otherwise shown disabled, and every handler goes on to its own checks. The real methods are run with stand-ins for the
access checks and the models (nothing is written, sent or run).
Run: python3 CPScripts/test_domain_pages_no_licence_service.py"""
import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'websiteFunctions', 'website.py')

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


HOST = 'platform.' + 'cyberpersons.com'
SERVICE = 'https://' + HOST + '/Cyberpanel' + 'AdOns/'
MARKERS = ('cyber' + 'persons', 'Adon' + 'permission', 'CheckFor' + 'PremFeature', 'req' + 'uests', 'cyberpanel' + '.website')

src = open(SOURCE, encoding='utf-8').read()
cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == 'WebsiteManager')


def method(name):
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    raw = ast.get_source_segment(src, node)
    return raw.replace('\n' + ' ' * node.col_offset, '\n')


calls = []


class FakeRequests:
    @staticmethod
    def post(url, *a, **k):
        calls.append(url)
        raise AssertionError('licence service called')


sys.modules['requests'] = FakeRequests

NAMES = ('createWebsite', 'CreateNewDomain', 'submitWebsiteCreation', 'submitDomainCreation', 'submitWebsiteDeletion', 'submitDomainDeletion')
SOURCES = {n: method(n) for n in NAMES}

for n in NAMES:
    check('%s no longer names the licence service or the test domain service' % n,
          any(word in SOURCES[n] for word in MARKERS), False)


class Page:
    def __init__(self, request, template, data, function=None):
        self.template, self.data, self.function = template, data, function

    def render(self):
        return ('rendered', self.template, self.data)


def build(source, name, ent=False, permission=1, owner=1, valid=True, admin_get_fails=False):
    class Admin:
        class objects:
            @staticmethod
            def get(**kw):
                if admin_get_fails:
                    raise RuntimeError('reached the first lookup')
                return types.SimpleNamespace(defaultSite=1, userName='admin', save=lambda: None)

    acl = types.SimpleNamespace(
        loadedACL=lambda u: {'admin': 1}, loadAllUsers=lambda u: ['admin'], loadPackages=lambda u, a: ['Default'],
        findAllSites=lambda a, u: ['a.example'], findWebsiteObjects=lambda a, u: [types.SimpleNamespace(id=1, domain='a.example')],
        currentContextPermission=lambda a, p: permission, checkOwnership=lambda d, ad, c: owner,
        loadErrorJson=lambda *a: {'status': 0, 'errorMessage': 'denied'},
        checkOwnerProtection=lambda *a: 1, CheckDomainBlackList=lambda d: 1,
        GetServerIP=lambda: calls.append('address') or '192.0.2.1')
    pu = types.SimpleNamespace(decideServer=lambda: 'ent' if ent else 'ols', ent='ent', OLS='ols')
    ns = {'json': json, 'os': os, 'HttpResponse': lambda b: json.loads(b), 'ACLManager': acl, 'Administrator': Admin,
          'ProcessUtilities': pu, 'httpProc': Page, 'randomPassword': types.SimpleNamespace(generate_pass=lambda n: 'AbCdEfGhIj'),
          'PHPManager': types.SimpleNamespace(findPHPVersions=lambda: ['PHP 7.4']), 'randint': lambda a, b: 1234,
          'validators': types.SimpleNamespace(domain=lambda d: valid), 'Websites': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda **kw: types.SimpleNamespace(domain='a.example', defaultSite=1, phpSelection='PHP 7.4'))),
          'ApacheVhost': types.SimpleNamespace(configBasePath='/nonexistent/'), 'wpplugins': None}
    exec(source, ns)
    return lambda *a, **k: ns[name](types.SimpleNamespace(), *a, **k)


def run(fn, *a, **k):
    del calls[:]
    try:
        return fn(*a, **k), list(calls)
    except BaseException as exc:
        return ('raised', type(exc).__name__, str(exc)), list(calls)


# Create Website and Create Child Domain pages
for name, template in (('createWebsite', 'websiteFunctions/createWebsite.html'), ('CreateNewDomain', 'websiteFunctions/createDomain.html')):
    for ent, flag in ((False, 0), (True, 1)):
        result, made = run(build(SOURCES[name], name, ent=ent), None, 1)
        check('%s renders its page with the Apache backend option %s when %s' % (name, 'enabled' if flag else 'disabled', 'LiteSpeed Enterprise runs' if ent else 'OpenLiteSpeed runs'),
              (result[0], result[1], result[2]['test_domain_data'], made), ('rendered', template, flag, []))
    result, made = run(build(SOURCES[name], name), None, 1)
    keys = sorted(result[2])
    want = ['Randam_String', 'owernList', 'packageList', 'phps', 'test_domain_data'] if name == 'createWebsite' else ['Randam_String', 'defaultSite', 'phps', 'test_domain_data', 'websiteList']
    check('%s passes the same values to its template as before' % name, keys, want)

# the create and delete handlers reach their own checks with a test domain name and never call out
CREATE = {'domainName': 'site.cyberpanel.website', 'adminEmail': 'a@example.invalid', 'phpSelection': 'PHP 7.4', 'package': 'Default', 'websiteOwner': 'Admin'}
result, made = run(build(SOURCES['submitWebsiteCreation'], 'submitWebsiteCreation', admin_get_fails=True), 1, dict(CREATE))
check('submitWebsiteCreation with a cyberpanel.website name goes on to its own lookups without calling out', (result['error_message'], made), ('reached the first lookup', []))
result, made = run(build(SOURCES['submitWebsiteCreation'], 'submitWebsiteCreation', permission=0), 1, dict(CREATE))
check('submitWebsiteCreation still refuses a user without the permission', (result, made), ({'status': 0, 'errorMessage': 'denied'}, []))

CHILD = {'domainName': 'child.cyberpanel.website', 'masterDomain': 'a.example', 'phpSelection': 'PHP 7.4', 'path': ''}
result, made = run(build(SOURCES['submitDomainCreation'], 'submitDomainCreation', valid=False), 1, dict(CHILD))
check('submitDomainCreation with a cyberpanel.website name goes on to its domain check without calling out', (result['error_message'], made), ('Invalid domain.', []))
result, made = run(build(SOURCES['submitDomainCreation'], 'submitDomainCreation', owner=0), 1, dict(CHILD))
check('submitDomainCreation still refuses a master domain the user does not own', (result, made), ({'status': 0, 'errorMessage': 'denied'}, []))

DELETE = {'websiteName': 'site.cyberpanel.website'}
result, made = run(build(SOURCES['submitWebsiteDeletion'], 'submitWebsiteDeletion', permission=0), 1, dict(DELETE))
check('submitWebsiteDeletion with a cyberpanel.website name reaches its permission check without calling out', (result, made), ({'status': 0, 'errorMessage': 'denied'}, []))
result, made = run(build(SOURCES['submitWebsiteDeletion'], 'submitWebsiteDeletion', owner=0), 1, dict(DELETE))
check('submitWebsiteDeletion still refuses a site the user does not own', (result, made), ({'status': 0, 'errorMessage': 'denied'}, []))
result, made = run(build(SOURCES['submitDomainDeletion'], 'submitDomainDeletion', owner=0), 1, dict(DELETE))
check('submitDomainDeletion with a cyberpanel.website name reaches its ownership check without calling out', (result, made), ({'status': 0, 'errorMessage': 'denied'}, []))

# controls: the old blocks, put back, would be caught by this test
FLAG_OLD = '''    url = "%s"
    data = {
        "name": "all",
        "IP": ACLManager.GetServerIP()
    }

    import requests
    response = requests.post(url, data=json.dumps(data))
    Status = response.json()['status']

    test_domain_status = 0

    if (Status == 1) or ProcessUtilities.decideServer() == ProcessUtilities.ent:
        test_domain_status = 1
'''
FLAG_NEW = '''    test_domain_status = 0

    if ProcessUtilities.decideServer() == ProcessUtilities.ent:
        test_domain_status = 1
'''
for name in ('createWebsite', 'CreateNewDomain'):
    assert SOURCES[name].count(FLAG_NEW) == 1
    old = SOURCES[name].replace(FLAG_NEW, FLAG_OLD % (SERVICE + 'Adon' + 'permission'))
    result, made = run(build(old, name), None, 1)
    check('control: with the old code %s would read the server address and call the licence service on every page load' % name, (result[0], made), ('raised', ['address', SERVICE + 'Adon' + 'permission']))

OLD_BLOCK = '''        if data['%s'].find("cyberpanel.website") > -1:
            url = "%s"

            domain_data = {
                "name": "test-domain",
                "IP": ACLManager.GetServerIP(),
                "domain": data['%s']
            }

            import requests
            response = requests.post(url, data=json.dumps(domain_data))

'''
for name, key, endpoint, kw, payload in (('submitWebsiteDeletion', 'websiteName', 'DeleteDomain', {'permission': 0}, DELETE),
                                         ('submitDomainDeletion', 'websiteName', 'DeleteDomain', {'owner': 0}, DELETE),
                                         ('submitWebsiteCreation', 'domainName', 'CreateDomain', {'admin_get_fails': True}, CREATE),
                                         ('submitDomainCreation', 'domainName', 'CreateDomain', {'owner': 0}, CHILD)):
    anchor = '    try:\n'
    assert SOURCES[name].count(anchor) >= 1
    old = SOURCES[name].replace(anchor, anchor + OLD_BLOCK % (key, SERVICE + endpoint, key), 1)
    result, made = run(build(old, name, **kw), 1, dict(payload))
    check('control: with the old block %s would read the server address and send the domain name to the test domain service' % name, made, ['address', SERVICE + endpoint])

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('website.py parses with the Python 3.9 grammar', parsed, True)
check('website.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
