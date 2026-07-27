from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
LOG_DIR = ROOT / "logs"


def run_step(label: str, script_name: str, log_file) -> None:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"必要なスクリプトがありません: {script_path}")

    command = [sys.executable, str(script_path)]
    heading = f"\n{'=' * 72}\n{label}\n実行: {' '.join(command)}\n{'=' * 72}\n"
    print(heading, flush=True)
    log_file.write(heading)
    log_file.flush()

    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"

    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=child_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        log_file.write(line)

    return_code = process.wait()
    log_file.flush()

    if return_code != 0:
        raise RuntimeError(
            f"{label}に失敗しました。終了コード: {return_code}"
        )

    success = f"{label}: 完了\n"
    print(success, flush=True)
    log_file.write(success)
    log_file.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "順位表・日程、ランキング、追加大会、予測、モデル評価、データ状態を順番に更新します。"
        )
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="API取得を省略し、予測・モデル評価・データ状態だけ更新します。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"update_all_{timestamp}.log"

    steps = []
    if not args.skip_fetch:
        steps.extend(
            [
                ("1/6 順位表・日程の取得", "fetch_football_data_org.py"),
                ("2/6 選手ランキングの取得", "fetch_football_data_rankings.py"),
                ("3/6 欧州大会・カップ戦補完の取得", "fetch_extra_competition_fixtures.py"),
            ]
        )
    steps.extend(
        [
            ("4/6 次節予測・SHAP・疲労指数の生成", "generate_real_predictions.py"),
            ("5/6 モデル評価データの更新", "update_model_performance.py"),
            ("6/6 データ状態の更新", "update_data_status.py"),
        ]
    )
    started_at = datetime.now()
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(f"開始日時: {started_at.isoformat()}\n")
            for label, script_name in steps:
                run_step(label, script_name, log_file)

            finished_at = datetime.now()
            elapsed = (finished_at - started_at).total_seconds()
            summary = (
                f"\n全処理が正常に完了しました。\n"
                f"所要時間: {elapsed:.1f}秒\n"
                f"ログ: {log_path}\n"
            )
            print(summary)
            log_file.write(summary)

    except Exception as error:
        failure = (
            f"\n更新処理を中止しました。\n"
            f"原因: {error}\n"
            f"ログ: {log_path}\n"
        )
        print(failure, file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
