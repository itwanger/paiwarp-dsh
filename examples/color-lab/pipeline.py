#!/usr/bin/env python3
"""Compile, test and zip a real tiny Python project, pausing for captures."""
import hashlib
import json
import subprocess
import sys
import zipfile
from terminal_style import page, paint, row, checkpoint, fresh_workspace

SOURCE = '''def subtotal(price, count):
    if price < 0 or count < 0:
        raise ValueError("negative value")
    return price * count
'''
TESTS = '''import unittest
from pricing import subtotal
class PricingTest(unittest.TestCase):
    def test_total(self): self.assertEqual(subtotal(12, 3), 36)
    def test_zero(self): self.assertEqual(subtotal(12, 0), 0)
    def test_decimal(self): self.assertEqual(subtotal(2.5, 4), 10)
    def test_negative_price(self):
        with self.assertRaises(ValueError): subtotal(-1, 2)
    def test_negative_count(self):
        with self.assertRaises(ValueError): subtotal(1, -2)
'''


def main():
    root = fresh_workspace('pipeline')
    (root / 'pricing.py').write_text(SOURCE)
    (root / 'test_pricing.py').write_text(TESTS)
    page('01', 'BUILD / VERIFY / PACKAGE', '真实 Python 编译与单元测试 · 全部在本地执行')
    row('Workspace', 'READY', '.color-lab/pipeline  ·  2 source files', 'cyan')
    row('Compile', 'PENDING', 'compileall validates Python syntax', 'amber')
    row('Unit tests', 'PENDING', '5 checks: totals, zero, decimals, invalid input', 'amber')
    row('Artifact', 'PENDING', 'zip archive + SHA-256', 'muted')
    checkpoint('pipeline-01-ready')
    compiled = subprocess.run([sys.executable, '-m', 'compileall', '-q', '.'], cwd=root, capture_output=True, text=True)
    tests = subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=root, capture_output=True, text=True)
    (root / 'tests.log').write_text(tests.stdout + tests.stderr)
    page('01', 'TEST RESULTS', '退出状态来自真实子进程，不根据成功关键词猜测')
    row('Compile', 'PASS' if compiled.returncode == 0 else 'FAIL', 'exit code = ' + str(compiled.returncode), 'mint' if compiled.returncode == 0 else 'red')
    print()
    for line in tests.stderr.splitlines():
        print('  ' + paint(line, 'mint' if line.endswith('ok') or line == 'OK' else 'muted'))
    checkpoint('pipeline-02-tests')
    if compiled.returncode or tests.returncode:
        raise SystemExit('真实检查失败，保留 tests.log，不生成成功产物。')
    archive = root / 'pricing-demo.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ['pricing.py', 'test_pricing.py']:
            z.write(root / name, name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    report = {'compileExit': compiled.returncode, 'testExit': tests.returncode,
              'archiveBytes': archive.stat().st_size, 'sha256': digest}
    (root / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    page('01', 'ARTIFACT READY', '构建结果已经写入磁盘，可以独立检查')
    row('Compile', 'PASS', 'Python bytecode created')
    row('Unit tests', 'PASS', '5 tests · exit code 0')
    row('Archive', 'SAVED', f'pricing-demo.zip · {archive.stat().st_size} bytes', 'cyan')
    print('\n  ' + paint('SHA-256', 'purple', True))
    print('  ' + paint(digest, 'muted'))
    print('\n  ' + paint('████████████████████████████████████████████  100%', 'mint'))
    checkpoint('pipeline-03-artifact')
    print('Saved: .color-lab/pipeline/result.json')


if __name__ == '__main__':
    main()
