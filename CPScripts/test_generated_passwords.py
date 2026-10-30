"""Tests the two runtime password generators (plogical/randomPassword.py and the copy inside plogical/acl.py): they draw
from the secrets module, and keep the alphabet, length and call shape they always had.
Run: python3 CPScripts/test_generated_passwords.py"""
import ast
import importlib.util
import os
import random
import secrets
import string
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RP = os.path.join(ROOT, 'plogical', 'randomPassword.py')
ACL = os.path.join(ROOT, 'plogical', 'acl.py')

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


ALPHABET = set(string.ascii_uppercase + string.ascii_lowercase + string.digits)

spec = importlib.util.spec_from_file_location('random_password_under_test', RP)
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

acl_src = open(ACL, encoding='utf-8').read()
acl_node = next(n for n in ast.walk(ast.parse(acl_src)) if isinstance(n, ast.FunctionDef) and n.name == 'generate_pass')
acl_ns = {'string': string, 'secrets': secrets}
exec(ast.get_source_segment(acl_src, acl_node).replace('\n' + ' ' * acl_node.col_offset, '\n'), acl_ns)

GENERATORS = (('plogical/randomPassword.generate_pass', rp.generate_pass), ('plogical/acl.py generate_pass', acl_ns['generate_pass']))

for label, gen in GENERATORS:
    p = gen()
    check('%s: default length is 14' % label, len(p), 14)
    check('%s: only letters and digits' % label, set(p) <= ALPHABET, True)
    check('%s: other lengths are honoured (1, 32, 50)' % label, [len(gen(n)) for n in (1, 32, 50)], [1, 32, 50])
    check('%s: length 0 gives an empty string as before' % label, gen(0), '')
    sample = [gen() for _ in range(2000)]
    check('%s: 2000 passwords are all different' % label, len(set(sample)), 2000)
    seen = set()
    for _ in range(4000):
        seen |= set(gen(40))
    check('%s: every one of the 62 characters shows up' % label, seen, ALPHABET)

    # the random module is not used: make it fail if anything calls it
    original = random.choice
    random.choice = lambda *a, **k: (_ for _ in ()).throw(AssertionError('random.choice was called'))
    try:
        gen(20)
        used_random = False
    except AssertionError:
        used_random = True
    finally:
        random.choice = original
    check('%s: random.choice is never called' % label, used_random, False)

# the secrets module is what supplies the characters
calls = []
real_choice = secrets.choice
secrets.choice = lambda seq: (calls.append(1), real_choice(seq))[1]
try:
    rp.generate_pass(10)
    n1 = len(calls)
    del calls[:]
    acl_ns['generate_pass'](10)
    n2 = len(calls)
finally:
    secrets.choice = real_choice
check('both generators draw every character from secrets.choice', (n1, n2), (10, 10))

check('plogical/randomPassword.py no longer imports random', 'random' in vars(rp), False)
check('plogical/acl.py no longer uses random.choice', 'random.choice' in acl_src, False)

for label, path in (('randomPassword.py', RP), ('acl.py', ACL)):
    data = open(path, 'rb').read()
    try:
        ast.parse(data, feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % label, parsed, True)
    check('%s has no carriage returns' % label, b'\r' in data, False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
