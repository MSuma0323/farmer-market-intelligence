from pathlib import Path

p = Path('backend/data/potato_dataset.csv')
if not p.exists():
    print('file missing')
    raise SystemExit(2)
b = p.read_bytes()
print('tab_byte_present:', b'\t' in b)
idx = b.find(b'2024-07-05')
print('index', idx)
if idx != -1:
    print(b[idx:idx+160])
else:
    print('sample date not found')
