"""データソース説明ページ（UI設計書 17章）。"""
from fastapi import APIRouter
from .. import data_store as ds

router = APIRouter(prefix="/api/v1/data-sources", tags=["data-sources"])


@router.get("")
def data_sources():
    return ds.get_data_sources()
