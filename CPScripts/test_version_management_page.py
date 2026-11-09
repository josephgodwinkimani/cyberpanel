"""Tests the script of baseTemplate/templates/baseTemplate/versionManagment.html: choosing a branch in the dropdown shows that
branch's version and newest commit, and shows the upgrade note only when that commit is not the installed one. The few Django
constructs of the template are rendered here and the real script is run by Node against a fake page and fake GitHub answers.
Needs node (the check is reported as skipped when it is missing).
Run: python3 CPScripts/test_version_management_page.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), 'baseTemplate', 'templates', 'baseTemplate', 'versionManagment.html')

total = ok = 0


def check(name, got, want):
    global total, ok
    total += 1
    if got == want:
        ok += 1
        print('ok    ' + name)
    else:
        print('NOT OK ' + name + '\n        wanted: %r\n        got:    %r' % (want, got))


raw = open(TEMPLATE, 'rb').read()
text = raw.decode('utf-8')


def render(source, context):
    """Renders only what this template uses: trans (plain and as), if/endif, variables with escapejs, load and static."""
    assigned = {}

    def assign(m):
        assigned[m.group(2)] = m.group(1)
        return ''

    source = re.sub(r'\{%\s*trans\s+"([^"]*)"\s+as\s+(\w+)\s*%\}', assign, source)
    source = re.sub(r'\{%\s*trans\s+"([^"]*)"\s*%\}', lambda m: m.group(1), source)
    source = re.sub(r'\{%\s*if\s+not\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}', lambda m: '' if context[m.group(1)] else m.group(2), source, flags=re.S)
    source = re.sub(r'\{%\s*load\s+[^%]*%\}', '', source)
    source = re.sub(r"\{%\s*static\s+[^%]*%\}", '/static/x', source)
    source = re.sub(r'\{%\s*(extends|block|endblock)[^%]*%\}', '', source)

    def variable(m):
        name, flt = m.group(1), m.group(2)
        value = assigned[name] if name in assigned else str(context[name])
        return value.replace('\\', '\\u005C').replace('"', '\\u0022').replace("'", '\\u0027').replace('<', '\\u003C').replace('>', '\\u003E') if flt else value

    source = re.sub(r'\{\{\s*(\w+)(?:\|(escapejs))?\s*\}\}', variable, source)
    leftover = re.findall(r'\{%.*?%\}|\{\{.*?\}\}', source)
    return source, leftover


CONTEXT = {'Notecheck': True, 'Currentcomt': 'f7fb2c4', 'latestVersion': '2.3', 'latestBuild': 9, 'latestcomit': 'old', 'currentVersion': '2.3', 'build': '9', 'logs': ''}
html, leftover = render(text, CONTEXT)
check('every Django construct of the template is rendered by this test (none left over)', leftover, [])
script = re.findall(r'<script>(.*?)</script>', html, flags=re.S)[-1]

# the page
check('the note is always in the page and starts visible when the server found a mismatch', 'id="commitNote" class="alert alert-info">' in html, True)
hidden_html, _ = render(text, dict(CONTEXT, Notecheck=False))
check('the note starts hidden when the server found no mismatch', 'id="commitNote" class="alert alert-info" style="display: none;">' in hidden_html, True)
check('the three latest rows can be found by id', all(('id="%s"' % i) in html for i in ('latestVersion', 'latestBuild', 'latestCommit')), True)
check('the rendered values reach the script', ('var installedCommit = "f7fb2c4";' in script, 'var renderedBranch = "v2.3.9";' in script), (True, True))
check('the existing branch listing and upgrade code is still there', ("getBranches('https://api.github.com/repos/josephgodwinkimani/cyberpanel/branches', [], 1);" in script, "fetch('/base/upgrade'" in script, 'function refreshPage()' in script), (True, True, True))
check('the template has no carriage returns', b'\r' in raw, False)
check('if and endif tags are balanced', (len(re.findall(r'\{%\s*if\b', text)), len(re.findall(r'\{%\s*endif\b', text))), (1, 1))

HARNESS = r"""
const fs = require('fs'); const vm = require('vm');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const BRANCHES = ['main', 'v2.3.8', 'v2.3.9', 'v2.3.9-dev', 'v2.4.0', 'version-counter', 'v-x'];
const ERROR_TEXT = 'Could not load the latest commit of this branch.';

async function load(script, heads, installed, rendered, delays) {
  const els = {};
  const el = (id, props) => (els[id] = Object.assign({ textContent: '', style: { display: '' }, listeners: {} }, props || {}));
  const select = el('branchSelect', {
    value: '', options: [],
    appendChild(o) { this.options.push(o); if (this.value === '') this.value = o.value; },
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
  });
  el('latestVersion', { textContent: '2.3' }); el('latestBuild', { textContent: '9' });
  el('latestCommit', { textContent: 'old' }); el('commitNote', { style: { display: '' } });
  const calls = [];
  const fetchFake = async (url) => {
    calls.push(url);
    if (url.indexOf('/branches?page=') > -1) {
      const page = parseInt(url.split('page=')[1], 10);
      return { json: async () => (page === 1 ? BRANCHES.map((name) => ({ name })) : []) };
    }
    const sha = decodeURIComponent(url.split('sha=')[1]);
    await sleep((delays && delays[sha]) || 0);
    const head = heads[sha];
    if (head === 'FAIL') throw new Error('network');
    if (head === 'LIMIT') return { json: async () => ({ message: 'API rate limit exceeded' }) };
    return { json: async () => [{ sha: head }] };
  };
  const ctx = vm.createContext({ document: { getElementById: (id) => els[id], createElement: () => ({ value: '', text: '' }) }, fetch: fetchFake, console, setTimeout });
  vm.runInContext(script, ctx);
  ctx.installedCommit = installed; ctx.renderedBranch = rendered;
  await sleep(40);
  const choose = (branch) => { select.value = branch; (select.listeners.change || []).forEach((fn) => fn()); };
  const state = () => ({ value: select.value, options: select.options.map((o) => o.value), version: els.latestVersion.textContent, build: els.latestBuild.textContent, commit: els.latestCommit.textContent, note: els.commitNote.style.display, commitCalls: calls.filter((u) => u.indexOf('/commits?') > -1).length });
  return { choose, state };
}

(async () => {
  const out = {};
  const heads = { 'v2.3.9': 'aaaa', 'v2.3.8': 'f7fb2c4', 'v2.4.0': 'bbbb', 'v-x': 'cccc' };

  let p = await load(input.script, { 'v2.3.9': 'f7fb2c4' }, 'f7fb2c4', 'v2.3.9');
  out.match_at_load = p.state();

  p = await load(input.script, heads, 'f7fb2c4', 'v2.3.9');
  out.mismatch_at_load = p.state();
  p.choose('v2.4.0'); await sleep(40); out.chose_newer = p.state();
  p.choose('v2.3.8'); await sleep(40); out.chose_installed = p.state();
  p.choose('v-x'); await sleep(40); out.chose_odd_name = p.state();

  p = await load(input.script, Object.assign({}, heads, { 'v2.4.0': 'FAIL' }), 'f7fb2c4', 'v2.3.9');
  p.choose('v2.4.0'); await sleep(40); out.failed_request = p.state();
  p = await load(input.script, Object.assign({}, heads, { 'v2.4.0': 'LIMIT' }), 'f7fb2c4', 'v2.3.9');
  p.choose('v2.4.0'); await sleep(40); out.rate_limited = p.state();

  p = await load(input.script, Object.assign({}, heads, { 'v2.4.0': 'slow' }), 'f7fb2c4', 'v2.3.9', { 'v2.4.0': 80 });
  p.choose('v2.4.0'); p.choose('v2.3.8'); await sleep(200); out.race = p.state();

  p = await load(input.script, heads, 'f7fb2c4', 'v9.9.9');
  out.rendered_branch_not_listed = p.state();
  out.error_text = ERROR_TEXT;
  console.log(JSON.stringify(out));
})().catch((e) => { console.log('HARNESS ERROR ' + e.stack); process.exit(1); });
"""


def run_node(script_text, workdir):
    inp = os.path.join(workdir, 'in.json')
    har = os.path.join(workdir, 'harness.js')
    open(inp, 'w', encoding='utf-8').write(json.dumps({'script': script_text}))
    open(har, 'w', encoding='utf-8').write(HARNESS)
    r = subprocess.run(['node', har, inp], capture_output=True, text=True, timeout=120)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''
    if r.returncode != 0 or not last.startswith('{'):
        print(r.stdout, r.stderr)
        return None
    return json.loads(last)


node = shutil.which('node')
if not node:
    print('SKIP  node is not installed: the script checks were not run')
else:
    work = tempfile.mkdtemp()
    syntax = os.path.join(work, 'page.js')
    open(syntax, 'w', encoding='utf-8').write(script)
    check('the page script is valid JavaScript', subprocess.run([node, '--check', syntax], capture_output=True).returncode, 0)
    res = run_node(script, work)
    check('the script runs against the fake page', res is not None, True)
    if res:
        ERR = res['error_text']
        s = res['match_at_load']
        check('at load: the dropdown starts on the branch the page was rendered for', (s['value'], s['options']), ('v2.3.9', ['v-x', 'v2.4.0', 'v2.3.9', 'v2.3.8']))
        check('at load: branches such as main, dev and version-counter are still left out', any(o in s['options'] for o in ('main', 'v2.3.9-dev', 'version-counter')), False)
        check('at load: a branch whose newest commit is the installed one hides the note even if the server showed it', (s['commit'], s['note']), ('f7fb2c4', 'none'))
        check('at load: the version rows show the selected branch', (s['version'], s['build']), ('2.3', '9'))

        s = res['mismatch_at_load']
        check('at load: a newer commit on the branch shows the note and the commit', (s['commit'], s['note']), ('aaaa', ''))

        s = res['chose_newer']
        check('choosing another branch shows its version build and newest commit', (s['version'], s['build'], s['commit']), ('2.4', '0', 'bbbb'))
        check('choosing a branch that differs from the installed commit shows the note', s['note'], '')
        s = res['chose_installed']
        check('choosing the branch at the installed commit hides the note', (s['version'], s['build'], s['commit'], s['note']), ('2.3', '8', 'f7fb2c4', 'none'))
        s = res['chose_odd_name']
        check('a branch name that is not vX.Y.Z keeps the version rows and still shows its commit', (s['version'], s['build'], s['commit'], s['note']), ('2.3', '8', 'cccc', ''))
        check('each selection makes exactly one commit request', s['commitCalls'], 4)

        for key, label in (('failed_request', 'a failed request'), ('rate_limited', 'a rate limited answer')):
            s = res[key]
            check('%s shows a message in the commit row and no note' % label, (s['commit'], s['note']), (ERR, 'none'))
        s = res['race']
        check('a slow answer for an earlier selection never replaces the newest selection', (s['value'], s['commit'], s['note']), ('v2.3.8', 'f7fb2c4', 'none'))
        s = res['rendered_branch_not_listed']
        check('when the rendered branch is not in the list the first option stays selected and nothing breaks', (s['value'], s['commit']), ('v-x', 'cccc'))

        # controls: the same checks must fail when the behaviour is removed
        listener = 'document.getElementById("branchSelect").addEventListener("change", showSelectedBranch);'
        assert script.count(listener) == 1
        c = run_node(script.replace(listener, ''), work)
        check('control: without the change listener choosing a branch changes nothing', (c['chose_newer']['commit'], c['chose_newer']['version']), ('aaaa', '2.3'))
        compare = "note.style.display = data[0].sha === installedCommit ? 'none' : '';"
        assert script.count(compare) == 1
        c = run_node(script.replace(compare, "note.style.display = '';"), work)
        check('control: without the comparison the note stays visible for the installed commit', c['chose_installed']['note'], '')
        guard = 'if (document.getElementById("branchSelect").value !== branch) return;'
        assert script.count(guard) == 2
        c = run_node(script.replace(guard, ''), work)
        check('control: without the stale answer guard the slow answer wins', c['race']['commit'], 'slow')
    shutil.rmtree(work, ignore_errors=True)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
