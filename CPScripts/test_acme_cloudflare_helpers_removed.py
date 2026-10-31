"""Tests that the two helpers that read and wrote Cloudflare credentials in the acme account file are removed after the wildcard SSL page
that was their only caller went: DNS.ConfigureCloudflareInAcme and ACLManager.FetchCloudFlareAPIKeyFromAcme. Nothing in the tree may name them
and the free Cloudflare DNS sync functions and the neighbouring helpers are unchanged (pinned by hash). The names are built here.
Run: python3 CPScripts/test_acme_cloudflare_helpers_removed.py"""
import ast
import hashlib
import os
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


def read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


WRITER = 'ConfigureCloudflare' + 'InAcme'
READER = 'FetchCloudFlareAPIKey' + 'FromAcme'
ACL, DNSU = read('plogical/acl.py'), read('plogical/dnsUtilities.py')


def methods(src, cls):
    c = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == cls)
    return {n.name: n for n in c.body if isinstance(n, ast.FunctionDef)}


def digest(src, node):
    return hashlib.sha256(ast.get_source_segment(src, node).encode()).hexdigest()[:16]


acl, dns = methods(ACL, 'ACLManager'), methods(DNSU, 'DNS')
check('the credential reader is gone from the access helper class', READER in acl, False)
check('the credential writer is gone from the DNS helper class', WRITER in dns, False)

hits, scanned = [], 0
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'static', 'public')]
    for f in files:
        if f.endswith(('.py', '.html', '.js')) and '.bak' not in f and not f.startswith('test_'):
            scanned += 1
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            hits += [(os.path.relpath(os.path.join(base, f), ROOT), n) for n in (WRITER, READER) if n in text]
check('files were scanned across the tree', scanned > 500, True)
check('nothing in the tree names either helper', hits, [])
check('the acme account file is no longer written or searched for the Cloudflare account values by these modules',
      [(rel, w) for rel, src in (('plogical/acl.py', ACL), ('plogical/dnsUtilities.py', DNSU)) for w in ('SAVED_CF' + '_Key', 'SAVED_CF' + '_Email') if w in src], [])

PINS_ACL = {'CheckIPBackupObjectOwner': 'eb4a2533fcc6cc9b', 'CheckIPPluginObjectOwner': '06a61c8e6c107d0b', 'GetServerIP': 'fe182f4839056536', 'GetALLWPObjects': '75b403e73a726349'}
check('four neighbouring access helpers are exactly as they were', {n: digest(ACL, acl[n]) if n in acl else None for n in PINS_ACL}, PINS_ACL)
PINS_DNS = {'getDNSZones': '868638bd4877e957', 'deleteDNSRecord': 'ebb5f5cc66a1ff8a', 'getZoneObject': '048e6df24da9a1d1', 'loadCFKeys': '9d24a75804119f91'}
check('four neighbouring DNS helpers are exactly as they were', {n: digest(DNSU, dns[n]) if n in dns else None for n in PINS_DNS}, PINS_DNS)
check('the free Cloudflare DNS sync functions are still there', [n for n in ('cfTemplate', 'createDNSRecordCloudFlare', 'loadCFKeys') if n not in dns], [])
for rel in ('plogical/acl.py', 'plogical/dnsUtilities.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar and has no carriage returns' % rel, (parsed, b'\r' in open(os.path.join(ROOT, rel), 'rb').read()), (True, False))

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
