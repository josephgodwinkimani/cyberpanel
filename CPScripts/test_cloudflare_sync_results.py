"""Tests DNS.cfTemplate in plogical/dnsUtilities.py: it always returns a (status, message) pair that the Sync CloudFlare handler can
unpack. A zone without saved Cloudflare credentials and an unexpected error used to give no pair (None or a NameError), and the
normal paths are unchanged. The real method is run with stand-ins for the database and the Cloudflare client (nothing is sent).
Run: python3 CPScripts/test_cloudflare_sync_results.py"""
import ast
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'plogical', 'dnsUtilities.py')

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
cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == 'DNS')
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'cfTemplate')
raw = ast.get_source_segment(src, node)
dedent = lambda text: text.replace('\n' + ' ' * node.col_offset, '\n')
real_src = dedent(raw)

# the old source is rebuilt from the real one by undoing the two changes (the real source is dedented one level)
credential_line = "\n        return 0, 'Cloudflare credentials are not configured.'\n"
outer_new = "    except BaseException as msg:\n        return 0, str(msg)"
assert real_src.count(credential_line) == 1
assert real_src.count(outer_new) == 1
old_source = real_src.replace(credential_line, '\n').replace(outer_new, "    except BaseException as msg:\n        return 0, str(e)")

APIError = type('CloudFlareAPIError', (Exception,), {})


def build(source, credentials=1, status='Enable', zones=None, post_error=None, load_error=None):
    created, posted, sent = [], [], []

    class FakeCloud:
        def __init__(self, email=None, token=None):
            def zones_get(params=None):
                return list(zones or [])

            def zones_post(data=None):
                if post_error:
                    raise post_error
                posted.append(data)
                return {'id': 'new-zone'}

            self.zones = types.SimpleNamespace(get=zones_get, post=zones_post)

    class FakeDNS:
        @staticmethod
        def createDNSRecordCloudFlare(cf, zone, name, type, value, priority, ttl):
            sent.append((zone, name, type, value, priority, ttl))

    rows = [types.SimpleNamespace(name='example.test', type='A', content='192.0.2.1', prio=0, ttl=3600),
            types.SimpleNamespace(name='example.test', type='MX', content='mail.example.test', prio=10, ttl=3600)]
    ns = {'DNS': FakeDNS, 'CloudFlare': types.SimpleNamespace(CloudFlare=FakeCloud, exceptions=types.SimpleNamespace(CloudFlareAPIError=APIError)),
          'Domains': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda name: types.SimpleNamespace(id=5))),
          'Records': types.SimpleNamespace(objects=types.SimpleNamespace(filter=lambda domain_id: rows)),
          'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=lambda m: None))}
    exec(source, ns)

    def load():
        if load_error:
            raise load_error
        return credentials

    me = types.SimpleNamespace(loadCFKeys=load, email='user@example.test', key='key', status=status)
    return (lambda zone='example.test', enableCheck=None: ns['cfTemplate'](me, zone, object(), enableCheck)), sent, posted


# the paths that did not give a (status, message) pair
fn, sent, posted = build(real_src, credentials=0)
check('no saved credentials: a (0, message) pair is returned and nothing is sent', (fn(), sent, posted), ((0, 'Cloudflare credentials are not configured.'), [], []))
fn, sent, posted = build(old_source, credentials=0)
check('control: the old code returned no pair at all when credentials were missing', fn(), None)

fn, sent, posted = build(real_src, load_error=RuntimeError('credential file unreadable'))
check('an unexpected error comes back as (0, its message)', fn(), (0, 'credential file unreadable'))
fn, sent, posted = build(old_source, load_error=RuntimeError('credential file unreadable'))
try:
    fn()
    raised = None
except BaseException as exc:
    raised = isinstance(exc, NameError)
check('control: the old code raised a NameError from its own error handler instead', raised, True)

# the paths that must not change
fn, sent, posted = build(real_src, status='Disable')
check('sync not enabled with the check requested is unchanged', (fn(enableCheck=True), sent), ((0, 'Sync not enabled.'), []))
fn, sent, posted = build(real_src, status='Enable')
check('sync enabled with the check requested goes on to sync', fn(enableCheck=True)[0], 1)

fn, sent, posted = build(real_src, zones=[{'name': 'example.test', 'id': 'zone-a'}])
check('an existing Cloudflare zone is synced with every record and returns (1, None)', (fn(), sent, posted), ((1, None), [('zone-a', 'example.test', 'A', '192.0.2.1', 0, 3600), ('zone-a', 'example.test', 'MX', 'mail.example.test', 10, 3600)], []))

fn, sent, posted = build(real_src, zones=[])
check('a missing zone is created and then synced and returns (1, None)', (fn(), [s[0] for s in sent], posted), ((1, None), ['new-zone', 'new-zone'], [{'jump_start': False, 'name': 'example.test'}]))

fn, sent, posted = build(real_src, zones=[], post_error=APIError('zone limit reached'))
check('a Cloudflare error while creating the zone is returned as (0, message)', (fn(), sent), ((0, 'zone limit reached'), []))
fn, sent, posted = build(old_source, zones=[], post_error=APIError('zone limit reached'))
check('the same case behaves the same in the old code', fn(), (0, 'zone limit reached'))

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
