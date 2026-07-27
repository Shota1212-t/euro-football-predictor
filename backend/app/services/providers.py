"""外部データ取得の境界（Provider）。

重要：APIキーはこのモジュール（バックエンド／バッチ側）でのみ扱い、
フロントエンドには一切渡さないこと（設計書 追記：環境変数・APIキー管理方針を参照）。

ここではインターフェースのみ定義している。実際の取得・整形ロジックは
scripts/ 配下、または ml/data_loader.py 側で実装し、最終的に
data/processed/*.json, data/raw/* に書き出す形にすると、
backend/app/data_store.py がそのまま拾ってAPI経由でフロントエンドに渡せる。

例として football-data.org 用の最小実装を1つだけ用意している
（scripts/fetch_football_data_org.py）。API-FOOTBALL / TheSportsDB は
同じ形（fixtures/standings/players を取得して dict で返す）で実装すればよい。
"""
from abc import ABC, abstractmethod
from typing import Any


class FootballProvider(ABC):
    """全プロバイダ共通のインターフェース。"""

    @abstractmethod
    async def fixtures(self, competition: str) -> list[dict[str, Any]]:
        """指定リーグの試合日程を取得する。"""

    @abstractmethod
    async def standings(self, competition: str) -> list[dict[str, Any]]:
        """指定リーグの順位表を取得する。"""


class FootballDataOrgProvider(FootballProvider):
    """football-data.org (https://www.football-data.org/documentation/api)"""

    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"X-Auth-Token": self.api_key}

    async def fixtures(self, competition: str) -> list[dict[str, Any]]:
        import httpx
        async with httpx.AsyncClient(base_url=self.BASE_URL, headers=self._headers(), timeout=20) as client:
            r = await client.get(f"/competitions/{competition}/matches", params={"status": "SCHEDULED"})
            r.raise_for_status()
            return r.json().get("matches", [])

    async def standings(self, competition: str) -> list[dict[str, Any]]:
        import httpx
        async with httpx.AsyncClient(base_url=self.BASE_URL, headers=self._headers(), timeout=20) as client:
            r = await client.get(f"/competitions/{competition}/standings")
            r.raise_for_status()
            return r.json().get("standings", [])


class ApiFootballProvider(FootballProvider):
    """API-FOOTBALL / API-SPORTS (https://www.api-football.com/documentation-v3)
    未実装。football-data.org と同じ形で fixtures / standings を実装する。
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fixtures(self, competition: str) -> list[dict[str, Any]]:
        raise NotImplementedError("API-FOOTBALL の fixtures 取得をここに実装してください。")

    async def standings(self, competition: str) -> list[dict[str, Any]]:
        raise NotImplementedError("API-FOOTBALL の standings 取得をここに実装してください。")


class TheSportsDBProvider:
    """TheSportsDB: チーム/選手の画像・プロフィール補完用。
    未実装。team logo / player photo を team_id, player_id をキーに取得する想定。
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def team_logo(self, team_name: str) -> str | None:
        raise NotImplementedError("TheSportsDB のロゴ取得をここに実装してください。")
