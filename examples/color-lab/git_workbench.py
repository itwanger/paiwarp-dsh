#!/usr/bin/env python3
"""A real local git diff and red-to-green unit test, with an intentional bug."""
import json
import shutil
import subprocess
import sys
from terminal_style import page, paint, row, checkpoint, fresh_workspace

BUGGY = 'def total(price, count):\n    return price + count\n'
FIXED = 'def total(price, count):\n    return price * count\n'
TEST = '''import unittest
from invoice import total
class InvoiceTest(unittest.TestCase):
    def test_three_items(self): self.assertEqual(total(12, 3), 36)
    def test_zero_items(self): self.assertEqual(total(12, 0), 0)
    def test_one_item(self): self.assertEqual(total(12, 1), 12)
'''


def main():
    if not shutil.which('git'):
        raise SystemExit('需要本机 Git；不会连接远程仓库。')
    root = fresh_workspace('git-workbench')
    (root / 'invoice.py').write_text(BUGGY)
    (root / 'test_invoice.py').write_text(TEST)
    (root / '.gitignore').write_text('__pycache__/\n*.log\nresult.json\n')
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    before = subprocess.run([sys.executable, '-B', '-X', f'pycache_prefix={root / ".pycache"}', '-m', 'unittest', '-v'], cwd=root, capture_output=True, text=True)
    (root / 'before.log').write_text(before.stderr)
    page('02', 'RED / REPAIR / GREEN', '故意设置的示例缺陷 · 真实测试必须先失败')
    row('Invoice total', 'FAIL' if before.returncode else 'UNEXPECTED', f'test process exit = {before.returncode}', 'red')
    row('Three items', 'MISMATCH', '12 × 3 expected 36; buggy function returns 15', 'red')
    print('\n  ' + paint('Actual unittest output', 'purple', True))
    for line in before.stderr.splitlines()[-8:]:
        print('  ' + paint(line.replace(str(root) + '/', ''), 'red' if 'FAILED' in line or '!=' in line else 'muted'))
    checkpoint('git-01-failing')
    if before.returncode == 0:
        raise SystemExit('负例意外通过，停止演示。')
    (root / 'invoice.py').write_text(FIXED)
    # Same-size, same-second edit: remove stale bytecode before the next real test.
    shutil.rmtree(root / '__pycache__', ignore_errors=True)
    diff = subprocess.run(['git', '-c', 'color.ui=always', 'diff', '--', 'invoice.py'], cwd=root, capture_output=True, text=True, check=True)
    (root / 'change.diff').write_text(subprocess.check_output(['git', 'diff', '--', 'invoice.py'], cwd=root, text=True))
    page('02', 'REVIEW THE PATCH', '红色删除 · 绿色新增 · git diff 的真实输出')
    print(diff.stdout)
    row('Change', 'LOCAL', 'Only invoice.py changed; no commit or push', 'amber')
    checkpoint('git-02-diff')
    after = subprocess.run([sys.executable, '-B', '-X', f'pycache_prefix={root / ".pycache"}', '-m', 'unittest', '-v'], cwd=root, capture_output=True, text=True)
    (root / 'after.log').write_text(after.stderr)
    (root / 'result.json').write_text(json.dumps({'beforeExit': before.returncode, 'afterExit': after.returncode,
                                                'diffHasMultiplication': '+    return price * count' in (root / 'change.diff').read_text()}, indent=2) + '\n')
    page('02', 'REGRESSION CHECK', '同一份测试重新执行，不修改断言去迎合结果')
    row('Before repair', 'FAIL', '3 tests rejected the original function', 'red')
    row('After repair', 'PASS' if after.returncode == 0 else 'FAIL', f'test process exit = {after.returncode}', 'mint' if after.returncode == 0 else 'red')
    print()
    for line in after.stderr.splitlines():
        print('  ' + paint(line, 'mint' if line.endswith('ok') or line == 'OK' else 'muted'))
    checkpoint('git-03-passing')
    raise SystemExit(after.returncode)


if __name__ == '__main__':
    main()
