from .data_loader import load_raw_matches,save_clean_matches
from .features import build_features
from .config import PROCESSED_DIR
def run():
    raw=load_raw_matches(); p=save_clean_matches(raw); features=build_features(raw); out=PROCESSED_DIR/'training_data.csv'; features.to_csv(out,index=False)
    print(f'試合データ: {len(raw)}件 -> {p}'); print(f'学習データ: {len(features)}件 -> {out}'); return features
if __name__=='__main__': run()
