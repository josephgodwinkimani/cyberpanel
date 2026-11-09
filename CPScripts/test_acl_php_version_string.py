"""Tests that ACLManager.getPHPString (plogical/acl.py) maps every PHP version string to its digits, including PHP 8.5, and that a later version without
its own branch no longer ends in an unbound variable. The real function is cut out of the source and run on its own, nothing else of the file is imported.
Run: python3 CPScripts/test_acl_php_version_string.py"""
import ast
import os
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_PATH = os.path.join(ROOT, 'plogical', 'acl.py')

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def load(source):
    """The function getPHPString of the class ACLManager, as a plain callable."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(source)
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'ACLManager')
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'getPHPString')
    func.decorator_list = []
    module = ast.Module(body=[func], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, '<getPHPString>', 'exec'), ns)
    return ns['getPHPString']


SOURCE = open(SRC_PATH, encoding='utf-8').read()
get = load(SOURCE)

KNOWN = {'PHP 5.3': '53', 'PHP 5.4': '54', 'PHP 5.5': '55', 'PHP 5.6': '56', 'PHP 7.0': '70', 'PHP 7.1': '71', 'PHP 7.2': '72', 'PHP 7.3': '73', 'PHP 7.4': '74',
         'PHP 8.0': '80', 'PHP 8.1': '81', 'PHP 8.2': '82', 'PHP 8.3': '83', 'PHP 8.4': '84'}
check('every version that had a branch before gives the same digits', {k: get(k) for k in KNOWN}, KNOWN)
check('PHP 8.5 gives 85', get('PHP 8.5'), '85')
check('a later version without a branch gives its digits', (get('PHP 8.6'), get('PHP 9.0'), get('PHP 10.1')), ('86', '90', '101'))
check('the explicit branch for PHP 8.5 exists (not only the default)', 'elif phpVersion == "PHP 8.5":' in SOURCE, True)

# control: the old function (no branch for 8.5 and no default) fails on 8.5 with an unbound variable
OLD = SOURCE.replace('''        elif phpVersion == "PHP 8.5":
            php = "85"
        else:''', '''        else:''', 1)
old_get = load(OLD.replace('''            php = phpVersion.split()[1].replace(".", "")''', '''            pass''', 1))
try:
    old_get('PHP 8.5')
    raised = None
except UnboundLocalError:
    raised = 'UnboundLocalError'
check('control: without the new branch and default PHP 8.5 raises UnboundLocalError', raised, 'UnboundLocalError')
check('plogical/acl.py has no carriage returns', b'\r' in open(SRC_PATH, 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
