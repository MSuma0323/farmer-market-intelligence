from pathlib import Path
import sys

def fix_file(path_str: str):
    p = Path(path_str)
    if not p.exists():
        print(f"File not found: {p}")
        return 2
    text = p.read_text(encoding='utf-8')
    if '\t' not in text:
        print(f"No tabs found in {p}; nothing changed.")
        return 0
    new = text.replace('\t', ',')
    p.write_text(new, encoding='utf-8')
    print(f"Replaced tabs with commas in {p}")
    return 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python fix_delimiters.py <file.csv>")
        sys.exit(2)
    sys.exit(fix_file(sys.argv[1]))
