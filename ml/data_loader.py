from pathlib import Path
import pandas as pd
from .config import RAW_DIR, PROCESSED_DIR
REQUIRED={'Date','HomeTeam','AwayTeam','FTHG','FTAG','FTR'}

def load_raw_matches(raw_dir=RAW_DIR):
    files=[p for p in Path(raw_dir).glob('*.csv') if p.name!='sample_schema.csv']
    if not files:
        raise FileNotFoundError(f'CSVがありません: {raw_dir}')
    frames=[]
    for p in sorted(files):
        df=pd.read_csv(p, encoding_errors='replace')
        missing=REQUIRED-set(df.columns)
        if missing: raise ValueError(f'{p.name} に必須列がありません: {sorted(missing)}')
        df['source_file']=p.name
        frames.append(df)
    df=pd.concat(frames,ignore_index=True)
    df['Date']=pd.to_datetime(df['Date'],dayfirst=True,errors='coerce')
    df=df.dropna(subset=['Date','HomeTeam','AwayTeam','FTR']).sort_values('Date').drop_duplicates(['Date','HomeTeam','AwayTeam'],keep='last')
    df=df[df['FTR'].isin(['H','D','A'])].reset_index(drop=True)
    return df

def save_clean_matches(df):
    PROCESSED_DIR.mkdir(parents=True,exist_ok=True)
    path=PROCESSED_DIR/'matches.csv'; df.to_csv(path,index=False); return path
