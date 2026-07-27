from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RAW_DIR=ROOT/'data'/'raw'/'football_data_co_uk'
PROCESSED_DIR=ROOT/'data'/'processed'
MODEL_DIR=ROOT/'ml'/'models'
REPORT_DIR=ROOT/'reports'
TARGET_MAP={'H':0,'D':1,'A':2}
TARGET_NAMES=['HOME_WIN','DRAW','AWAY_WIN']
RANDOM_STATE=42
