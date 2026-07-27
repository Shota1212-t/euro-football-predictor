import numpy as np
import pandas as pd
from .config import TARGET_MAP
BASE_OPTIONAL=['HS','AS','HST','AST','B365H','B365D','B365A']

def _points(result, side):
    if result=='D': return 1
    return 3 if (result=='H' and side=='home') or (result=='A' and side=='away') else 0

def build_features(matches, window=5):
    """各試合直前までの情報だけを使用。行を日付順に処理し、更新は特徴量作成後に行う。"""
    df=matches.sort_values('Date').reset_index(drop=True).copy()
    history={}; rows=[]
    for _,m in df.iterrows():
        h,a=m.HomeTeam,m.AwayTeam; hh=history.get(h,[]); ah=history.get(a,[])
        def agg(hist):
            recent=hist[-window:]
            if not recent: return dict(points=0,gf=0,ga=0,shots=0,sot=0,days=14,played=0)
            return dict(points=sum(x['points'] for x in recent)/len(recent),gf=sum(x['gf'] for x in recent)/len(recent),ga=sum(x['ga'] for x in recent)/len(recent),shots=sum(x['shots'] for x in recent)/len(recent),sot=sum(x['sot'] for x in recent)/len(recent),days=max(1,(m.Date-recent[-1]['date']).days),played=len(recent))
        H,A=agg(hh),agg(ah)
        row={'Date':m.Date,'HomeTeam':h,'AwayTeam':a,'target':TARGET_MAP[m.FTR],
             'home_recent_points':H['points'],'away_recent_points':A['points'],'recent_points_diff':H['points']-A['points'],
             'home_recent_gf':H['gf'],'away_recent_gf':A['gf'],'recent_gf_diff':H['gf']-A['gf'],
             'home_recent_ga':H['ga'],'away_recent_ga':A['ga'],'recent_ga_diff':H['ga']-A['ga'],
             'home_recent_shots':H['shots'],'away_recent_shots':A['shots'],'home_recent_sot':H['sot'],'away_recent_sot':A['sot'],
             'home_days_rest':H['days'],'away_days_rest':A['days'],'rest_days_diff':H['days']-A['days'],
             'home_history_count':H['played'],'away_history_count':A['played']}
        for c in ['B365H','B365D','B365A']:
            row[c]=pd.to_numeric(m.get(c,np.nan),errors='coerce')
        rows.append(row)
        hs=pd.to_numeric(m.get('HS',0),errors='coerce'); ass=pd.to_numeric(m.get('AS',0),errors='coerce'); hst=pd.to_numeric(m.get('HST',0),errors='coerce'); ast=pd.to_numeric(m.get('AST',0),errors='coerce')
        hs=0 if pd.isna(hs) else hs; ass=0 if pd.isna(ass) else ass; hst=0 if pd.isna(hst) else hst; ast=0 if pd.isna(ast) else ast
        history.setdefault(h,[]).append({'date':m.Date,'points':_points(m.FTR,'home'),'gf':m.FTHG,'ga':m.FTAG,'shots':hs,'sot':hst})
        history.setdefault(a,[]).append({'date':m.Date,'points':_points(m.FTR,'away'),'gf':m.FTAG,'ga':m.FTHG,'shots':ass,'sot':ast})
    out=pd.DataFrame(rows)
    # 履歴ゼロの序盤を除外
    out=out[(out.home_history_count>=window)&(out.away_history_count>=window)].reset_index(drop=True)
    return out

def feature_columns(df):
    excluded={'Date','HomeTeam','AwayTeam','target'}
    return [c for c in df.columns if c not in excluded]
