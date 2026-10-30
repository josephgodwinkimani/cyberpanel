"""Tests WebsiteManager.addNewCron and WebsiteManager.saveCronChanges in websiteFunctions/website.py: the cron line reaches the
worker as exactly one argument and a cron command can never add shell commands of its own. The real methods are run with
stand-ins for the access checks, models and the runner, and the command they build is handed to a real shell with the worker
replaced by a program that prints the arguments it received. Run: python3 CPScripts/test_cron_command_quoting.py"""
import ast
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
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


def find_bash():
    for candidate in (r'C:\Program Files\Git\bin\bash.exe', r'C:\Program Files\Git\usr\bin\bash.exe', shutil.which('bash')):
        if candidate and os.path.exists(candidate):
            try:
                if 'GNU bash' in subprocess.run([candidate, '--version'], capture_output=True, text=True, timeout=20).stdout:
                    return candidate
            except Exception:
                continue
    return None


BASH = find_bash()
if BASH is None:
    print('SKIP  no GNU bash found: the shell checks cannot run')
    sys.exit(0)

src = open(SOURCE, encoding='utf-8').read()
cls = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == 'WebsiteManager')
methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('addNewCron', 'saveCronChanges')}
assert len(methods) == 2


def method_source(name, old_quoting=False):
    node = methods[name]
    raw = ast.get_source_segment(src, node)
    if old_quoting:
        raw = raw.replace('" --finalCron " + shlex.quote(finalCron)', '" --finalCron \'" + finalCron + "\'"')
        raw = raw.replace("shlex.quote(finalCron)", "\"'\" + finalCron + \"'\"")
        assert raw != ast.get_source_segment(src, node)
    return raw.replace('\n' + ' ' * node.col_offset, '\n')


work = tempfile.mkdtemp(prefix='cronq-')
dump = os.path.join(work, 'argdump.py').replace('\\', '/')
open(dump, 'w').write('import sys, json\nprint("ARGS" + json.dumps(sys.argv[1:]))\n')
py = sys.executable.replace('\\', '/')

captured = []


def output_executioner(command, user=None, *a, **k):
    captured.append((command, user))
    cmd = command.replace('/usr/local/CyberCP/bin/python /usr/local/CyberCP/plogical/cronUtil.py', '"%s" "%s"' % (py, dump))
    out = subprocess.run([BASH, '-c', cmd], capture_output=True, text=True, cwd=work).stdout
    return '1,\n' + out


class Site:
    externalApp = 'siteuser'
    domain = 'a.example'


def build(source, name):
    ns = {
        'json': json, 'shlex': shlex, 'HttpResponse': lambda b: json.loads(b),
        'ACLManager': types.SimpleNamespace(loadedACL=lambda u: {'admin': 0}, checkOwnership=lambda d, a, c: 1,
                                            loadErrorJson=lambda *a: {'error': 1}),
        'Administrator': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda pk: object())),
        'Websites': types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda domain: Site)),
        'CronUtil': types.SimpleNamespace(CronPrem=lambda n: None),
        'virtualHostUtilities': types.SimpleNamespace(cyberPanel='/usr/local/CyberCP'),
        'ProcessUtilities': types.SimpleNamespace(
            outputExecutioner=output_executioner, executioner=lambda *a, **k: 1, decideDistro=lambda: 'centos',
            centos='centos', cent8='cent8', ubuntu='ubuntu', ubuntu20='ubuntu20'),
    }
    exec(source, ns)
    fn = ns[name]
    return lambda data: fn(types.SimpleNamespace(), 1, data)


def run(fn, command, line=None):
    del captured[:]
    data = {'domain': 'a.example', 'minute': '*/5', 'hour': '*', 'monthday': '*', 'month': '*', 'weekday': '*', 'cronCommand': command}
    if line is not None:
        data['line'] = line
    r = fn(data)
    out = captured[0][0] if captured else ''
    # what the worker received, as printed by the replacement program
    cmd = out.replace('/usr/local/CyberCP/bin/python /usr/local/CyberCP/plogical/cronUtil.py', '"%s" "%s"' % (py, dump))
    res = subprocess.run([BASH, '-c', cmd], capture_output=True, text=True, cwd=work).stdout
    args = None
    injected = False
    for l in res.splitlines():
        if l.startswith('ARGS'):
            args = json.loads(l[4:])
        if l.strip() == 'INJECTED':
            injected = True
    return r, args, injected


COMMANDS = {
    'plain command': '/usr/bin/php /home/a.example/public_html/cron.php',
    'command with a pipe and redirect': 'cd /home/a.example && ls | wc -l > /tmp/n',
    'command with double quotes': 'echo "hello world"',
    'command with single quotes': "echo 'hello world'",
    'command with a dollar sign': 'echo $HOME',
}
HOSTILE = {
    'single quote break-out': "x'; echo INJECTED; echo '",
    'break-out with substitution': "x'$(echo INJECTED)'",
    'newline command': "x\necho INJECTED\n",
}

for method in ('addNewCron', 'saveCronChanges'):
    real = build(method_source(method), method)
    old = build(method_source(method, old_quoting=True), method)
    line = 3 if method == 'saveCronChanges' else None
    for label, cmd in COMMANDS.items():
        expected = '*/5 * * * * ' + cmd
        r, args, injected = run(real, cmd, line)
        want_args = ['addNewCron' if method == 'addNewCron' else 'saveCronChanges', '--externalApp', 'siteuser'] + (['--line', '3'] if line else []) + ['--finalCron', expected]
        check('%s, %s: the worker receives the cron line as one argument' % (method, label), (args, injected), (want_args, False))
    for label, cmd in HOSTILE.items():
        r, args, injected = run(real, cmd, line)
        check('%s, %s: no extra command runs' % (method, label), injected, False)
        check('%s, %s: the whole text is still the one cron argument' % (method, label), args is not None and args[-1] == '*/5 * * * * ' + cmd, True)
    _, _, injected_old = run(old, HOSTILE['single quote break-out'], line)
    check('control: %s with the old quoting runs the injected command' % method, injected_old, True)
    # a plain cron line is passed exactly as before
    r, args_new, _ = run(real, COMMANDS['plain command'], line)
    r, args_old, _ = run(old, COMMANDS['plain command'], line)
    check('%s: a plain cron line gives the worker the same arguments as the old code' % method, args_new, args_old)
    check('%s: the response still reports success' % method, list(r.values())[0], 1)

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('website.py parses with the Python 3.9 grammar', parsed, True)
check('website.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

shutil.rmtree(work, ignore_errors=True)
print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
