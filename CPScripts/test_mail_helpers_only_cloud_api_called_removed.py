"""Tests that three mail server helpers that only the removed Cloud API called (the server level email checks, the email configuration reset
and the per site mail check) are gone from the two mail modules together with their thread entry point and their command line
branches, while everything else in the two modules is byte for byte what it was (pinned by hash where no other change touches it) and the
real command line entry point of the mail utilities still runs every remaining function (run with recorders, with the old branch put back
as a control). Run: python3 CPScripts/test_mail_helpers_only_cloud_api_called_removed.py"""
import argparse
import ast
import hashlib
import os
import re
import sys
import types

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


TRIO = ['RunServerLevelEmailChecks', 'ResetEmailConfigurations', 'debugEmailForSite']
MGR, UTIL = read('mailServer/mailserverManager.py'), read('plogical/mailUtilities.py')


def methods(src, cls):
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == cls)
    return {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}


mm, mu = methods(MGR, 'MailServerManager'), methods(UTIL, 'MailServerManagerUtils')
check('none of the three helpers is left in the mail server manager', sorted(set(TRIO) & set(mm)), [])
check('none of the three helpers is left in the mail utilities', sorted(set(TRIO) & set(mu)), [])
check('the manager thread entry point that only ran the first helper is gone and the class keeps its constructor', ('run' in mm, '__init__' in mm), (False, True))
MPIN = {'loadEmailHome': 'aafd7877d619a9ec', 'createEmailAccount': '176cfeb39154c068', 'listEmails': '60a87cb1d8d06e02', 'deleteEmailAccount': '8bf11026a0225767',
        'submitEmailDeletion': '674aeef52f35da6c', 'fixMailSSL': '60f940ae1732c3a1', 'emailForwarding': 'df3ec1b81ef585c1', 'fetchCurrentForwardings': '52e7322b1ee28fe0',
        'submitForwardDeletion': 'a3833e0fb7ef2821', 'submitEmailForwardingCreation': '80ab036717c0b8fa', 'fetchEmails': 'd5a3fff5a4a1bcc4',
        'changeEmailAccountPassword': '6afef4d1e3937353', 'submitPasswordChange': 'b5e9ede493b33135', 'dkimManager': '9661f658817443f0', 'fetchDKIMKeys': '299dc714932019fe',
        'generateDKIMKeys': '09bd4cbe0bd7fccd', 'installOpenDKIM': '1dccc4c74f755009', 'installStatusOpenDKIM': '30be164f2a711673', 'checkIfMailServerSSLIssued': 'e110b743027af91a',
        'setup_email_Passwords': '9a499ccbf0a6c429', 'centos_lib_dir_to_ubuntu': 'b714909fe5f9ea59', 'setup_postfix_dovecot_config': '0797147cefaf021a',
        'installOpenDKIMNew': '32e4acab0ae8fa8e', 'configureOpenDKIM': '739e1c0ac0a41676', 'fixCyberPanelPermissions': 'e116d9f6c91dc8f7'}
check('the other mail server manager methods untouched by any other change are exactly as they were',
      {n: fp(ast.get_source_segment(MGR, mm[n])) if n in mm else None for n in MPIN}, MPIN)
UPIN = {'checkIfMailServerSSLIssued': '972d8a1b54271d3f', 'FetchCloudLinuxAlmaVersionVersion': '952ddfe2c28d45a0', 'setup_email_Passwords': 'c47ea74145cf1833',
        'centos_lib_dir_to_ubuntu': '2ec07354ba3d7837', 'setup_postfix_dovecot_config': '681d38145c393f11', 'fixCyberPanelPermissions': '74062e15319cba8a',
        'installOpenDKIMNew': '12a4c2a16c654632', 'SetupDKIMFromResetMail': 'b3cc01e7f80228d8', 'configureOpenDKIM': 'a268ed97901f2084'}
check('the other mail utility methods untouched by any other change are exactly as they were',
      {n: fp(ast.get_source_segment(UTIL, mu[n])) if n in mu else None for n in UPIN}, UPIN)
check('the manager module no longer has a command line entry point and still defines the class',
      ('def main' in MGR, '__main__' in MGR, 'class MailServerManager(' in MGR), (False, False, True))

# the command line entry point of the mail utilities
tree = ast.parse(UTIL)
main_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
MAIN = ast.get_source_segment(UTIL, main_node)
FUNCS = ['createEmailAccount', 'generateKeys', 'configureOpenDKIM', 'configureSpamAssassin', 'saveSpamAssassinConfigs', 'savePolicyServerStatus', 'installSpamAssassin',
         'installMailScanner', 'AfterEffects']


def run_main(code, function):
    calls = []

    class Utils:
        def __getattr__(self, name):
            return lambda *a, **k: calls.append(name)

    class Meta(type):
        def __getattr__(cls, name):
            return lambda *a, **k: calls.append(name)

    class Threaded(metaclass=Meta):
        def __init__(self, request, function_, extra):
            calls.append('thread:' + function_)

        def ResetEmailConfigurations(self):
            calls.append('reset')

    ns = {'argparse': argparse, 'mailUtilities': Utils(), 'MailServerManagerUtils': Threaded}
    exec(code, ns)
    saved = sys.argv
    sys.argv = ['x', function, '--domain', 'd', '--userName', 'u', '--password', 'p', '--tempConfigPath', 't', '--install', 'i']
    try:
        ns['main']()
    finally:
        sys.argv = saved
    return calls


check('every remaining command line function makes exactly its own call', {f: run_main(MAIN, f) for f in FUNCS}, {f: [f] for f in FUNCS})
check('the removed reset function and an unknown function do nothing', (run_main(MAIN, 'ResetEmailConfigurations'), run_main(MAIN, 'somethingElse')), ([], []))
TAIL = "        mailUtilities.AfterEffects(args.domain)"
OLD = MAIN.replace(TAIL, TAIL + "\n    elif args.function == \"ResetEmailConfigurations\":\n        background = MailServerManagerUtils(None, 'ResetEmailConfigurations', {})\n        background.ResetEmailConfigurations()")
check('control: with the old branch put back the reset function would run and the check sees it', (OLD != MAIN, run_main(OLD, 'ResetEmailConfigurations')), (True, ['thread:ResetEmailConfigurations', 'reset']))

# nobody else calls them
callers = []
SKIP = ('.git', 'node_modules', 'static', 'public', 'locale')
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(('.py', '.js', '.html', '.sh')) and not f.startswith('test_') and '.bak' not in f:
            text = open(os.path.join(base, f), encoding='utf-8', errors='replace').read()
            for name in TRIO:
                if re.search(r'\b' + name + r'\b', text):
                    callers.append((os.path.relpath(os.path.join(base, f), ROOT), name))
check('nothing in the tree names the three helpers', callers, [])

for rel in ('mailServer/mailserverManager.py', 'plogical/mailUtilities.py'):
    try:
        ast.parse(open(os.path.join(ROOT, rel), 'rb').read(), feature_version=(3, 9))
        parsed = True
    except SyntaxError:
        parsed = False
    check('%s parses with the Python 3.9 grammar' % rel, parsed, True)
    check('%s has no carriage returns' % rel, b'\r' in open(os.path.join(ROOT, rel), 'rb').read(), False)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
