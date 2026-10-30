"""Tests DNS.ConfigureCloudflareInAcme in plogical/dnsUtilities.py: the Cloudflare key and email are written to the acme.sh
account file literally, and a value that could run a command (when the command is built or when acme.sh sources the file)
is refused before anything is changed. The real function source is run with its file path pointed at a temporary file and
its commands executed by a real shell. Run: python3 CPScripts/test_cloudflare_acme_credentials.py"""
import ast
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), 'plogical', 'dnsUtilities.py')
LIVE_PATH = '/root/.acme.sh/account.conf'

total = ok = skipped = 0


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
                out = subprocess.run([candidate, '--version'], capture_output=True, text=True, timeout=20).stdout
            except Exception:
                continue
            if 'GNU bash' in out:
                return candidate
    return None


BASH = find_bash()
if BASH is None:
    print('SKIP  no GNU bash found: the shell checks cannot run')
    sys.exit(0)

src = open(SOURCE, encoding='utf-8').read()
node = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == 'ConfigureCloudflareInAcme')
func_src = ast.get_source_segment(src, node)
assert LIVE_PATH in func_src
func_src = func_src.replace('\n' + ' ' * node.col_offset, '\n')

work = tempfile.mkdtemp(prefix='cfacme-')
conf = os.path.join(work, 'account.conf').replace('\\', '/')
marker = os.path.join(work, 'MARKER').replace('\\', '/')
func_src = func_src.replace(LIVE_PATH, conf)

calls = []


def executioner(command, user=None, shell=False):
    calls.append((command, shell))
    if shell:
        subprocess.run([BASH, '-c', command], cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run([BASH, '-c', 'exec "$@"', 'x'] + shlex.split(command), cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 1


logged = []
ns = {
    'shlex': shlex,
    'ProcessUtilities': types.SimpleNamespace(executioner=executioner),
    'logging': types.SimpleNamespace(CyberCPLogFileWriter=types.SimpleNamespace(writeToFile=lambda m: logged.append(m))),
}
exec('import types\n' + func_src.replace('@staticmethod\n', ''), ns)
configure = ns['ConfigureCloudflareInAcme']


def reset(initial):
    for f in (conf, marker):
        if os.path.exists(f):
            os.remove(f)
    del calls[:]
    del logged[:]
    if initial is not None:
        open(conf, 'w', newline='\n').write(initial)


def read():
    return open(conf, newline='').read() if os.path.exists(conf) else None


def source_value(name):
    """What acme.sh would see after sourcing the file."""
    r = subprocess.run([BASH, '-c', '. "$1"; printf %s "$' + name + '"', 'x', conf], cwd=work, capture_output=True, text=True)
    return r.stdout


KEY = '0123456789abcdef0123456789abcdef01234'
EMAIL = 'admin@example.test'
OTHER = "ACCOUNT_EMAIL='someone@example.test'\nUSER_PATH='/root/.acme.sh'\n"

# normal save keeps the file exactly as before
reset(OTHER)
res = configure(KEY, EMAIL)
check('a normal save succeeds', res, (1, None))
check('the other lines are kept and the two new ones are appended exactly as before', read(), OTHER + "\nSAVED_CF_Key='%s'\nSAVED_CF_Email='%s'\n\n" % (KEY, EMAIL))
check('acme.sh reads the same key and email back', (source_value('SAVED_CF_Key'), source_value('SAVED_CF_Email')), (KEY, EMAIL))

# the new file is byte for byte what the old command wrote for normal values
reset(OTHER)
content = "\nSAVED_CF_Key='%s'\nSAVED_CF_Email='%s'\n" % (KEY, EMAIL)
subprocess.run([BASH, '-c', 'echo "%s" >> %s' % (content, conf)], cwd=work)
old_bytes = read()
reset(OTHER)
configure(KEY, EMAIL)
check('output for normal values is identical to the old command', read(), old_bytes)

# saving twice replaces the old pair
reset(OTHER)
configure('oldkey', 'old@example.test')
configure(KEY, EMAIL)
text = read()
check('a second save replaces the first (one key line, one email line)', (text.count('SAVED_CF_Key'), text.count('SAVED_CF_Email'), source_value('SAVED_CF_Key')), (1, 1, KEY))

# values the panel's input filter lets through are written literally and run nothing
hostile = {
    'double quote break-out': 'x"; touch ' + marker + '; echo "',
    'command substitution': 'x$(touch ' + marker + ')',
    'backticks': 'x`touch ' + marker + '`',
    'backslash and double quote': 'a\\"b',
    'spaces and redirect': 'x" > ' + marker + ' "',
}
for label, value in hostile.items():
    reset(OTHER)
    res = configure(value, EMAIL)
    check('%s: saved' % label, res, (1, None))
    check('%s: no command ran' % label, os.path.exists(marker), False)
    check('%s: acme.sh reads the value back unchanged' % label, source_value('SAVED_CF_Key'), value)
    check('%s: the email line is still intact' % label, source_value('SAVED_CF_Email'), EMAIL)

# the old command is shown to be injectable with the same input, so the checks above are not vacuous
reset(OTHER)
bad = hostile['double quote break-out']
subprocess.run([BASH, '-c', 'echo "%s" >> %s' % ("\nSAVED_CF_Key='%s'\n" % bad, conf)], cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
check('control: the old command would have run the injected command', os.path.exists(marker), True)

# values that would break out of the single quotes in the sourced file are refused and change nothing
for label, value in (("a single quote", "x'; touch " + marker + "; '"), ('a line break', 'x\ntouch ' + marker), ('a carriage return', 'x\rtouch'), ('a NUL', 'x\0y')):
    for field in ('key', 'email'):
        reset(OTHER + "SAVED_CF_Key='keep'\nSAVED_CF_Email='keep@example.test'\n")
        before = read()
        res = configure(value if field == 'key' else KEY, value if field == 'email' else EMAIL)
        check('%s in the %s: refused' % (label, field), (res[0], 'quotes or line breaks' in res[1]), (0, True))
        check('%s in the %s: the file is untouched and nothing ran' % (label, field), (read() == before, calls, os.path.exists(marker)), (True, [], False))

# a missing field keeps the old behaviour (written as text), it is not a new failure
reset(OTHER)
check('a missing value (None) is handled as before', configure(None, EMAIL), (1, None))

try:
    ast.parse(src.encode(), feature_version=(3, 9))
    parsed = True
except SyntaxError:
    parsed = False
check('dnsUtilities.py parses with the Python 3.9 grammar', parsed, True)
check('dnsUtilities.py has no carriage returns', b'\r' in open(SOURCE, 'rb').read(), False)

shutil.rmtree(work, ignore_errors=True)
print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
