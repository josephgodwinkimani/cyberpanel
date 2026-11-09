"""Tests that the upgrade records the installed version in the panel database.
plogical/upgrade.py has a function upgradeVersion() that writes the VERSION and BUILD constants of the upgrade script into the
database row of the baseTemplate version table. The call was commented out, so that row kept the number of the first
installation after every upgrade. The call now runs right after the permissions step. The function is cut out of the source
and run against fake django and model modules, nothing real is imported or changed.
Run: python3 CPScripts/test_upgrade_records_version.py"""
import ast
import os
import sys
import types
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = open(os.path.join(ROOT, 'plogical', 'upgrade.py'), encoding='utf-8').read()

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


lines = SOURCE.splitlines()
calls = [i for i, l in enumerate(lines) if l.strip() == 'Upgrade.upgradeVersion()']
commented = [l for l in lines if l.strip().startswith('#') and 'upgradeVersion()' in l]
check('the call is present exactly once and is not commented out', (len(calls), commented), (1, []))

# the call sits between the permissions step and the SSL connections step of the main upgrade
neighbours = [l.strip() for l in lines[max(calls[0] - 4, 0):calls[0] + 3] if l.strip() and not l.strip().startswith('#')] if calls else []
check('the call runs after fixPermissions and before UpdateMaxSSLCons', neighbours, ['Upgrade.fixPermissions()', 'Upgrade.upgradeVersion()', 'Upgrade.UpdateMaxSSLCons()'])

with warnings.catch_warnings():
    warnings.simplefilter('ignore')  # the file holds old regular expressions with plain backslashes, not part of this check
    tree = ast.parse(SOURCE)
func = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'upgradeVersion':
        func = node
check('upgradeVersion is defined once as a static method of the upgrade class', (func is not None, [type(d).__name__ + ':' + getattr(d, 'id', '') for d in func.decorator_list]), (True, ['Name:staticmethod']))


def run(version, build, rows, raise_in_get=False):
    """Run the real function body against fakes. rows is the list of rows the fake table holds (key 1 is the first)."""
    saved = []

    class Row:
        def __init__(self):
            self.currentVersion = rows[0]
            self.build = rows[1]

        def save(self):
            saved.append((self.currentVersion, self.build))

    class Manager:
        def get(self, pk):
            if raise_in_get:
                raise LookupError('no row')
            assert pk == 1
            return Row()

    models = types.ModuleType('baseTemplate.models')
    models.version = types.SimpleNamespace(objects=Manager())
    package = types.ModuleType('baseTemplate')
    package.models = models
    fake_django = types.ModuleType('django')
    fake_django.setup = lambda: None
    old = {k: sys.modules.get(k) for k in ('django', 'baseTemplate', 'baseTemplate.models')}
    sys.modules.update({'django': fake_django, 'baseTemplate': package, 'baseTemplate.models': models})
    try:
        source = ast.unparse(ast.Module(body=[ast.FunctionDef(name=func.name, args=func.args, body=func.body, decorator_list=[], returns=None, lineno=1, col_offset=0)], type_ignores=[]))
        namespace = {'os': os, 'VERSION': version, 'BUILD': build}
        exec(source, namespace)
        namespace['upgradeVersion']()
    finally:
        for k, v in old.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return saved


check('an old row is rewritten with the version and build of the upgrade script (build as text)', run('3.0', 0, ('2.3', '9')), [('3.0', '0')])
check('a row that already has the number is saved with the same number', run('3.0', 0, ('3.0', '0')), [('3.0', '0')])
check('a missing row is not an error (the function swallows it as before and saves nothing)', run('3.0', 0, ('2.3', '9'), raise_in_get=True), [])

raw = open(os.path.join(ROOT, 'plogical', 'upgrade.py'), 'rb').read()
check('plogical/upgrade.py has no carriage returns', b'\r' in raw, False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
