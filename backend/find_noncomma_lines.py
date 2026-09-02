from pathlib import Path

p = Path('backend/data/potato_dataset.csv')
text = p.read_text(encoding='utf-8')
lines = text.splitlines()
bad = []
for i, line in enumerate(lines, start=1):
    # expecting 5 commas (6 columns)
    if line.count(',') < 5:
        bad.append((i, line))

print(f"Total lines: {len(lines)}; Non-comma lines: {len(bad)}")
for idx, ln in bad[:50]:
    print(idx, repr(ln))
