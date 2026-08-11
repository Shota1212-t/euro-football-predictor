# Euro Football Predictor

欧州5大リーグを対象に、実日程・順位表・クラブ／選手情報・機械学習による試合予測をまとめて閲覧できるWebアプリケーションです。

Next.jsのフロントエンド、FastAPIのバックエンド、LightGBMの予測パイプラインで構成されています。バックエンドはデータベースを使用せず、`data/processed`および`data/predictions`のJSONをAPIとして配信します。

Web App:
https://euro-football-predictor-web.vercel.app

API:
https://euro-football-predictor.vercel.app

API Docs:
https://euro-football-predictor.vercel.app/docs

> [!IMPORTANT]
> 本アプリの勝敗確率は、未校正の機械学習モデルが出力した参考値です。実際の発生確率、賭けの推奨、利益を保証する情報ではありません。

## 主な機能

- Premier League、La Liga、Serie A、Bundesliga、Ligue 1に対応
- 次節48試合のホーム勝利・引き分け・アウェイ勝利予測
- 5大リーグの順位表、得点・アシスト・出場数ランキング
- 96クラブの一覧・詳細、エンブレム表示
- 1,698人の選手一覧・詳細、現所属確認状態の表示
- 監督一覧・詳細、暫定所属情報の明示
- SHAPによる試合単位の予測要因表示
- リーグ戦、Champions League、取得可能なカップ戦情報を使った疲労指数
- モデル評価、データ取得状況、データソースの表示
- API取得・予測・評価・状態更新の一括実行
- JSON検証、原子的保存、既存データ保護
- pytestによる予測パイプラインの自動テスト

## 現在のデータ状態

2026年7月時点の開発データです。

| 項目 | 件数・状態 |
|---|---:|
| 対象クラブ | 96クラブ |
| リーグ日程 | 1,752試合 |
| 次節予測 | 48試合 |
| 選手 | 1,698人 |
| 監督 | 38人（暫定所属） |
| 追加大会 | 209試合 |
| SHAP説明 | 48試合 |
| 自動テスト | 24件 |

開幕前は順位表を0試合・0勝点で表示し、選手ランキングは`preseason`状態になります。開幕後にデータ提供元が現シーズン情報を返すと、更新処理によって実データへ切り替わります。

## 技術スタック

### Frontend

- Next.js 14.2.13
- React
- TypeScript
- Lucide React

### Backend

- FastAPI
- Uvicorn
- Pydantic
- JSONベースのデータストア

### Machine Learning / Data

- Python 3.11
- LightGBM
- scikit-learn
- pandas / NumPy
- SHAP
- joblib

## アーキテクチャ

```text
External data sources
  ├─ football-data.org
  ├─ Football-Data.co.uk
  └─ TheSportsDB
          │
          ▼
      scripts/*.py
          │
          ├─ data/processed/*.json
          ├─ data/predictions/*.json
          └─ ml/models/lightgbm_model.joblib
                  │
                  ▼
             FastAPI backend
                  │
                  ▼
             Next.js frontend
```

## ディレクトリ構成

```text
backend/                  FastAPI API
  app/
    routers/              APIルーター
    services/             疲労指数・データ取得関連
frontend/                 Next.jsフロントエンド
  app/                    App Routerのページ・型・共通UI
ml/                       学習・評価・推論パイプライン
  models/                 本番LightGBMモデルとメタデータ
data/
  processed/              日程・順位表・チーム・選手・監督・ランキング
  predictions/            次節予測・モデル評価
  raw/                    学習用CSV（Git管理対象外）
scripts/                  取得・照合・予測・一括更新スクリプト
test/                     pytestテスト
reports/                  モデル評価結果
```

## セットアップ

### 前提

- Python 3.11
- Conda
- Node.js / npm
- football-data.orgのAPIキー

### 1. リポジトリを取得

```bash
git clone <YOUR_REPOSITORY_URL>
cd euro-football-predictor
```

### 2. Python環境を準備

```bash
conda create -n football-env python=3.11 -y
conda activate football-env
pip install -r backend/requirements.txt
```

予測生成・モデル学習も実行する場合は、使用するConda環境へLightGBM、pandas、scikit-learn、SHAP、joblibなどのML依存関係も導入してください。

### 3. 環境変数を設定

プロジェクト直下に`.env`を作成します。

```dotenv
FOOTBALL_DATA_API_KEY=your_football_data_org_api_key
API_FOOTBALL_KEY=your_optional_api_football_key
```

`API_FOOTBALL_KEY`は現在の本番更新処理では使用しません。`.env`はGit管理対象外です。

フロントエンドでは`frontend/.env.local`を作成します。

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### 4. Frontend依存関係を準備

```bash
cd frontend
npm install
cd ..
```

## ローカル起動

バックエンドとフロントエンドを別ターミナルで起動します。

### Backend

```bash
conda activate football-env
cd backend
uvicorn app.main:app --reload
```

- API: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>

### Frontend

```bash
conda activate football-env
cd frontend
npm run dev
```

- Web: <http://localhost:3000>

開発モードでは、初めて開くルートのコンパイルに時間がかかる場合があります。本番相当の速度を確認するときは次を使用します。

```bash
cd frontend
npm run build
npm run start
```

## データ更新

### 通常更新

```bash
python scripts/update_all.py
```

現在の更新工程：

1. 順位表・日程の取得
2. 選手ランキングの取得
3. 欧州大会・カップ戦補完の取得
4. 次節予測・SHAP・疲労指数の生成
5. モデル評価データの更新
6. データ状態の更新

### API取得を省略

既存の取得済みデータを使って、予測・評価・状態だけを更新します。

```bash
python scripts/update_all.py --skip-fetch
```

更新ログは`logs/`へ保存されます。`logs/`はGit管理対象外です。

> [!NOTE]
> `data/raw/`はGit管理対象外です。予測再生成や再学習には、Football-Data.co.ukの1部・2部CSVをローカルの所定フォルダへ配置する必要があります。

## テスト

### Python

```bash
pytest -v
```

現在のテストでは、以下を含む24項目を検証しています。

- チーム名正規化と統一ID
- 1部・2部履歴の使用
- 確率合計と重複試合ID
- 予測JSONの必須項目
- 原子的保存と既存データ保護
- SHAP出力形式と説明内容
- APIキーのJSON混入防止
- 追加大会スキーマと重複除去
- 疲労指数の範囲
- 未来の試合を疲労計算へ含めないこと

### Frontend

```bash
cd frontend
npm run build
```

ビルドではTypeScript、Lint、全ルートの生成を確認します。

## モデル

本番モデル：

```text
lightgbm_no_odds_uncalibrated_v2
```

仕様：

- LightGBM
- オッズ特徴量なし
- `class_weight="balanced"`
- 未校正
- 18特徴量
- 直近5試合、得点・失点、シュート、枠内シュート、休養日数などを使用

時系列ホールドアウト731試合での評価：

| 指標 | 値 |
|---|---:|
| Accuracy | 40.63% |
| Macro F1 | 38.00% |
| Draw Recall | 19.78% |

この評価値は運用開始後の的中率ではなく、過去データを時系列で分割したテスト結果です。

### SHAP

予測クラスに対する寄与の絶対値が大きい特徴量を最大5件保存し、試合詳細画面へ表示します。SHAP値はモデル出力への寄与であり、勝敗確率の増減量そのものではありません。

## データソース

| ソース | 主な用途 |
|---|---|
| football-data.org | 日程、順位表、ランキング、現所属確認、Champions League |
| Football-Data.co.uk | 1部・2部の過去試合、学習、直近成績、シュート統計 |
| TheSportsDB | エンブレム、スタジアム、写真、プロフィール、追加大会の部分補完 |

各サービスの利用条件、再配布条件、レート制限に従ってください。

## データ品質と制限

- 監督情報は38クラブ分のみで、すべて暫定所属として表示します。
- 選手548人・58クラブ分は、football-data.orgで現所属を確認できず、TheSportsDB情報を暫定利用しています。
- 得点・アシスト・出場数ランキングは対応していますが、カードランキングは未実装です。
- Champions Leagueは公式データを使用します。Europa League、Conference League、国内カップは無料APIの取得範囲により部分補完です。
- 移動距離、代表戦、選手別出場時間、怪我、ラインアップは疲労指数へ含まれません。
- 外部データの更新遅延や誤登録が残る場合があります。
- 本アプリは情報提供・研究目的です。予測結果を金銭的判断へ使用しないでください。

## セキュリティ

- `.env`、`frontend/.env.local`、キャッシュ、ログ、バックアップはGit管理しません。
- APIキーをフロントエンドへ渡しません。
- 予測JSONへAPIキーや認証ヘッダーが混入しないことをテストしています。
- 公開前にNext.js 14.2.13を安全なバージョンへ更新し、依存関係監査を実施する必要があります。

## Git運用

```bash
git status
git add .
git commit -m "Describe the change"
git push
```

生成物や秘密情報が誤って追加されていないことを、コミット前に確認してください。

## 今後の課題

- GitHub ActionsによるCIと定期更新
- FastAPIのJSON読込キャッシュによるレスポンス高速化
- Next.js依存関係の安全な更新
- 公開環境の構築
- 開幕後の選手・監督・ランキング再照合
- 監督58クラブ分の信頼できるデータ補完
- カードランキング
- ラインアップ、怪我、移動距離、選手別出場時間の活用
- モデル再評価と確率校正の改善


