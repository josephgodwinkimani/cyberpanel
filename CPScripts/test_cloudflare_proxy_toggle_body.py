"""Tests DNSManager.enableProxy in dns/dnsManager.py: turning the Cloudflare proxy on or off for a record sends only the writable
record fields (type, name, content, ttl, proxied) in the update. The record's id and zone id are already in the request path and
Cloudflare lists them as response fields, so they are not sent in the body. The real method is run with stand-ins for the access
checks and the Cloudflare client (nothing is sent).
Run: python3 CPScripts/test_cloudflare_proxy_toggle_body.py"""
import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'dns', 'dnsManager.py')

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
cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == 'DNSManager')
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'enableProxy')
raw = ast.get_source_segment(src, node)
dedent = lambda text: text.replace('\n' + ' ' * node.col_offset, '\n')
real_src = dedent(raw)

# the old source is rebuilt from the real one by undoing the change (the real source is dedented one level)
pad = ' ' * 12
new_reads = ''.join(pad + line + '\n' for line in ("r_name = dns_record['name']", "r_type = dns_record['type']", "r_content = dns_record['content']", "r_ttl = dns_record['ttl']", "r_proxied = dns_record['proxied']"))
old_reads = pad + "r_zone_id = dns_record['zone_id']\n" + pad + "r_id = dns_record['id']\n" + new_reads + pad + "r_proxiable = dns_record['proxiable']\n"
new_body = pad + "new_dns_record = {\n" + pad + "    'type': r_type,"
old_body = pad + "new_dns_record = {\n" + pad + "    'zone_id': r_zone_id,\n" + pad + "    'id': r_id,\n" + pad + "    'type': r_type,"
assert real_src.count(new_reads) == 1 and real_src.count(new_body) == 1
old_source = real_src.replace(new_reads, old_reads).replace(new_body, old_body)


def record(proxied, **drop):
    r = {'zone_id': 'zone-1', 'id': 'record-9', 'name': 'www.example.test', 'type': 'A', 'content': '192.0.2.10', 'ttl': 1, 'proxied': proxied, 'proxiable': True}
    for key in drop:
        del r[key]
    return r


def build(source, records, allowed=1, owner=1):
    puts = []

    class FakeCloud:
        def __init__(self, email=None, token=None):
            records_api = types.SimpleNamespace(get=lambda zone_id, params=None: list(records), put=lambda zone_id, record_id, data=None: puts.append((zone_id, record_id, data)))
            self.zones = types.SimpleNamespace(get=lambda params=None: [{'id': 'zone-1'}], dns_records=records_api)

    denied = {'status': 0, 'errorMessage': 'denied'}
    acl = types.SimpleNamespace(loadedACL=lambda u: {}, currentContextPermission=lambda a, p: allowed, checkOwnershipZone=lambda z, a, c: owner,
                                loadErrorJson=lambda *a: denied)
    ns = {'json': json, 'HttpResponse': lambda b: json.loads(b), 'ACLManager': acl, 'CloudFlare': types.SimpleNamespace(CloudFlare=FakeCloud),
          'Administrator': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda pk: object()))}
    exec(source, ns)
    me = types.SimpleNamespace(loadCFKeys=lambda: 1, email='user@example.test', key='key')
    return (lambda value: ns['enableProxy'](me, 1, {'selectedZone': 'example.test', 'name': 'www.example.test', 'value': value})), puts


OK = {'status': 1, 'delete_status': 1, 'error_message': 'None'}

# turning the proxy off and on
fn, puts = build(real_src, [record(True)])
r = fn(True)
check('turning the proxy off updates the record and answers success', (r, len(puts)), (OK, 1))
check('the update goes to the right zone and record', (puts[0][0], puts[0][1]), ('zone-1', 'record-9'))
check('the update body holds only the writable fields with the proxy off', puts[0][2], {'type': 'A', 'name': 'www.example.test', 'content': '192.0.2.10', 'ttl': 1, 'proxied': False})

fn, puts = build(real_src, [record(False)])
r = fn(False)
check('turning the proxy on updates the record and answers success', (r, len(puts)), (OK, 1))
check('the update body holds only the writable fields with the proxy on', puts[0][2], {'type': 'A', 'name': 'www.example.test', 'content': '192.0.2.10', 'ttl': 1, 'proxied': True})
check('the body never carries the id or the zone id', [k for k in puts[0][2] if k in ('id', 'zone_id')], [])

# a record that is already in the wanted state is left alone (as before)
fn, puts = build(real_src, [record(True)])
fn(False)
check('a record already in the wanted state is not updated', puts, [])

# the first record that needs a change ends the request (as before)
fn, puts = build(real_src, [record(True), dict(record(True), id='record-10')])
fn(True)
check('only the first record that needs a change is updated as before', [p[1] for p in puts], ['record-9'])

# fields the update no longer reads
fn, puts = build(real_src, [{k: v for k, v in record(True).items() if k not in ('proxiable', 'zone_id')}])
r = fn(True)
check('a record without proxiable and zone_id fields can now be updated', (r, len(puts)), (OK, 1))
fn, puts = build(old_source, [{k: v for k, v in record(True).items() if k not in ('proxiable', 'zone_id')}])
r = fn(True)
check('control: the old code failed on such a record', (r['status'], len(puts)), (0, 0))

# control: the old code sent the id and zone id in the body
fn, puts = build(old_source, [record(True)])
fn(True)
check('control: the old body carried the id and zone id', sorted(k for k in puts[0][2] if k in ('id', 'zone_id')), ['id', 'zone_id'])

# access checks unchanged
fn, puts = build(real_src, [record(True)], allowed=0)
check('without the permission the request is refused and nothing is sent', (fn(True), puts), ({'status': 0, 'errorMessage': 'denied'}, []))
fn, puts = build(real_src, [record(True)], owner=0)
check('for a zone the user does not own the request is refused and nothing is sent', (fn(True), puts), ({'status': 0, 'errorMessage': 'denied'}, []))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('dnsManager.py parses with the Python 3.9 grammar', parsed, True)
check('dnsManager.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
