"""Tests that the PHP settings code of the panel recognises the memory_limit line of a php.ini exactly. PHP 8.5 added the directive max_memory_limit
next to memory_limit and the old test (the text memory_limit and an equals sign anywhere in the line) matched both: the settings page showed the wrong value
and saving the settings replaced both lines with memory_limit, so the php.ini of PHP 8.5 lost its max_memory_limit and gained a second memory_limit.
managePHP/phpConfig.matches_directive matches only a line that starts with the directive. The files are only read, nothing is written.
Run: python3 CPScripts/test_php_memory_limit_directive.py"""
import importlib.util
import os
import re
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


spec = importlib.util.spec_from_file_location('phpConfig', os.path.join(ROOT, 'managePHP', 'phpConfig.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
m = mod.matches_directive


def old_rule(line):
    return line.find('memory_limit') > -1 and line.find('=') > -1


# lines as found in the php.ini of the lsphp packages (8.3 to 8.5) and in comments
PHP85 = ['; Maximum amount of memory a script may consume', '; https://php.net/memory-limit', 'memory_limit = 128M', 'max_memory_limit = -1']
PHP83 = ['; https://php.net/memory-limit', 'memory_limit = 128M']
check('memory_limit is recognised in the lines of PHP 8.3', [m(l, 'memory_limit') for l in PHP83], [False, True])
check('only memory_limit is recognised in PHP 8.5 (not max_memory_limit)', [m(l, 'memory_limit') for l in PHP85], [False, False, True, False])
check('control: the old rule matches max_memory_limit in PHP 8.5 too (the defect)', [old_rule(l) for l in PHP85], [False, False, True, True])
check('white space and capitals are accepted', (m('  MEMORY_LIMIT=256M', 'memory_limit'), m('\tmemory_limit  =  1G', 'memory_limit')), (True, True))
check('a commented line is not an assignment', (m('; memory_limit = 128M', 'memory_limit'), m('# memory_limit = 1', 'memory_limit')), (False, False))
check('a line without an equals sign is not an assignment', m('memory_limit 128M', 'memory_limit'), False)
check('a longer name starting the same is not matched', m('memory_limit_extra = 1', 'memory_limit'), False)

# the four places in the code use it and none uses the old test any more
SOURCES = {rel: open(os.path.join(ROOT, rel), encoding='utf-8').read() for rel in ('managePHP/phpManager.py', 'managePHP/views.py', 'plogical/phpUtilities.py')}
check('the old substring test for memory_limit is gone from the three files', {rel: len(re.findall(r'find\("memory_limit"\)', s)) for rel, s in SOURCES.items()},
      {'managePHP/phpManager.py': 0, 'managePHP/views.py': 0, 'plogical/phpUtilities.py': 0})
check('the four places call matches_directive', {rel: s.count('matches_directive(items, "memory_limit")') for rel, s in SOURCES.items()},
      {'managePHP/phpManager.py': 2, 'managePHP/views.py': 1, 'plogical/phpUtilities.py': 1})
check('each of the three files imports it', {rel: bool(re.search(r'^from (\.|managePHP\.)phpConfig import matches_directive$', s, re.M)) for rel, s in SOURCES.items()},
      {'managePHP/phpManager.py': True, 'managePHP/views.py': True, 'plogical/phpUtilities.py': True})
check('the files have no carriage returns', [b'\r' in open(os.path.join(ROOT, rel), 'rb').read() for rel in list(SOURCES) + ['managePHP/phpConfig.py']], [False] * 4)

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
