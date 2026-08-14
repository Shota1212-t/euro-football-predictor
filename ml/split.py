from __future__ import annotations

from collections.abc import Iterator

import pandas as pd


def _sorted(df: pd.DataFrame) -> pd.DataFrame:
    if "Date" not in df.columns:
        raise ValueError("Date column is required for chronological splitting")
    result = df.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    if result["Date"].isna().any():
        raise ValueError("Date contains missing or invalid values")
    return result.sort_values("Date", kind="stable").reset_index(drop=True)


def chronological_split(df, train_ratio=.7, val_ratio=.15):
    data = _sorted(df)
    n = len(data)
    train_end = int(n * train_ratio)
    validation_end = int(n * (train_ratio + val_ratio))
    if train_end < 50 or validation_end <= train_end or n - validation_end < 20:
        raise ValueError(
            f"データ不足です。特徴量生成後 {n} 試合。より多くのCSVを追加してください。"
        )
    return (
        data.iloc[:train_end].copy(),
        data.iloc[train_end:validation_end].copy(),
        data.iloc[validation_end:].copy(),
    )


def calibration_selection_split(validation: pd.DataFrame, ratio: float = 0.5):
    """Split validation by complete match dates to prevent date overlap."""
    data = _sorted(validation)
    unique_dates = data["Date"].drop_duplicates().sort_values().reset_index(drop=True)
    boundary = int(len(unique_dates) * ratio)
    if boundary <= 0 or boundary >= len(unique_dates):
        raise ValueError("校正用と選択用に分割できる日付数が不足しています")

    selection_start = unique_dates.iloc[boundary]
    calibration = data[data["Date"] < selection_start].copy()
    selection = data[data["Date"] >= selection_start].copy()
    if len(calibration) < 20 or len(selection) < 20:
        raise ValueError("校正用と選択用にそれぞれ20試合以上必要です")
    return calibration, selection


def expanding_window_splits(
    df: pd.DataFrame,
    *,
    n_splits: int = 4,
    min_train_ratio: float = 0.5,
    evaluation_ratio: float = 0.1,
) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
    """Generate expanding-window folds using complete match dates.

    Several matches can share the same calendar date. Boundaries are therefore
    calculated from unique dates, so a date can never appear in both training
    and evaluation data.
    """
    data = _sorted(df)
    unique_dates = data["Date"].drop_duplicates().sort_values().reset_index(drop=True)
    date_count = len(unique_dates)
    first_train_date_count = int(date_count * min_train_ratio)
    evaluation_date_count = max(1, int(date_count * evaluation_ratio))

    if first_train_date_count <= 0:
        raise ValueError("ローリング評価の初期学習期間が不足しています")

    produced = 0
    for index in range(n_splits):
        evaluation_start_index = first_train_date_count + index * evaluation_date_count
        evaluation_end_index = evaluation_start_index + evaluation_date_count
        if evaluation_end_index > date_count:
            break

        evaluation_start = unique_dates.iloc[evaluation_start_index]
        evaluation_end = unique_dates.iloc[evaluation_end_index - 1]
        train = data[data["Date"] < evaluation_start].copy()
        evaluation = data[
            (data["Date"] >= evaluation_start) & (data["Date"] <= evaluation_end)
        ].copy()

        if len(train) < 50 or len(evaluation) < 20:
            continue
        if train["Date"].max() >= evaluation["Date"].min():
            raise ValueError("時系列分割で学習期間と評価期間が重複しています")

        produced += 1
        yield train, evaluation

    if produced < 2:
        raise ValueError("ローリング評価には2分割以上必要です")
