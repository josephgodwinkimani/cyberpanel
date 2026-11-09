"""Tests that PHP 8.4 and 8.5 are installed by a new installation on the Red Hat family (the cent8 branch of install/installCyberPanel.py, which also serves
AlmaLinux 9) and nowhere else: not on the other distributions in that method, and not by the upgrade (plogical/upgrade.py), so an existing server never gets
new PHP packages from a panel upgrade. The files are only read. Run: python3 CPScripts/test_fresh_install_php84_85.py"""
import ast
import os
import re
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INST = open(os.path.join(ROOT, 'install', 'installCyberPanel.py'), encoding='utf-8').read()
UPG = open(os.path.join(ROOT, 'plogical', 'upgrade.py'), encoding='utf-8').read()

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def method_blocks(src):
    """The source of installAllPHPVersions split by the distribution branches: {'ubuntu': ..., 'centos': ..., 'cent8': ..., 'openeuler': ...}."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'installAllPHPVersions')
    text = ast.get_source_segment(src, func)
    out = {}
    names = {'ubuntu': r'if self\.distro == ubuntu:', 'centos': r'if self\.distro == centos:', 'cent8': r'if self\.distro == cent8:', 'openeuler': r'if self\.distro == openeuler:'}
    spots = sorted((m.start(), k) for k, p in names.items() for m in re.finditer(p, text))
    for i, (pos, key) in enumerate(spots):
        end = spots[i + 1][0] if i + 1 < len(spots) else len(text)
        out[key] = out.get(key, '') + text[pos:end]
    return out


def problems(src):
    blocks = method_blocks(src)
    out = []
    mentions = {k: bool(re.search(r'lsphp8[45]', v)) for k, v in blocks.items()}
    if not mentions.get('cent8'):
        out.append('cent8 does not install PHP 8.4 and 8.5')
    for k in ('ubuntu', 'centos', 'openeuler'):
        if mentions.get(k):
            out.append(k + ' mentions PHP 8.4 or 8.5')
    return out


check('a new installation on the Red Hat family installs 8.4 and 8.5 and no other branch does', problems(INST), [])
check('the command skips broken packages and the imagick packages like the one for 8.1 to 8.3', "dnf install lsphp84* lsphp85* --exclude *imagick* -y --skip-broken" in INST, True)
check('the existing installs of 7.1 to 8.3 are unchanged', all(c in INST for c in ("dnf install lsphp71* lsphp72* lsphp73* lsphp74* lsphp80* --exclude lsphp73-pecl-zip --exclude *imagick* -y --skip-broken",
                                                                          "dnf install lsphp81* lsphp82* lsphp83* --exclude *imagick* -y --skip-broken")), True)
check('the upgrade does not install PHP 8.4 or 8.5', re.findall(r"(?:install|find)[^\n]*lsphp8[45]", UPG), [])
check('the upgrade does not call the new installation method', 'installAllPHPVersions' in UPG, False)
check('control: putting 8.4 into the Ubuntu branch is reported', len(problems(INST.replace("apt-get -y install lsphp83*'", "apt-get -y install lsphp83* lsphp84*'", 1))) > 0, True)
check('control: removing the line is reported', len(problems(INST.replace("lsphp84* lsphp85*", "lsphp83*", 1))) > 0, True)
check('install/installCyberPanel.py has no carriage returns', b'\r' in open(os.path.join(ROOT, 'install', 'installCyberPanel.py'), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
