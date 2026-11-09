"""Tests backupUtilities.startRestore in plogical/backupUtilities.py: restoring a website no longer asks the add-on licence service
whether it may restore an Apache backend configuration. The two Apache steps (the child domain one and the main site one) now run
under their own conditions only: the vhost file of the backup names an Apache backend and the backup holds the Apache file.
Everything else in the file is unchanged (checked by a hash of the file without those two steps). The real code of both steps is
run against real temporary files with stand-ins for the web server helpers and a request library that fails on any call.
Run: python3 CPScripts/test_restore_without_licence_service.py"""
import ast
import hashlib
import os
import sys
import tempfile
import textwrap
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'plogical', 'backupUtilities.py')

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
LINES = src.split('\n')

CHILD = ('### take care of apache conf', '### apache ends')
MAIN = ('### apache starts here', '### apache ends here')


def region(markers):
    start = [i for i, l in enumerate(LINES) if l.strip() == markers[0]]
    assert len(start) == 1
    end = next(i for i in range(start[0], len(LINES)) if LINES[i].strip() == markers[1])
    return start[0], end


def without_regions(text):
    out, skipping, end = [], False, None
    for l in text.split('\n'):
        t = l.strip()
        if not skipping and t in (CHILD[0], MAIN[0]):
            skipping, end = True, (CHILD[1] if t == CHILD[0] else MAIN[1])
            continue
        if skipping:
            if t == end:
                skipping = False
            continue
        out.append(l)
    return '\n'.join(out)


cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == 'backupUtilities')
restore = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'startRestore']
check('there is one startRestore', len(restore), 1)
check('outside the two Apache steps startRestore is exactly as it was', hashlib.sha256(without_regions(ast.get_source_segment(src, restore[0])).encode()).hexdigest()[:16], '840d6ac419da4a75')
# the marker names are built here so this file does not name them
check('the file no longer names the licence service', any(w in src for w in ('Adon' + 'permission', 'platform.' + 'cyberpersons', 'CheckFor' + 'PremFeature')), False)


def snippet(markers):
    a, b = region(markers)
    return textwrap.dedent('\n'.join(LINES[a:b + 1]))


calls = []


class FakeRequests:
    @staticmethod
    def post(url, *a, **k):
        calls.append(url)
        raise AssertionError('licence service called')


sys.modules['requests'] = FakeRequests


def old_form(code, status):
    """The same step in its old form: asks the service first and runs the rest only when the answer is 1."""
    first, rest = code.split('\n', 1)
    ask = ('Status = %d\nif (Status == 1):\n' % status)
    body = '\n'.join(('    ' + l) if l.strip() else l for l in rest.split('\n'))
    return first + '\n' + ask + body


def run(code, variant, apache_in_vhost=True, apache_file=True, final_exists=True):
    """Runs one Apache step. variant is 'child' or 'main'. Returns what the step did."""
    tmp = tempfile.mkdtemp()
    backup = os.path.join(tmp, 'backup')
    os.makedirs(backup)
    conf_dir = os.path.join(tmp, 'apache')
    os.makedirs(conf_dir)
    vhost = os.path.join(backup, 'vhost.conf')
    open(vhost, 'w').write('docRoot /home/x\n' + ('proxyApacheBackendSSL on\n' if apache_in_vhost else ''))
    apache_name = 'example.test.apache.conf' if variant == 'child' else 'apache.conf'
    apache_path = os.path.join(backup, apache_name)
    if apache_file:
        open(apache_path, 'w').write('apache config\n')
    log, copies, switches = [], [], []

    def switch(domain, php, server, status):
        switches.append((domain, php, server, status))
        if final_exists:
            open(os.path.join(conf_dir, domain + '.conf'), 'w').write('converted\n')

    ns = {'os': os, 'completPath': backup, 'domain': 'example.test', 'masterDomain': 'example.test', 'phpSelection': 'PHP 7.4',
          'phpSelectionGlobalMainSite': 'PHP 7.4', 'childConfPathinBKUP': vhost, 'confPathMainSite': vhost,
          'ProcessUtilities': types.SimpleNamespace(debugPath='/nonexistent/debug'),
          'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=log.append)),
          'virtualHostUtilities': types.SimpleNamespace(switchServer=switch, apache='apache'),
          'ApacheVhost': types.SimpleNamespace(configBasePath=conf_dir + '/'),
          'copy': lambda a, b: copies.append((os.path.basename(a), os.path.basename(b)))}
    if variant == 'child':
        ns['completPath'] = backup
        # the child step builds its Apache file name from completPath and the domain
    del calls[:]
    try:
        exec(code, ns)
        error = None
    except BaseException as exc:
        error = '%s: %s' % (type(exc).__name__, exc)
    return {'error': error, 'switches': switches, 'copies': copies, 'outbound': list(calls)}


STEPS = (('child', CHILD, 'example.test.apache.conf'), ('main', MAIN, 'apache.conf'))
for variant, markers, apache_name in STEPS:
    code = snippet(markers)
    label = 'the %s step' % variant
    full = run(code, variant)
    check('%s restores the Apache configuration when the backup holds one and makes no outbound call' % label,
          (full['error'], full['switches'], full['copies'], full['outbound']),
          (None, [('example.test', 'PHP 7.4', 'apache', '/home/cyberpanel/fakePath')], [(apache_name, 'example.test.conf')], []))
    check('%s does nothing when the vhost file of the backup names no Apache backend' % label, run(code, variant, apache_in_vhost=False),
          {'error': None, 'switches': [], 'copies': [], 'outbound': []})
    check('%s does nothing when the backup has no Apache file' % label, run(code, variant, apache_file=False),
          {'error': None, 'switches': [], 'copies': [], 'outbound': []})
    r = run(code, variant, final_exists=False)
    check('%s switches but copies nothing when the converted configuration does not appear' % label,
          (r['error'], len(r['switches']), r['copies']), (None, 1, [] if variant == 'child' else [(apache_name, 'example.test.conf')]))

    # controls: the old form of the step
    r = run(old_form(code, 1), variant)
    check('control: the old step with a yes answer restored the same way (nothing is lost for installs where the answer was yes) (%s)' % variant,
          (r['error'], r['switches'], r['copies']), (None, full['switches'], full['copies']))
    r = run(old_form(code, 0), variant)
    check('control: the old step with a no answer skipped the Apache restore for the same backup (%s)' % variant,
          (r['error'], r['switches'], r['copies']), (None, [], []))
    fail_form = old_form(code, 1).replace('Status = 1', 'import requests\nStatus = requests.post("https://licence.invalid/check", data="{}").text')
    r = run(fail_form, variant)
    check('control: an old step whose service call fails raises where the restore would stop (%s)' % variant, (r['error'], len(r['outbound'])), ('AssertionError: licence service called', 1))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('backupUtilities.py parses with the Python 3.9 grammar', parsed, True)
check('backupUtilities.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
