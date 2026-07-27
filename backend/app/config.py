"""アプリ全体の設定。すべての値は環境変数（.env）から読み込む。
APIキーやDB接続情報をソースコードに直書きしないためのモジュール。
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# プロジェクトルート（backend/app/config.py から2階層上）
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
PREDICTIONS_DIR = DATA_DIR / "predictions"
RAW_DIR = DATA_DIR / "raw"


class Settings(BaseSettings):
    # 外部API（値が空でもアプリは起動する＝取得ジョブ側でのみ必須）
    football_data_api_key: str = ""
    api_football_key: str = ""
    thesportsdb_api_key: str = ""

    # DB（将来JSONファイルからDBへ移行する場合のために残してあるが、
    # 現状のAPIはdata/配下のJSONファイルを直接読む実装になっている）
    database_url: str = "postgresql://postgres:postgres@localhost:5432/euro_football_predictor"

    backend_base_url: str = "http://localhost:8000"
    next_public_api_base_url: str = "http://localhost:8000"

    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
