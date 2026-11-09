"""Tests the PHP version fallback of the panel: managePHP/phpManager.py (the fallback lists and PHPManager.pickFallbackVersion) and the two places in
plogical/phpUtilities.py that use it. Until now a site whose PHP version was not installed got the second last entry of the installed versions. That
result must stay the same on a server that has versions up to 8.3, and installing PHP 8.4 or 8.5 later must not move it. The real function is cut out of the
source and run on its own. Run: python3 CPScripts/test_php_fallback_version.py"""
import ast
import os
import re
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MGR = open(os.path.join(ROOT, 'managePHP', 'phpManager.py'), encoding='utf-8').read()
UTIL = open(os.path.join(ROOT, 'plogical', 'phpUtilities.py'), encoding='utf-8').read()

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
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PHPManager')
    keep = [n for n in cls.body if (isinstance(n, ast.FunctionDef) and n.name == 'pickFallbackVersion') or (isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'FALLBACK_ESTABLISHED_UP_TO')]
    for n in keep:
        if isinstance(n, ast.FunctionDef):
            n.decorator_list = []
    new_cls = ast.ClassDef(name='PHPManager', bases=[], keywords=[], body=keep, decorator_list=[])
    ns = {}
    # staticmethod is needed because the real code is decorated; re-add it
    for n in keep:
        if isinstance(n, ast.FunctionDef):
            n.decorator_list = [ast.Name(id='staticmethod', ctx=ast.Load())]
    module = ast.Module(body=[new_cls], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, '<phpManager>', 'exec'), ns)
    return ns['PHPManager']


PM = load(MGR)
pick = PM.pickFallbackVersion

UP_TO_83 = ['PHP 7.4', 'PHP 8.0', 'PHP 8.1', 'PHP 8.2', 'PHP 8.3']
legacy = lambda v: v[-2]  # what the code did before: the second last entry
check('a server with versions up to 8.3 gets what it always got (the second last)', pick(UP_TO_83), legacy(UP_TO_83))
check('the same set in any order', pick(list(reversed(UP_TO_83))), 'PHP 8.2')
check('installing 8.4 does not move the fallback', pick(UP_TO_83 + ['PHP 8.4']), 'PHP 8.2')
check('installing 8.4 and 8.5 does not move the fallback', pick(UP_TO_83 + ['PHP 8.4', 'PHP 8.5']), 'PHP 8.2')
check('a small old server is unchanged too', (pick(['PHP 7.4', 'PHP 8.0']), pick(['PHP 7.0', 'PHP 7.1', 'PHP 7.2'])), ('PHP 7.4', 'PHP 7.1'))
check('only one established version plus newer ones: the second last of all is used', pick(['PHP 8.3', 'PHP 8.4', 'PHP 8.5']), 'PHP 8.4')
check('only newer versions', pick(['PHP 8.4', 'PHP 8.5']), 'PHP 8.4')
check('one version only', pick(['PHP 8.5']), 'PHP 8.5')
try:
    pick([])
    raised = None
except IndexError:
    raised = 'IndexError'
check('nothing installed still raises IndexError as the old code did', raised, 'IndexError')
check('two digit minor versions sort numerically (a text sort would give PHP 8.10)', pick(['PHP 8.9', 'PHP 8.10', 'PHP 7.4']), 'PHP 8.9')

lists = re.findall(r"return \[('PHP 7\.0'[^\]]*)\]", MGR)
FULL = "'PHP 7.0', 'PHP 7.1', 'PHP 7.2', 'PHP 7.3', 'PHP 7.4', 'PHP 8.0', 'PHP 8.1', 'PHP 8.2', 'PHP 8.3', 'PHP 8.4', 'PHP 8.5'"
fallbacks = [l for l in lists if l == FULL]
check('both fallback lists of the version search (used when the disk cannot be read) go up to PHP 8.5', len(fallbacks), 2)
check('no fallback list still stops at PHP 8.1 in live code', [l for l in re.findall(r"^\s+return \[('PHP 7\.0'[^\]]*)\]", MGR, re.M) if l.endswith("'PHP 8.1'")], [])
check('both places in phpUtilities use the new function', (UTIL.count('PHPManager.pickFallbackVersion(PHPManager.findPHPVersions())'), UTIL.count('findPHPVersions()[-2]')), (2, 0))
check('the files have no carriage returns', (b'\r' in open(os.path.join(ROOT, 'managePHP', 'phpManager.py'), 'rb').read(), b'\r' in open(os.path.join(ROOT, 'plogical', 'phpUtilities.py'), 'rb').read()), (False, False))

# control: the old rule moves the fallback when 8.4 and 8.5 appear, which is what the new function prevents
check('control: the old rule would have moved the fallback to 8.4', legacy(UP_TO_83 + ['PHP 8.4', 'PHP 8.5']), 'PHP 8.4')

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
