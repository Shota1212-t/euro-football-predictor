import json, joblib, numpy as np, pandas as pd, torch
from torch import nn
from torch.utils.data import DataLoader,TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from .config import PROCESSED_DIR,MODEL_DIR,REPORT_DIR,RANDOM_STATE
from .features import feature_columns
from .split import chronological_split
from .evaluate import evaluate
class MLP(nn.Module):
    def __init__(self,n):
        super().__init__(); self.net=nn.Sequential(nn.Linear(n,64),nn.BatchNorm1d(64),nn.ReLU(),nn.Dropout(.25),nn.Linear(64,32),nn.ReLU(),nn.Dropout(.15),nn.Linear(32,3))
    def forward(self,x): return self.net(x)
def train(epochs=150):
    torch.manual_seed(RANDOM_STATE); df=pd.read_csv(PROCESSED_DIR/'training_data.csv',parse_dates=['Date']); tr,va,te=chronological_split(df); cols=feature_columns(df)
    imp=SimpleImputer(strategy='median'); sc=StandardScaler(); Xtr=sc.fit_transform(imp.fit_transform(tr[cols])); Xva=sc.transform(imp.transform(va[cols])); Xte=sc.transform(imp.transform(te[cols]))
    loader=DataLoader(TensorDataset(torch.tensor(Xtr,dtype=torch.float32),torch.tensor(tr.target.values,dtype=torch.long)),batch_size=64,shuffle=True)
    model=MLP(len(cols)); opt=torch.optim.AdamW(model.parameters(),lr=1e-3,weight_decay=1e-4); lossfn=nn.CrossEntropyLoss(); best=float('inf'); best_state=None; wait=0
    for epoch in range(epochs):
        model.train()
        for x,y in loader: opt.zero_grad(); loss=lossfn(model(x),y); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad(): vl=float(lossfn(model(torch.tensor(Xva,dtype=torch.float32)),torch.tensor(va.target.values,dtype=torch.long)))
        if vl<best-1e-4: best=vl; best_state={k:v.cpu().clone() for k,v in model.state_dict().items()}; wait=0
        else: wait+=1
        if wait>=15: break
    model.load_state_dict(best_state); model.eval()
    with torch.no_grad(): proba=torch.softmax(model(torch.tensor(Xte,dtype=torch.float32)),dim=1).numpy()
    metrics=evaluate(te.target,proba); MODEL_DIR.mkdir(parents=True,exist_ok=True); REPORT_DIR.mkdir(parents=True,exist_ok=True)
    torch.save({'state_dict':model.state_dict(),'input_size':len(cols),'features':cols},MODEL_DIR/'neural_network.pth'); joblib.dump({'imputer':imp,'scaler':sc},MODEL_DIR/'neural_preprocess.joblib')
    (REPORT_DIR/'neural_network_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(metrics,ensure_ascii=False,indent=2)); return metrics
if __name__=='__main__': train()
