"""Small ANSI presentation helpers; no network or third-party dependencies."""
import os
import sys
from pathlib import Path

COLORS = {'mint': '84;225;179', 'cyan': '105;200;255', 'amber': '255;202;105',
          'red': '255;119;143', 'purple': '185;161;255', 'muted': '155;169;191',
          'white': '234;240;250'}


def paint(text, color='white', bold=False):
    if not sys.stdout.isatty() or os.environ.get('NO_COLOR'):
        return str(text)
    return '\033[' + ('1;' if bold else '') + '38;2;' + COLORS[color] + 'm' + str(text) + '\033[0m'


def page(number, title, subtitle):
    if sys.stdout.isatty():
        print('\033[2J\033[H', end='')
    print(paint('  PAIWARP  /  COLOR LAB', 'cyan', True))
    print(paint('  ' + '─' * 88, 'muted'))
    print('\n  ' + paint(number + '  ' + title, 'white', True))
    print('  ' + paint(subtitle, 'muted') + '\n')


def row(label, status, detail, color='mint'):
    print('  ' + paint(status.ljust(11), color, True) + ' ' + label.ljust(21) + paint(detail, 'muted'))


def checkpoint(label):
    print('\n  ' + paint('CAPTURE  ' + label, 'purple', True))
    input('  按 Enter 继续 > ')


def fresh_workspace(name):
    root = Path('.color-lab') / name
    if root.exists():
        raise SystemExit(f'{root} 已存在，请使用新的工作区，避免覆盖上次结果。')
    root.mkdir(parents=True)
    return root.resolve()
