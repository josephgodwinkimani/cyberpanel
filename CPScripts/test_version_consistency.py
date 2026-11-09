"""Tests that every place that holds the panel version agrees with version.txt.
version.txt on main names the release branch the upgrade downloads (for example {"version":"3.0","build":0} is branch v3.0.0).
Six python files carry their own VERSION and BUILD constants: the upgrade script, the installer, the base template views, the
login views, the admin password script and the server status views (which print the version shown on the dashboard). A file
that is missed keeps showing the old number after an upgrade. plogical/backupUtilities.py also has the constants but tests
for the literal value 2.3 when it creates and restores database backups, so it must keep 2.3 for as long as those tests exist.
Any other file that assigns VERSION or BUILD at the start of a line must be added to the list in this test on purpose.
Run: python3 CPScripts/test_version_consistency.py"""
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CARRIERS = ['baseTemplate/views.py', 'install/install.py', 'loginSystem/views.py', 'plogical/adminPass.py', 'plogical/upgrade.py', 'serverStatus/views.py']
BACKUP = 'plogical/backupUtilities.py'
BACKUP_GATE = "VERSION == '2.3'"
SKIP_DIRS = {'.git', 'static', 'node_modules', 'lib', 'bin', 'public', '__pycache__'}
LINE = re.compile(r"^(VERSION|BUILD) = ('[0-9.]+'|[0-9]+)[ \t]*$", re.M)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def constants(root, rel):
    """Return {'VERSION': text, 'BUILD': text} for the first assignment of each constant at the start of a line."""
    found = {}
    text = open(os.path.join(root, rel), encoding='utf-8', newline='').read()
    for m in LINE.finditer(text):
        found.setdefault(m.group(1), m.group(2).strip("'"))
    return found, text


def problems(root):
    """List every disagreement under root (empty list when all is consistent)."""
    out = []
    meta = json.load(open(os.path.join(root, 'version.txt'), encoding='utf-8'))
    version, build = str(meta['version']), str(meta['build'])
    for rel in CARRIERS:
        found, text = constants(root, rel)
        if found.get('VERSION') != version or found.get('BUILD') != build:
            out.append('%s has VERSION %s and BUILD %s, version.txt has %s and %s' % (rel, found.get('VERSION'), found.get('BUILD'), version, build))
        if '\r' in text:
            out.append('%s has carriage returns' % rel)
    found, text = constants(root, BACKUP)
    if BACKUP_GATE in text:
        if found.get('VERSION') != '2.3' or found.get('BUILD') != '9':
            out.append('%s must stay 2.3 and 9 while it tests for 2.3, it has %s and %s' % (BACKUP, found.get('VERSION'), found.get('BUILD')))
    elif found.get('VERSION') != version or found.get('BUILD') != build:
        out.append('%s has VERSION %s and BUILD %s, version.txt has %s and %s' % (BACKUP, found.get('VERSION'), found.get('BUILD'), version, build))
    known = set(CARRIERS) | {BACKUP}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith('.py'):
                continue  # only python files matter, and a stray device-like name (a file called nul on Windows) must not stop the test
            rel = os.path.relpath(os.path.join(folder, name), root).replace(os.sep, '/')
            if rel in known or rel.startswith('CPScripts/test_'):
                continue
            if LINE.search(open(os.path.join(folder, name), encoding='utf-8', errors='replace', newline='').read()):
                out.append('%s assigns VERSION or BUILD and is not on the list of this test' % rel)
    return out


def copy_tree(dest):
    """A small copy of the files this test looks at, so controls can break it without touching the repository."""
    for rel in ['version.txt'] + CARRIERS + [BACKUP]:
        os.makedirs(os.path.dirname(os.path.join(dest, rel)) or dest, exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, rel), os.path.join(dest, rel))


def mutated(edit):
    tmp = tempfile.mkdtemp()
    try:
        copy_tree(tmp)
        normalise(tmp)
        edit(tmp)
        return problems(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def set_constant(tmp, rel, name, value):
    """Write the first VERSION or BUILD assignment of a file in the temporary copy, whatever it holds now."""
    path = os.path.join(tmp, rel)
    text = open(path, encoding='utf-8', newline='').read()
    new = ("'%s'" % value) if name == 'VERSION' else str(value)
    text, count = re.subn(r"^%s = ('[0-9.]+'|[0-9]+)[ \t]*$" % name, '%s = %s' % (name, new), text, count=1, flags=re.M)
    assert count == 1, (rel, name)
    open(path, 'w', encoding='utf-8', newline='').write(text)


meta = json.load(open(os.path.join(ROOT, 'version.txt'), encoding='utf-8'))
V, B = str(meta['version']), str(meta['build'])
backup_text = open(os.path.join(ROOT, BACKUP), encoding='utf-8').read()


def normalise(tmp):
    """Make the temporary copy consistent first, so a control never depends on the state of the real repository."""
    for rel in CARRIERS:
        set_constant(tmp, rel, 'VERSION', V)
        set_constant(tmp, rel, 'BUILD', B)
    if BACKUP_GATE not in backup_text:
        set_constant(tmp, BACKUP, 'VERSION', V)
        set_constant(tmp, BACKUP, 'BUILD', B)
check('version.txt holds a version and a build', (sorted(meta), bool(re.fullmatch(r'[0-9]+\.[0-9]+', str(meta['version']))), bool(re.fullmatch(r'[0-9]+', str(meta['build'])))), (['build', 'version'], True, True))
check('the branch the upgrade would use is vX.Y.Z', 'v%s.%s' % (meta['version'], meta['build']), 'v%s.%s' % (meta['version'], meta['build']))
check('the repository is consistent: every file agrees with version.txt', problems(ROOT), [])

# controls: each kind of mistake must be caught
check('control: the server status views left on another version are caught', mutated(lambda tmp: set_constant(tmp, 'serverStatus/views.py', 'VERSION', '0.1')), ['serverStatus/views.py has VERSION 0.1 and BUILD %s, version.txt has %s and %s' % (B, V, B)])
check('control: a wrong build in the upgrade script is caught', len(mutated(lambda tmp: set_constant(tmp, 'plogical/upgrade.py', 'BUILD', 99))), 1)
check('control: a changed version.txt is caught in all six files', len(mutated(lambda tmp: open(os.path.join(tmp, 'version.txt'), 'w', newline='').write('{"version":"9.9","build":1}'))), 6 + (0 if BACKUP_GATE in open(os.path.join(ROOT, BACKUP), encoding='utf-8').read() else 1))


def add_stray(tmp):
    os.makedirs(os.path.join(tmp, 'otherApp'), exist_ok=True)
    open(os.path.join(tmp, 'otherApp', 'views.py'), 'w', newline='').write("VERSION = '1.0'\n")


check('control: a new file that assigns VERSION is caught', len(mutated(add_stray)), 1)
if BACKUP_GATE in backup_text:
    check('control: bumping plogical/backupUtilities.py while it tests for 2.3 is caught', len(mutated(lambda tmp: set_constant(tmp, BACKUP, 'VERSION', '0.1'))), 1)
check('control: an untouched copy is clean', mutated(lambda tmp: None), [])

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
