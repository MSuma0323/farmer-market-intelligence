from pathlib import Path
import sys
p = Path('backend/data/potato_dataset.csv')
if not p.exists():
    print('File not found:', p)
    sys.exit(2)
raw = p.read_text(encoding='utf-8', errors='replace')
# quick checks
has_tab = '\t' in raw
lines = raw.splitlines()
header = lines[0] if lines else ''
num_rows = max(0, len(lines)-1)
# try pandas if available
try:
    import pandas as pd
    df = pd.read_csv(p)
    print('Loaded with pandas')
    print('Shape:', df.shape)
    print('\nDtypes:')
    print(df.dtypes)
    print('\nHead:')
    print(df.head(5).to_string(index=False))
except Exception as e:
    print('Pandas load failed or not available:', e)
    print('\nFallback summary:')
    print('Header:', header)
    print('Rows (excluding header):', num_rows)
    # sample first 10 data lines
    sample = lines[1:11]
    for i, ln in enumerate(sample, start=1):
        comma_count = ln.count(',')
        tab_count = ln.count('\t')
        print(f'{i}: commas={comma_count}, tabs={tab_count} -> {ln}')
    if has_tab:
        print('\nWarning: file still contains tab characters')
    else:
        print('\nNo tab characters found')
