import sys
from pathlib import Path

def fix(path_str):
    p = Path(path_str)
    if not p.exists():
        print(f"File not found: {p}")
        return 2
    data = p.read_bytes()
    if b'\t' not in data:
        print("No tab bytes found — nothing to do.")
        return 0
    backup = p.with_suffix(p.suffix + '.bak')
    backup.write_bytes(data)
    new = data.replace(b'\t', b',')
    p.write_bytes(new)
    print(f"Replaced tabs with commas in {p}. Backup: {backup}")
    return 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: fix_all_tabs.py <file>")
        sys.exit(2)
    sys.exit(fix(sys.argv[1]))
