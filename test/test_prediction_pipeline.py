from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import data_store as ds

SCRIPT_PATH = PROJECT_ROOT / "scripts" / "generate_real_predictions.py"
FIXTURES_PATH = PROJECT_ROOT / "data" / "processed" / "fixtures.json"
PREDICTIONS_PATH = PROJECT_ROOT / "data" / "predictions" / "matches.json"
EXTRA_FIXTURES_PATH = PROJECT_ROOT / "data" / "processed" / "extra_fixtures.json"
EXTRA_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "fetch_extra_competition_fixtures.py"


def load_prediction_module():
    spec = importlib.util.spec_from_file_location(
        "generate_real_predictions",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"スクリプトを読み込めません: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prediction_module():
    return load_prediction_module()


def load_extra_fixture_module():
    spec = importlib.util.spec_from_file_location(
        "fetch_extra_competition_fixtures",
        EXTRA_SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"スクリプトを読み込めません: {EXTRA_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def extra_fixture_module():
    return load_extra_fixture_module()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_prediction() -> dict:
    return {
        "id": "test-1",
        "league_id": "pl",
        "league_name": "Premier League",
        "kickoff": "2026-08-21T19:00:00Z",
        "home_team": {"id": "fd-1", "name": "Home"},
        "away_team": {"id": "fd-2", "name": "Away"},
        "home_win_probability": 40.0,
        "draw_probability": 30.0,
        "away_win_probability": 30.0,
        "predicted_result": "Home Win",
        "confidence": "Low",
        "data_quality": "full_history",
        "model_version": "test-model",
    }


def test_team_name_normalization(prediction_module):
    assert prediction_module.normalize_name("Brighton & Hove Albion FC") == (
        "brighton and hove albion fc"
    )
    assert prediction_module.normalize_name("Deportivo Alavés") == "deportivo alaves"


def test_second_division_team_aliases(prediction_module):
    known = {
        "Santander",
        "La Coruna",
        "Malaga",
        "Coventry",
        "Hull",
        "Le Mans",
        "Troyes",
        "Paderborn",
        "Elversberg",
        "Hamburg",
        "Schalke 04",
    }
    cases = {
        "Real Racing Club de Santander": "Santander",
        "RC Deportivo La Coruna": "La Coruna",
        "Malaga CF": "Malaga",
        "Coventry City FC": "Coventry",
        "Hull City AFC": "Hull",
        "Le Mans FC": "Le Mans",
        "ES Troyes AC": "Troyes",
        "SC Paderborn 07": "Paderborn",
        "SV 07 Elversberg": "Elversberg",
        "Hamburger SV": "Hamburg",
        "FC Schalke 04": "Schalke 04",
    }
    for api_name, csv_name in cases.items():
        assert prediction_module.second_division_team_name(api_name, known) == csv_name


def test_second_division_csv_files_are_available(prediction_module):
    path = prediction_module.SECOND_DIVISION_PATH

    assert path.exists()
    assert path.is_file()

    matches = prediction_module.load_history_matches(
        path,
        "2部固定履歴CSV",
    )

    assert not matches.empty

    expected_codes = {"E1", "SP2", "D2", "I2", "F2"}
    expected_seasons = {"2324", "2425", "2526"}

    actual_codes = set(matches["Div"].astype(str).unique())
    actual_seasons = set(
        matches["Season"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .unique()
    )

    assert actual_codes == expected_codes
    assert actual_seasons == expected_seasons
    assert len(matches[["Season", "Div"]].drop_duplicates()) == 15


def test_saved_predictions_use_second_division_history():
    predictions = read_json(PREDICTIONS_PATH)

    allowed_data_quality = {
        "full_history",
        "second_division_history",
        "estimated",
    }

    assert predictions, "保存済み予測がありません"

    for item in predictions:
        assert item.get("data_quality") in allowed_data_quality

        if item.get("data_quality") == "second_division_history":
            history_source = item.get("history_source", {})
            assert (
                history_source.get("home") == "second_division"
                or history_source.get("away") == "second_division"
            )


def test_team_payload_uses_football_data_id(prediction_module):
    payload = prediction_module.team_payload(
        {"api_id": 263, "name": "Deportivo Alavés", "short": "ALA"},
        "laliga",
    )
    assert payload["id"] == "fd-263"
    assert payload["api_id"] == 263


def test_timezone_aware_kickoff_can_filter_naive_csv_dates(prediction_module):
    matches = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-05-01", "2026-05-10"]),
            "HomeTeam": ["A", "B"],
            "AwayTeam": ["B", "A"],
        }
    )
    kickoff = pd.Timestamp("2026-08-15T17:30:00Z")
    history = prediction_module.team_history(matches, "A", kickoff)
    assert len(history) == 2


def test_prediction_validation_accepts_valid_record(prediction_module):
    prediction_module.validate_predictions([valid_prediction()], expected_count=1)


def test_prediction_validation_rejects_bad_probability_sum(prediction_module):
    item = valid_prediction()
    item["draw_probability"] = 10.0
    with pytest.raises(ValueError, match="確率合計"):
        prediction_module.validate_predictions([item], expected_count=1)


def test_prediction_validation_rejects_duplicate_match_ids(prediction_module):
    first = valid_prediction()
    second = valid_prediction()
    with pytest.raises(ValueError, match="重複"):
        prediction_module.validate_predictions([first, second], expected_count=2)


def test_atomic_write_keeps_existing_file_on_invalid_data(
    prediction_module,
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "matches.json"
    temporary = tmp_path / "matches.json.tmp"
    backup = tmp_path / "matches_backup.json"
    original = [{"protected": True}]
    output.write_text(json.dumps(original), encoding="utf-8")

    monkeypatch.setattr(prediction_module, "OUTPUT_PATH", output)
    monkeypatch.setattr(prediction_module, "TEMP_OUTPUT_PATH", temporary)
    monkeypatch.setattr(prediction_module, "BACKUP_PATH", backup)

    invalid = valid_prediction()
    invalid["home_win_probability"] = 150.0

    with pytest.raises(ValueError):
        prediction_module.atomic_write_predictions([invalid])

    assert read_json(output) == original
    assert not temporary.exists()


def test_saved_predictions_have_required_fields_and_valid_probabilities():
    predictions = read_json(PREDICTIONS_PATH)
    assert predictions, "matches.jsonが空です"

    required = {
        "id",
        "league_id",
        "kickoff",
        "home_team",
        "away_team",
        "home_win_probability",
        "draw_probability",
        "away_win_probability",
        "data_quality",
        "model_version",
    }

    for item in predictions:
        assert required <= item.keys()
        assert item["data_quality"] in {
            "full_history",
            "second_division_history",
            "estimated",
        }
        assert re.fullmatch(r"fd-\d+", item["home_team"]["id"])
        assert re.fullmatch(r"fd-\d+", item["away_team"]["id"])
        probability_sum = sum(
            [
                item["home_win_probability"],
                item["draw_probability"],
                item["away_win_probability"],
            ]
        )
        assert probability_sum == pytest.approx(100.0, abs=0.2)


def test_completed_matches_empty_list_is_valid_state(monkeypatch):
    monkeypatch.setattr(ds, "get_completed_matches", lambda: [])
    assert ds.get_completed_matches() == []
    perf = ds.get_completed_performance()
    assert perf["total_predictions"] == 0
    assert perf["correct_predictions"] == 0
    assert perf["incorrect_predictions"] == 0
    assert perf["accuracy"] == 0.0


def test_completed_performance_zero_total_is_safe_and_non_negative(monkeypatch):
    monkeypatch.setattr(
        ds,
        "get_completed_matches",
        lambda: [
            {"prediction_status": "recorded", "is_correct": False},
            {"prediction_status": "recorded", "is_correct": False},
        ],
    )
    perf = ds.get_completed_performance()
    assert perf["total_predictions"] == 2
    assert perf["correct_predictions"] == 0
    assert perf["incorrect_predictions"] == 2
    assert perf["accuracy"] == pytest.approx(0.0)
    assert np.isfinite(float(perf["accuracy"]))


def test_saved_predictions_are_one_matchday_per_league():
    fixtures = read_json(FIXTURES_PATH)
    predictions = read_json(PREDICTIONS_PATH)
    matchday_by_id = {
        str(item["id"]): item.get("matchday")
        for item in fixtures
    }

    league_matchdays: dict[str, set[int]] = {}
    for prediction in predictions:
        matchday = matchday_by_id.get(str(prediction["id"]))
        assert matchday is not None
        league_matchdays.setdefault(prediction["league_id"], set()).add(int(matchday))

    assert set(league_matchdays) == {
        "pl",
        "laliga",
        "seriea",
        "bundesliga",
        "ligue1",
    }
    assert all(len(matchdays) == 1 for matchdays in league_matchdays.values())



def test_saved_predictions_have_valid_shap_explanations():
    predictions = read_json(PREDICTIONS_PATH)
    assert len(predictions) == 48
    required = {"feature", "label", "value", "shap_value", "impact", "target", "text"}
    for item in predictions:
        explanations = item.get("explanations")
        assert isinstance(explanations, list)
        assert 1 <= len(explanations) <= 5
        assert item.get("explanation_method") == "SHAP TreeExplainer"
        for explanation in explanations:
            assert required <= explanation.keys()
            assert isinstance(explanation["shap_value"], (int, float))
            assert np.isfinite(float(explanation["shap_value"]))
            assert explanation["impact"] in {"supports", "opposes"}
            assert explanation["target"] == item["predicted_result"]


def test_class_shap_vector_supports_current_multiclass_shape(prediction_module):
    values = np.arange(12, dtype=float).reshape(1, 4, 3)
    actual = prediction_module.class_shap_vector(values, class_index=2, feature_count=4)
    np.testing.assert_array_equal(actual, values[0, :, 2])


def test_class_shap_vector_supports_legacy_list_shape(prediction_module):
    values = [np.arange(4, dtype=float).reshape(1, 4) + 10 * index for index in range(3)]
    actual = prediction_module.class_shap_vector(values, class_index=1, feature_count=4)
    np.testing.assert_array_equal(actual, values[1][0])


def test_build_shap_explanations_returns_empty_without_context(prediction_module):
    frame = pd.DataFrame([{"home_recent_points": 1.4, "away_recent_points": 1.0}])
    assert prediction_module.build_shap_explanations(
        None, frame, frame.iloc[0].to_dict(), 0, "Home Win"
    ) == []


def test_prediction_json_does_not_contain_api_credentials():
    raw = PREDICTIONS_PATH.read_text(encoding="utf-8")
    forbidden = {"FOOTBALL_DATA_API_KEY", "API_FOOTBALL_KEY", "x-apisports-key", "X-Auth-Token"}
    assert all(token not in raw for token in forbidden)


def test_extra_fixtures_have_valid_schema_and_no_duplicate_ids():
    events = read_json(EXTRA_FIXTURES_PATH)
    assert events
    required = {"id", "source", "competition_name", "competition_type", "kickoff", "team_ids", "data_quality"}
    ids = []
    for event in events:
        assert required <= event.keys()
        assert event["competition_type"] in {"european", "domestic_cup", "other", "unknown"}
        assert isinstance(event["team_ids"], list)
        assert pd.notna(pd.to_datetime(event["kickoff"], utc=True, errors="coerce"))
        ids.append(event["id"])
    assert len(ids) == len(set(ids))


def test_unknown_competition_is_not_classified_as_domestic_cup(extra_fixture_module):
    assert extra_fixture_module.classify_competition("Unregistered Invitational") == "unknown"
    assert extra_fixture_module.classify_competition("English Premier League") == "league"
    assert extra_fixture_module.classify_competition("UEFA Champions League") == "european"
    assert extra_fixture_module.classify_competition("FA Cup") == "domestic_cup"


def test_extra_competition_context_counts_only_matches_before_kickoff(prediction_module):
    events = [
        {"kickoff": "2026-08-18T20:00:00Z", "team_ids": ["fd-57"], "competition_type": "european", "competition_name": "UEFA Champions League", "source": "football-data.org", "had_extra_time_or_penalties": False},
        {"kickoff": "2026-08-22T20:00:00Z", "team_ids": ["fd-57"], "competition_type": "european", "competition_name": "UEFA Champions League", "source": "football-data.org", "had_extra_time_or_penalties": False},
    ]
    context = prediction_module.extra_competition_context(
        events, "fd-57", pd.Timestamp("2026-08-21T19:00:00Z"),
        {"last7": 1, "last14": 2, "days": 6},
        {"success": True, "coverage": {"champions_league": "available", "other_european_and_domestic_cups": "partial_last_event_only", "extra_time_and_penalties": "partial"}},
    )
    assert context["extra_matches_last_7d"] == 1
    assert context["extra_matches_last_14d"] == 1
    assert context["last7"] == 2
    assert context["last14"] == 3
    assert context["days"] == 2
    assert context["after_european"] is True


def test_domestic_cup_context_sets_flag(prediction_module):
    context = prediction_module.extra_competition_context(
        [{"kickoff": "2026-08-19T20:00:00Z", "team_ids": ["fd-57"], "competition_type": "domestic_cup", "competition_name": "FA Cup", "source": "TheSportsDB", "had_extra_time_or_penalties": False}],
        "fd-57", pd.Timestamp("2026-08-21T19:00:00Z"),
        {"last7": 0, "last14": 1, "days": 8},
        {"success": True, "coverage": {}},
    )
    assert context["after_domestic_cup"] is True
    assert context["after_european"] is False


def test_no_extra_data_uses_league_only_status(prediction_module):
    context = prediction_module.extra_competition_context(
        [], "fd-57", pd.Timestamp("2026-08-21T19:00:00Z"),
        {"last7": 1, "last14": 2, "days": 6}, {},
    )
    assert context["last7"] == 1
    assert context["last14"] == 2
    assert context["days"] == 6
    assert context["official_matches_data_completeness"] == "league_only"


def test_fatigue_payload_is_bounded_and_preserves_data_status(prediction_module):
    context = {
        "last7": 8, "last14": 10, "days": 1,
        "after_european": True, "after_domestic_cup": True,
        "had_extra_time_or_penalties": True,
        "extra_matches_last_7d": 3, "extra_matches_last_14d": 4,
        "last_extra_competition": "UEFA Champions League",
        "last_extra_match_source": "football-data.org",
        "european_data_status": "available",
        "domestic_cup_data_status": "partial_last_event_only",
        "extra_time_data_status": "partial",
        "official_matches_data_completeness": "league_and_champions_league_with_partial_cup_supplement",
    }
    payload = prediction_module.fatigue_payload({"last7": 0, "last14": 0, "days": 14}, context)
    assert payload["index"] == 100
    assert payload["level"] == "High"
    assert payload["european_competition_data_status"] == "available"
    assert payload["domestic_cup_data_status"] == "partial_last_event_only"


def test_saved_prediction_fatigue_payloads_are_valid():
    predictions = read_json(PREDICTIONS_PATH)
    for item in predictions:
        for side in ("home_fatigue", "away_fatigue"):
            fatigue = item[side]
            assert 0 <= fatigue["index"] <= 100
            assert fatigue["level"] in {"Low", "Medium", "High"}
            assert fatigue["matches_last_7d"] >= fatigue.get("extra_matches_last_7d", 0)
            assert fatigue["matches_last_14d"] >= fatigue["matches_last_7d"]
            assert fatigue["days_since_last_match"] >= 1
            assert fatigue.get("official_matches_data_completeness") in {
                "league_only",
                "league_and_champions_league_with_partial_cup_supplement",
            }


def test_predictor_maps_probabilities_by_model_class(monkeypatch, tmp_path):
    from ml import predict

    class FakeModel:
        classes_ = np.array([2, 0, 1])

        def predict_proba(self, X):
            assert list(X.columns) == ["feature_a"]
            return np.array([[0.2, 0.5, 0.3]])

    model_path = tmp_path / "lightgbm_model.joblib"
    metadata_path = tmp_path / "lightgbm_metadata.json"
    model_path.write_bytes(b"placeholder")
    metadata_path.write_text(
        json.dumps({"features": ["feature_a"], "version": "test-v1"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(predict, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(predict.joblib, "load", lambda path: FakeModel())

    result = predict.Predictor().predict_features({"feature_a": 123})

    assert result["home_win_probability"] == 0.5
    assert result["draw_probability"] == 0.3
    assert result["away_win_probability"] == 0.2
    assert result["predicted_result"] == "HOME_WIN"



def _timeline_feature_matches():
    frame = pd.DataFrame(
        [
            {"Date": "2026-09-01", "HomeTeam": "A", "AwayTeam": "B", "FTHG": 2, "FTAG": 0, "FTR": "H"},
            {"Date": "2026-09-01", "HomeTeam": "C", "AwayTeam": "D", "FTHG": 0, "FTAG": 1, "FTR": "A"},
            {"Date": "2026-09-02", "HomeTeam": "A", "AwayTeam": "C", "FTHG": 5, "FTAG": 0, "FTR": "H"},
            {"Date": "2026-09-02", "HomeTeam": "D", "AwayTeam": "A", "FTHG": 0, "FTAG": 1, "FTR": "A"},
            {"Date": "2026-09-03", "HomeTeam": "A", "AwayTeam": "D", "FTHG": 1, "FTAG": 0, "FTR": "H"},
        ]
    )
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame


def test_training_features_are_independent_of_same_day_row_order():
    from ml.features import build_features

    matches = _timeline_feature_matches()
    reordered = pd.concat(
        [group.iloc[::-1] for _, group in matches.groupby("Date", sort=False)],
        ignore_index=True,
    )
    original = build_features(matches, window=1).sort_values(
        ["Date", "HomeTeam", "AwayTeam"]
    ).reset_index(drop=True)
    changed_order = build_features(reordered, window=1).sort_values(
        ["Date", "HomeTeam", "AwayTeam"]
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(original, changed_order)


def test_same_day_result_is_not_used_by_another_same_day_match():
    from ml.features import build_features

    features = build_features(_timeline_feature_matches(), window=1)
    same_day_match = features[
        (features["Date"] == pd.Timestamp("2026-09-02"))
        & (features["AwayTeam"] == "A")
    ].iloc[0]
    assert same_day_match["away_recent_gf"] == 2
    assert same_day_match["away_recent_points"] == 3
    assert same_day_match["away_history_count"] == 1


def test_previous_day_result_is_used_by_later_match():
    from ml.features import build_features

    features = build_features(_timeline_feature_matches(), window=1)
    next_day_match = features[
        features["Date"] == pd.Timestamp("2026-09-03")
    ].iloc[0]
    assert next_day_match["home_recent_gf"] == 1
    assert next_day_match["home_recent_ga"] == 0
    assert next_day_match["home_recent_points"] == 3
    assert next_day_match["home_history_count"] == 1


def test_match_does_not_use_its_own_result_as_history():
    from ml.features import build_features

    matches = pd.DataFrame(
        [
            {"Date": "2026-09-01", "HomeTeam": "A", "AwayTeam": "B", "FTHG": 1, "FTAG": 0, "FTR": "H"},
            {"Date": "2026-09-02", "HomeTeam": "A", "AwayTeam": "B", "FTHG": 9, "FTAG": 8, "FTR": "H"},
        ]
    )
    matches["Date"] = pd.to_datetime(matches["Date"])
    second_match = build_features(matches, window=1).iloc[0]
    assert second_match["home_recent_gf"] == 1
    assert second_match["away_recent_gf"] == 0
    assert second_match["home_history_count"] == 1
    assert second_match["away_history_count"] == 1
