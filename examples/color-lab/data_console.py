#!/usr/bin/env python3
"""Interactive CSV inspection: actual rows, validation, repair and export."""
import csv
import hashlib
import json
from terminal_style import page, paint, row, fresh_workspace


def main():
    root = fresh_workspace('data-console')
    source = root / 'orders.csv'
    source.write_text('order,product,quantity,price\nA01,Notebook,3,12\nA02,Keyboard,2,79\nA03,Monitor,-1,299\nA04,Mouse,4,25\nA05,Desk,1,invalid\nA06,Headset,2,59\n')
    current = source
    valid, invalid = [], []
    checked = False
    history = ['准备了 6 行演示 CSV；尚未检查。']
    while True:
        with current.open(newline='') as f:
            records = list(csv.DictReader(f))
        page('03', 'DATA QUALITY CONSOLE', '交互式本地数据检查 · scan / check / repair / export / quit')
        row('Source', 'CSV', current.name + ' · ' + str(current.stat().st_size) + ' bytes', 'cyan')
        row('Rows on disk', str(len(records)), 'Actual CSV records', 'purple')
        row('Validation', 'PENDING' if not checked else ('FAIL' if invalid else 'PASS'),
            '尚未校验' if not checked else f'{len(valid)} valid / {len(invalid)} invalid',
            'amber' if not checked else ('red' if invalid else 'mint'))
        print('\n  ' + paint('ORDER   PRODUCT         QTY   PRICE        STATUS', 'muted', True))
        for record in records:
            bad = checked and record in invalid
            status = 'INVALID' if bad else ('VALID' if checked else 'WAITING')
            text = f"{record['order']:<7} {record['product']:<15} {record['quantity']:<5} {record['price']:<12} {status}"
            print('  ' + paint(text, 'red' if bad else ('mint' if checked else 'muted')))
        print('\n  ' + paint('EVENTS', 'purple', True))
        for event in history[-4:]:
            print('  ' + paint('› ' + event, 'muted'))
        command = input('\n  data> ').strip().lower()
        if command == 'scan':
            history.append('SHA-256 ' + hashlib.sha256(current.read_bytes()).hexdigest()[:32])
        elif command == 'check':
            valid, invalid = [], []
            for record in records:
                try:
                    okay = int(record['quantity']) > 0 and float(record['price']) >= 0
                except ValueError:
                    okay = False
                (valid if okay else invalid).append(record)
            checked = True
            history.append(f'实际校验：{len(valid)} 行有效，{len(invalid)} 行无效。')
        elif command == 'repair':
            if not checked:
                history.append('先 check，再决定如何处理；本示例只过滤无效行。')
                continue
            current = root / 'cleaned.csv'
            with current.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['order', 'product', 'quantity', 'price'])
                writer.writeheader(); writer.writerows(valid)
            checked = False
            history.append('写入 cleaned.csv；保留原 orders.csv，等待重新 check。')
        elif command == 'export':
            if not checked or invalid:
                history.append('BLOCKED：先通过检查，再导出。')
                continue
            total = sum(int(r['quantity']) * float(r['price']) for r in valid)
            result = {'rows': len(valid), 'total': total, 'source': current.name,
                      'sha256': hashlib.sha256(current.read_bytes()).hexdigest()}
            (root / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
            history.append(f'EXPORTED summary.json · {len(valid)} rows · total {total:.2f}')
        elif command == 'quit':
            break
        else:
            history.append('未知命令；可用 scan / check / repair / export / quit。')
    print('Session closed. Files preserved in .color-lab/data-console/')


if __name__ == '__main__':
    main()
