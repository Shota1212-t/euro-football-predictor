import json

import joblib
import pandas as pd

from .config import MODEL_DIR, TARGET_NAMES


class Predictor:
    def __init__(self):
        self.model = joblib.load(MODEL_DIR / "lightgbm_model.joblib")
        self.meta = json.loads(
            (MODEL_DIR / "lightgbm_metadata.json").read_text(encoding="utf-8")
        )

    def predict_features(self, features: dict):
        columns = self.meta["features"]
        X = pd.DataFrame([{column: features.get(column) for column in columns}])
        probabilities = self.model.predict_proba(X)[0]
        classes = list(getattr(self.model, "classes_", range(len(probabilities))))

        by_class = {
            int(label): float(probability)
            for label, probability in zip(classes, probabilities)
        }
        class_probabilities = [by_class.get(index, 0.0) for index in range(3)]
        predicted_index = max(range(3), key=class_probabilities.__getitem__)

        return {
            "home_win_probability": class_probabilities[0],
            "draw_probability": class_probabilities[1],
            "away_win_probability": class_probabilities[2],
            "predicted_result": TARGET_NAMES[predicted_index],
            "model_version": self.meta["version"],
        }
