from __future__ import annotations
import json, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; R=ROOT/'data/processed/current_season_results.json'; H=ROOT/'data/predictions/prediction_history.json'; O=ROOT/'data/predictions/completed_matches.json'; T=O.with_suffix('.json.tmp')
def load(p):
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
    except (OSError,json.JSONDecodeError):return []
def main():
    hist={str(x.get('id')):x for x in load(H) if x.get('id') is not None}; out=[]
    for r in load(R):
        x=dict(r); p=hist.get(str(r.get('id')))
        x['prediction']=p
        x['prediction_status']='recorded' if p else '予測記録なし'
        if p:
            x['predicted_result']=p.get('predicted_result'); x['is_correct']=p.get('predicted_result')==r.get('actual_result')
            x['probabilities']={k:p.get(k) for k in ('home_win_probability','draw_probability','away_win_probability')}
        out.append(x)
    T.parent.mkdir(parents=True,exist_ok=True); T.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); json.loads(T.read_text(encoding='utf-8')); os.replace(T,O)
if __name__=='__main__':main()
