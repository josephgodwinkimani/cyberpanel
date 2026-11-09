"""Tests that the Basic Settings readers of the PHP settings code keep the sign of memory_limit and max_execution_time and max_input_time. The readers
split the line into words with a pattern that dropped the minus sign, so an active memory_limit = -1 was shown as 1 and saving the form wrote
memory_limit = 1 (one byte) and stopped every site on that PHP version. The pattern now allows a leading + or -, and the two time limits are matched as
exact directives like memory_limit. The files are only read; the pattern is taken from the source and run on its own.
Run: python3 CPScripts/test_php_signed_limits.py"""
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
matches = mod.matches_directive

FILES = ('managePHP/phpManager.py', 'managePHP/views.py')
SRC = {rel: open(os.path.join(ROOT, rel), encoding='utf-8').read() for rel in FILES}
OLD_PATTERN = r'[A-Za-z0-9_]+'
NEW_PATTERN = r'[+-]?[A-Za-z0-9_]+'

# the readers: three limits in each of the two files
for rel, src in SRC.items():
    sites = re.findall(r'(\w+) = re\.findall\(r"([^"]+)", items\)\[1\]', src)
    limits = {name: pat for name, pat in sites if name in ('memory_limit', 'max_execution_time', 'max_input_time')}
    check('%s: the three limits are read with the signed pattern' % rel, limits, {'memory_limit': NEW_PATTERN, 'max_execution_time': NEW_PATTERN, 'max_input_time': NEW_PATTERN})
    check('%s: the size settings keep the old pattern (no sign is valid there)' % rel,
          {name: pat for name, pat in sites if name in ('upload_max_filesize', 'post_max_size')}, {'upload_max_filesize': OLD_PATTERN, 'post_max_size': OLD_PATTERN})
    check('%s: the two time limits are matched as exact directives' % rel, (src.count('matches_directive(items, "max_execution_time")'), src.count('matches_directive(items, "max_input_time")')), (1, 1))


def read(pattern, line):
    return re.findall(pattern, line)[1]


CASES = [('memory_limit = -1', '-1'), ('memory_limit = 128M', '128M'), ('max_input_time = -1', '-1'), ('max_execution_time = 0', '0'), ('max_execution_time = +120', '+120'),
         ('max_input_time = "-1"', '-1'), ("max_input_time = '-1'", '-1'), ('memory_limit = 12000M', '12000M'), ('max_execution_time = 30 ; seconds', '30')]
check('signed and unsigned values are read as written', [read(NEW_PATTERN, line) for line, _ in CASES], [want for _, want in CASES])
check('control: the old pattern turns -1 into 1', (read(OLD_PATTERN, 'memory_limit = -1'), read(OLD_PATTERN, 'max_input_time = -1')), ('1', '1'))
check('values without a sign read the same with both patterns', [read(OLD_PATTERN, l) == read(NEW_PATTERN, l) for l, w in CASES if not w.startswith(('-', '+'))], [True] * 4)

fixture = ['; max_execution_time = 999', 'max_execution_time = 30', '; max_input_time = 999', 'max_input_time = -1', 'max_memory_limit = 2G', 'memory_limit = -1']
check('comments and other directives are not read as the limits', ([l for l in fixture if matches(l, 'max_execution_time')], [l for l in fixture if matches(l, 'max_input_time')],
      [l for l in fixture if matches(l, 'memory_limit')]), (['max_execution_time = 30'], ['max_input_time = -1'], ['memory_limit = -1']))
check('the files have no carriage returns', [b'\r' in open(os.path.join(ROOT, rel), 'rb').read() for rel in FILES], [False, False])

print('----')
print('%d of %d checks passed' % (ok, total))
sys.exit(0 if ok == total else 1)
