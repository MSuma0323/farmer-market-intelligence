from pathlib import Path

from data_utils import load_price_data


def test_onion_dataset_is_loaded():
    df = load_price_data(Path(__file__).resolve().parent / 'data')
    onion_rows = df[df['crop_name'] == 'Onion']
    assert not onion_rows.empty
    assert 'Arakalgud APMC' in onion_rows['market_name'].unique().tolist()
