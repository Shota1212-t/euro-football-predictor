# Euro Football Predictor

欧州5大リーグの試合予測Webアプリ。`frontend`(Next.js) / `backend`(FastAPI) / `ml`(学習パイプライン) の3つで構成。
バックエンドはDBを使わず、`data/processed` と `data/predictions` のJSONファイルをそのまま返す設計。
**JSONを更新すれば、APIもフロントエンドの表示もそのまま更新される。**

## 今すぐ動かす（デモデータ）

```bash
cp .env.example .env

# 1. デモデータ生成（実データが無くても全ページ表示できる）
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd .. && python scripts/generate_demo_data.py

# 2. バックエンド起動
cd backend && PYTHONPATH=.. uvicorn app.main:app --reload --port 8000
# -> http://localhost:8000/docs

# 3. フロントエンド起動（別ターミナル）
cd frontend && cp .env.local.example .env.local && npm install && npm run dev
# -> http://localhost:3000
```

## 実データに差し替える手順

1. `.env` に `FOOTBALL_DATA_API_KEY` など取得したAPIキーを設定
2. `python scripts/fetch_football_data_org.py` を実行
   → `data/processed/standings/*.json` が実データで上書きされる（動作する参考実装）
3. API-FOOTBALL / TheSportsDB は `backend/app/services/providers.py` にインターフェースのみ用意した。
   `fetch_football_data_org.py` と同じ形（取得→`backend/app/schemas.py`のキー名でJSON化→`data/processed`に書き出し）で実装する
4. `data/raw/football_data_co_uk/` に過去シーズンCSVを配置し、Anaconda環境で学習：
   ```bash
   conda env create -f environment.yml
   conda activate euro-football-predictor
   python -m ml.pipeline        # prepare_data -> train_lightgbm -> train_neural_network -> compare
   ```
   → `ml/models/` にモデル、`ml/evaluate.py` の出力を `data/predictions/model_performance.json` に保存
5. 学習済みモデル＋直近フィクスチャ＋疲労指数（`backend/app/services/fatigue.py`）から
   `data/predictions/matches.json` を生成するバッチを作る（`scripts/generate_demo_data.py` の
   `build_predictions()` が出力フォーマットの実例）

以降はバックエンド／フロントエンドの再起動だけで実データに切り替わる。

## Docker

```bash
docker compose up --build
```

## ディレクトリ構成

```
backend/   FastAPI（data/ 配下のJSONを読んでAPI化するだけ。DBなし）
frontend/  Next.js（バックエンドAPIをfetchして表示。外部APIキーは持たない）
ml/        学習パイプライン（Anaconda想定。football-data.co.uk CSVで学習）
data/
  raw/           元データ（CSV等）
  processed/     チーム/選手/監督/順位表/ランキング（あなたの取得スクリプトが書く）
  predictions/   試合予測・モデル精度（mlパイプラインが書く）
scripts/
  generate_demo_data.py       デモデータ生成（形式サンプルも兼ねる）
  fetch_football_data_org.py  football-data.org 取得の参考実装
```

## セキュリティ

外部APIキーは `backend`・`scripts`・`ml` 側だけで使用し、フロントエンドには渡さない。
`.env` はGit管理しない（`.gitignore` 済み）。
