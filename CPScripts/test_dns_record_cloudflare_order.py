"""Tests DNS.createDNSRecord in plogical/dnsUtilities.py: the record sent to Cloudflare after a record is added in the panel carries
the priority and the TTL in the order DNS.createDNSRecordCloudFlare takes them (priority first), as every other caller does.
The real method is run with stand-ins for the database, the Cloudflare client and the command runner (nothing is written or sent).
Run: python3 CPScripts/test_dns_record_cloudflare_order.py"""
import ast
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, 'plogical', 'dnsUtilities.py')

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
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DNS')
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'createDNSRecord')
raw = ast.get_source_segment(src, node)
dedent = lambda text: text.replace('\n' + ' ' * node.col_offset, '\n')
real_src = dedent(raw)

call = 'DNS.createDNSRecordCloudFlare(cf, zone, name, type, value, priority, ttl)'
swapped = 'DNS.createDNSRecordCloudFlare(cf, zone, name, type, value, ttl, priority)'
assert raw.count(call) == 1
swapped_src = dedent(raw.replace(call, swapped))


def build(source, sync='Enable'):
    sent, saved = [], []

    class NoRows(list):
        def count(self):
            return 0

    class FakeRecords:
        class objects:
            @staticmethod
            def filter(**kw):
                return NoRows()

        def __init__(self, **kw):
            self.kw = kw

        def save(self):
            saved.append(self.kw)

    class FakeCloud:
        def __init__(self, email=None, token=None):
            self.zones = types.SimpleNamespace(get=lambda params=None: [{'name': params['name'], 'id': 'zone-id'}])

    class FakeDNS:
        def __init__(self):
            self.email, self.key, self.status = 'user@example.test', 'key', sync

        def loadCFKeys(self):
            return 1

        @staticmethod
        def createDNSRecordCloudFlare(cf, zone, name, type, value, priority, ttl):
            sent.append({'zone': zone, 'name': name, 'type': type, 'value': value, 'priority': priority, 'ttl': ttl})

    pu = types.SimpleNamespace(decideDistro=lambda: 'centos', ubuntu='ubuntu', ubuntu20='ubuntu20', executioner=lambda *a, **k: None,
                               outputExecutioner=lambda *a, **k: '')
    ns = {'Records': FakeRecords, 'DNS': FakeDNS, 'ProcessUtilities': pu,
          'CloudFlare': types.SimpleNamespace(CloudFlare=FakeCloud, exceptions=types.SimpleNamespace(CloudFlareAPIError=type('CloudFlareAPIError', (Exception,), {}))),
          'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=lambda m: None))}
    exec(source, ns)
    zone = types.SimpleNamespace(type='NATIVE', id=7, name='example.test', admin=object())
    return (lambda *a: ns['createDNSRecord'](zone, *a)), sent, saved


# the record sent to Cloudflare
fn, sent, saved = build(real_src)
fn('www.example.test', 'A', '192.0.2.10', 0, 3600)
check('an A record is sent with priority 0 and its own TTL', sent, [{'zone': 'zone-id', 'name': 'www.example.test', 'type': 'A', 'value': '192.0.2.10', 'priority': 0, 'ttl': 3600}])

fn, sent, saved = build(real_src)
fn('example.test', 'MX', 'mail.example.test', 10, 3600)
check('an MX record still returns before the Cloudflare step as before', (sent, len(saved)), ([], 1))

fn, sent, saved = build(real_src)
fn('_sip._tcp.example.test', 'SRV', '5 5060 sip.example.test', 5, 300)
check('an SRV record is sent with its own priority and TTL', [(s['priority'], s['ttl']) for s in sent], [(5, 300)])

# the local record is unchanged
fn, sent, saved = build(real_src)
fn('www.example.test', 'A', '192.0.2.10', 0, 3600)
check('the local record is saved with the same TTL and priority as before', [(s['ttl'], s['prio'], s['type']) for s in saved], [(3600, 0, 'A')])

# nothing is sent when the sync is off, and the types that return early are untouched
fn, sent, saved = build(real_src, sync='Disable')
fn('www.example.test', 'A', '192.0.2.10', 0, 3600)
check('nothing is sent to Cloudflare when the sync is not enabled', sent, [])
fn, sent, saved = build(real_src)
fn('example.test', 'TXT', 'v=spf1 -all', 0, 3600)
check('a TXT record still returns before the Cloudflare step as before', (sent, len(saved)), ([], 1))

# control: the old call really swaps the two values
fn, sent, saved = build(swapped_src)
fn('_sip._tcp.example.test', 'SRV', '5 5060 sip.example.test', 5, 300)
check('control: with the old call the SRV priority sent would be the TTL (300) and the TTL would be 5', [(s['priority'], s['ttl']) for s in sent], [(300, 5)])
fn, sent, saved = build(swapped_src)
fn('www.example.test', 'A', '192.0.2.10', 0, 3600)
check('control: with the old call an A record would be sent with priority 3600 and TTL 0', [(s['priority'], s['ttl']) for s in sent], [(3600, 0)])


# every caller of createDNSRecordCloudFlare passes the priority before the TTL
def calls_in(path):
    text = open(path, encoding='utf-8').read()
    found = []
    for n in ast.walk(ast.parse(text)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'createDNSRecordCloudFlare':
            found.append([ast.get_source_segment(text, a) for a in n.args])
    return found


all_calls = calls_in(SOURCE) + calls_in(os.path.join(ROOT, 'dns', 'dnsManager.py'))
check('there are 14 callers of createDNSRecordCloudFlare in the panel', len(all_calls), 14)
check('every caller has 7 arguments', {len(c) for c in all_calls}, {7})
check('no caller passes the TTL before the priority', [c for c in all_calls if c[5] == 'ttl' and c[6] == 'priority'], [])

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('dnsUtilities.py parses with the Python 3.9 grammar', parsed, True)
check('dnsUtilities.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
