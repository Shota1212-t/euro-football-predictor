"""本番モデルの評価情報とオンデマンド予測API。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .. import data_store as ds

router = APIRouter(prefix="/api/v1/model", tags=["model"])


@router.get("/performance")
def performance():
    perf = ds.get_model_performance()
    if perf is None:
        raise HTTPException(
            404,
            "モデル精度データがありません。"
            "python scripts/update_model_performance.py を実行してください。",
        )
    return perf


class FeatureRequest(BaseModel):
    features: dict[str, float | None]


@router.get("/status")
def status():
    try:
        from ml.predict import Predictor
        predictor = Predictor()
        return {
            "ready": True,
            "model_version": predictor.meta.get("version"),
            "metrics": predictor.meta.get("metrics"),
        }
    except Exception as error:
        return {"ready": False, "reason": str(error)}


@router.post("/predict")
def predict(req: FeatureRequest):
    try:
        from ml.predict import Predictor
        return Predictor().predict_features(req.features)
    except FileNotFoundError as error:
        raise HTTPException(
            503,
            "学習済みモデルが見つかりません。python -m ml.train_lightgbm を実行してください。",
        ) from error
    except Exception as error:
        raise HTTPException(400, str(error)) from error
