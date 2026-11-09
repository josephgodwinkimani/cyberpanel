"""Tests that the leftovers of the removed advanced mail filter manager are gone: the upgrade step that rewrote the postfix configuration and
restarted two services whenever the filter's directory existed (the step and its one call are gone and the neighbouring upgrade steps keep
their order), the four request field names the removed page used to send (they no longer bypass the request body filter, every other
exempt field name still does), and one unused script variable. The real filter condition is evaluated for every exempt and non exempt
name, with the old condition rebuilt as a control. Needs node for the script syntax check (skipped when missing).
Run: python3 CPScripts/test_mail_filter_leftovers_removed.py"""
import ast
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


def read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


def fp(src):
    return hashlib.sha256(src.encode()).hexdigest()[:16]


WORD = 'rsp' + 'amd'
STEP = 'Fix' + WORD.upper() + 'Config'
UPG, SEC, JS = read('plogical/upgrade.py'), read('CyberCP/secMiddleware.py'), read('emailPremium/static/emailPremium/emailPremium.js')

# the upgrade step
tree = ast.parse(UPG)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Upgrade')
fn = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
check('the upgrade step is gone and nothing in the file names it or its directory', (STEP in fn, STEP in UPG, '/etc/' + WORD in UPG, 'issues/1176' in UPG), (False, False, False, False))
PIN = {'is_port_open': 'd2b5f40eebe32f11', 'installLSCPD': '1dd0c5a6fe7add23', 'AutoUpgradeAcme': '009e934b95fb606e', 'installCLScripts': '3525bba461d93ea8',
       'runSomeImportantBash': '04a496a51802f367', 'CreateMissingPoolsforFPM': 'b2855675ca50b186', 'enableServices': '19ba03056d1f392c', 'fixPermissions': 'fb0acfc8f7086ace',
       'upgradeVersion': '3d958f5bff5dfd3c', 'mailServerMigrations': 'dfeb90eafc4de30a', 'executioner': '0fc70432c43c36f0', 'stdOut': '31d61008b82e3391'}
check('the neighbouring upgrade methods untouched by any other change are exactly as they were',
      {n: fp(ast.get_source_segment(UPG, fn[n])) if n in fn else None for n in PIN}, PIN)
calls = [ast.get_source_segment(UPG, x) for x in fn['upgrade'].body if isinstance(x, ast.Expr)]
i = calls.index('Upgrade.runSomeImportantBash()')
check('in the upgrade the steps around the removed call keep their order', calls[i - 2:i + 3],
      ['Upgrade.AutoUpgradeAcme()', 'Upgrade.installCLScripts()', 'Upgrade.runSomeImportantBash()', 'Upgrade.CreateMissingPoolsforFPM()', 'Upgrade.installDNS_CyberPanelACMEFile()'])
check('the removed call sat between two steps that are now adjacent', (calls[i + 1], 'Upgrade.' + STEP + '()' in calls), ('Upgrade.CreateMissingPoolsforFPM()', False))

# the request body filter
stree = ast.parse(SEC)
conds = [n.test for n in ast.walk(stree) if isinstance(n, ast.If) and "'MainDashboardCSS'" in (ast.get_source_segment(SEC, n.test) or '')]
check('the field name exemption condition is found once', len(conds), 1)
COND = re.sub(r'\\\s*\n', ' ', ast.get_source_segment(SEC, conds[0])).replace('\n', ' ')
KEEP = ['MainDashboardCSS', 'ownerPassword', 'scriptUrl', 'key', 'cert', 'recordContentAAAA', 'backupDestinations', 'ports', 'imageByPass', 'passwordByPass', 'PasswordByPass',
        'cronCommand', 'emailMessage', 'configData', 'rewriteRules', 'modSecRules', 'recordContentTXT', 'SecAuditLogRelevantStatus', 'fileContent', 'commands', 'gitHost', 'ipv6',
        'contentNow']
GONE = ['CLAMAV_VIRUS', WORD.capitalize() + 'server', 'smtpd_milters', 'non_smtpd_milters']
check('every other exempt field name is still exempt', [k for k in KEEP if not eval(COND, {'key': k})], [])
check('the four removed field names and an ordinary one are no longer exempt', {k: bool(eval(COND, {'key': k})) for k in GONE + ['domainName']}, {k: False for k in GONE + ['domainName']})
OLD = COND.replace("key == 'scriptUrl'", "key == 'scriptUrl' or key == 'CLAMAV_VIRUS' or key == '" + GONE[1] + "' or key == 'smtpd_milters' or key == 'non_smtpd_milters'")
check('control: with the four names put back they would be exempt and the check sees it', (OLD != COND, [bool(eval(OLD, {'key': k})) for k in GONE]), (True, [True, True, True, True]))
check('no page or script sends the removed field names', [r for r in ('emailPremium', 'mailServer', 'baseTemplate') for b, d, fs in os.walk(os.path.join(ROOT, r))
                                                         for f in fs if f.endswith(('.js', '.html')) and any(w in open(os.path.join(b, f), encoding='utf-8', errors='replace').read() for w in GONE[:2])], [])

# the script
tree_js = re.findall(r"app\.controller\('([A-Za-z0-9_]+)'", JS)
check('the script no longer names the removed filter and keeps the spam assassin controller', (WORD in JS.lower(), 'SpamAssassin' in tree_js), (False, True))
node = shutil.which('node')
if node:
    check('emailPremium.js is valid JavaScript', subprocess.run([node, '--check', os.path.join(ROOT, 'emailPremium/static/emailPremium/emailPremium.js')], capture_output=True).returncode, 0)
else:
    print('SKIP  node is not installed: the script syntax check was not run')

for rel in ('plogical/upgrade.py', 'CyberCP/secMiddleware.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
for rel in ('plogical/upgrade.py', 'CyberCP/secMiddleware.py', 'emailPremium/static/emailPremium/emailPremium.js'):
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
