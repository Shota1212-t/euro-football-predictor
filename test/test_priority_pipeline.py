import importlib.util,json,sys
from pathlib import Path
import httpx, pytest
ROOT=Path(__file__).resolve().parents[1]
def mod(name):
 p=ROOT/'scripts'/name; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def test_429_retry(monkeypatch):
 m=mod('fetch_football_data_org.py'); calls=[]
 class C:
  def get(self,*a,**k):
   calls.append(1); r=httpx.Response(429 if len(calls)==1 else 200,content='{}',headers={'Retry-After':'0'},request=httpx.Request('GET','https://x')); return r
 monkeypatch.setattr(m.time,'sleep',lambda x:None); monkeypatch.setattr(m,'rate_limit_wait',lambda:None)
 assert m.request_json(C(),'/x')=={} and len(calls)==2
def test_results_atomic(monkeypatch,tmp_path):
 m=mod('fetch_football_data_org.py'); out=tmp_path/'r.json'; tmp=tmp_path/'r.tmp'; monkeypatch.setattr(m,'RESULTS_PATH',out); monkeypatch.setattr(m,'TEMP_RESULTS_PATH',tmp)
 rows=[{'id':'1','status':'FINISHED','kickoff':'x','home_score':1,'away_score':0,'actual_result':'Home Win'}]; m.atomic_write_results(rows); assert json.loads(out.read_text())==rows
def test_completed_marks_missing(tmp_path,monkeypatch):
 m=mod('build_completed_matches.py'); r=tmp_path/'r.json'; h=tmp_path/'h.json'; o=tmp_path/'o.json'; r.write_text(json.dumps([{'id':'1'}])); h.write_text('[]'); monkeypatch.setattr(m,'R',r); monkeypatch.setattr(m,'H',h); monkeypatch.setattr(m,'O',o); monkeypatch.setattr(m,'T',o.with_suffix('.tmp')); m.main(); assert json.loads(o.read_text())[0]['prediction_status']=='予測記録なし'
