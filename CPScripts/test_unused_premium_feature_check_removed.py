"""Tests that the premium feature check of the access control helpers is gone: nothing calls it any more and it was the only helper that asked the
external licence service for permission and then trusted any failure as a yes. Every other method of the class that no other change touches is
byte for byte what it was, the helper that reads the machine address stays, and no file in the tree calls the removed check by name.
Run: python3 CPScripts/test_unused_premium_feature_check_removed.py"""
import ast
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def fp(src):
    return hashlib.sha256(src.encode()).hexdigest()[:16]


NAME = 'CheckFor' + 'PremFeature'
ACL = open(os.path.join(ROOT, 'plogical/acl.py'), encoding='utf-8').read()
tree = ast.parse(ACL)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ACLManager')
methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
check('the check is no longer a method of the class', NAME in methods, False)
check('the file no longer posts to the licence service', ('Adon' + 'permission' in ACL, 'platform.cyber' + 'persons' in ACL), (False, False))
PIN = {
        'AliasDomainCheck': '0b991b6794619922', 'CheckDomainBlackList': '93c269e81be8abd6', 'CheckIPPluginObjectOwner': '06a61c8e6c107d0b',
        'CheckPackageOwnership': 'd2e63916524850d8', 'CheckRegEx': '2324528b9d75bfb5', 'CheckStatusFilleLoc': '5bf014d8e0bdde57',
        'CreateSecureDir': '20f1d2a97285ed93', 'FetchExternalApp': 'f80c8d1590f5adaa', 'FindDocRootOfSite': '1a58403dc3178ba9',
        'FindDocRootOfSiteApache': '76507d31e7176d76', 'FindIfChild': '2004d1829f13ae63', 'GetServerIP': 'fe182f4839056536',
        'GetServiceStatus': 'fa77b4233af75981', 'ISARM': '12ed9674ad02c652', 'ReplaceDocRoot': '4014dc1ba6be1e09', 'ReplaceDocRootApache': '93794fec624aa215',
        'VerifyRecordOwner': 'e576e4d49fa6a1f6', 'VerifySMTPHost': '91ce5b84c08a5024', 'checkContainerOwnership': '2b006f3cb12c5b87',
        'checkOwnerProtection': 'd7ae4274c8256bb7', 'checkOwnership': '9e9360cd2f92abcb', 'checkOwnershipZone': '0ac97c651e7c64d4',
        'checkUserOwnerShip': '0219b10f0d7410f8', 'commandInjectionCheck': '8f9c2208269c8907', 'createDefaultACLs': 'be2b9c4459900ca4',
        'currentContextPermission': '68b75d36517506e5', 'executeCall': '4f592da98ed47d7e', 'fetchIP': 'f7455616ea86da60',
        'fetchTableUserObjects': '0bb7c4b27c7d9556', 'findAllACLs': '8e1d9933fb3edb2f', 'findAllContainers': '3c8be3ae02cd2777',
        'findAllDomains': 'a40de59b1bb2d296', 'findAllSites': '560c4d17518939c0', 'findAllUsers': '555b953e220204c5', 'findAllWebsites': '6dc8f899cf4de30b',
        'findChildDomains': '740e4613901689be', 'findContainersObjects': 'b12ef89611a1e77a', 'findDockersiteObjects': '68cffafbb52a4a39',
        'findWebsiteObjects': 'db20bad6dcf57d2a', 'getPHPString': '63e8732f16202ca5', 'loadAllUsers': '1fd917c7b357eab1', 'loadDeletionUsers': 'd45e89bd8175859c',
        'loadError': '935f599a486ce998', 'loadErrorJson': '004450d82e34701a', 'loadPackageObjects': '34ce5144289d3e71', 'loadPackages': '30cef010fc5ca37e',
        'loadUserObjects': '5cb8948ccff30eec', 'loadedACL': '9d01fdde29fea284', 'searchWebsiteObjects': '0a2ae59e3de6ca57', 'unFileteredACLs': 'dd800b8c0fd25720',
        'userWithResellerPriv': '166f71b1f6861749', 'validateInput': 'b1e9070adc992893', 'websitesLimitCheck': '3c1a87e8f2c6ad0a',
}
check('the other methods untouched by any other change are exactly as they were', {n: fp(ast.get_source_segment(ACL, methods[n])) if n in methods else None for n in PIN}, PIN)
check('the machine address helper stays', 'GetServerIP' in methods, True)

SKIP = ('.git', 'node_modules', 'static', 'public', 'locale')
CALL = re.compile(r'\b' + NAME + r'\b')
callers = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(('.py', '.js', '.html', '.sh')) and not f.startswith('test_') and '.bak' not in f and not f.endswith('.min.js'):
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            if CALL.search(open(os.path.join(base, f), encoding='utf-8', errors='replace').read()):
                callers.append(rel.replace(os.sep, '/'))
check('no code or script names the check', sorted(callers), [])
check('control: the scanner sees a call and a definition when one is present', [bool(CALL.search(x)) for x in ('if ACLManager.' + NAME + "('all'):", '    def ' + NAME + '(feature):', 'def other():')], [True, True, False])

try:
    ast.parse(open(os.path.join(ROOT, 'plogical/acl.py'), 'rb').read(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('plogical/acl.py parses with the Python 3.9 grammar', parsed, True)
check('plogical/acl.py has no carriage returns', b'\r' in open(os.path.join(ROOT, 'plogical/acl.py'), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
