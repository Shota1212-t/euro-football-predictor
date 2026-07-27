import json, joblib, pandas as pd
from .config import MODEL_DIR,TARGET_NAMES
class Predictor:
    def __init__(self):
        self.model=joblib.load(MODEL_DIR/'lightgbm_model.joblib'); self.meta=json.loads((MODEL_DIR/'lightgbm_metadata.json').read_text(encoding='utf-8'))
    def predict_features(self,features:dict):
        X=pd.DataFrame([{c:features.get(c) for c in self.meta['features']}]); p=self.model.predict_proba(X)[0]; i=int(p.argmax())
        return {'home_win_probability':float(p[0]),'draw_probability':float(p[1]),'away_win_probability':float(p[2]),'predicted_result':TARGET_NAMES[i],'model_version':self.meta['version']}
