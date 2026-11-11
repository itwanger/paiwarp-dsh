#!/usr/bin/env python3
"""A tiny stdlib-only todo list used as PaiWarp's non-PaiCLI example."""
import json
import sys
from pathlib import Path


def load(path):
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save(path, items):
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n")


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "todos.json")
    items = load(path)
    print("PaiWarp todo. 命令：add <内容> / list / done <编号> / quit")
    while True:
        try:
            line = input("todo> ").strip()
        except EOFError:
            break
        if not line:
            continue
        command, _, rest = line.partition(" ")
        if command == "quit":
            break
        if command == "add" and rest.strip():
            items.append({"text": rest.strip(), "done": False})
            save(path, items)
            print(f"已添加第 {len(items)} 项")
        elif command == "list":
            if not items:
                print("（空）")
            for index, item in enumerate(items, 1):
                mark = "x" if item["done"] else " "
                print(f"{index}. [{mark}] {item['text']}")
        elif command == "done" and rest.strip().isdigit():
            number = int(rest)
            if 1 <= number <= len(items):
                items[number - 1]["done"] = True
                save(path, items)
                print(f"完成第 {number} 项")
            else:
                print("没有这个编号")
        else:
            print("用法：add <内容> / list / done <编号> / quit")
    save(path, items)
    print(f"保存到 {path}，共 {len(items)} 项")
    return 0


if __name__ == "__main__":
    sys.exit(main())
