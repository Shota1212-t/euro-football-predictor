"""データ更新状況ページ（UI設計書 16章）。"""
from fastapi import APIRouter
from .. import data_store as ds

router = APIRouter(prefix="/api/v1/data-status", tags=["data-status"])


@router.get("")
def data_status():
    items = ds.get_data_status()
    for item in items:
        item["is_stale"] = ds.is_stale(item.get("last_updated"))
    return items
