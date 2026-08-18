"""
Полный прогон абляции RelAgent: 50 повторов x 2 условия (с защитой / без).
Параллелизм 2 (безопасно по памяти, см. пилот). Каждый повтор — изолированный
SCRATCH_DIR, чтобы не путать DuckDB-файлы конкурентных процессов и не раздуть
диск (после каждого прогона: оракул на его best_program.json -> сразу удалить
его 2+ГБ DuckDB-файл).

Устойчиво к падениям процесса (ненулевой код выхода не значит "нет данных" —
RelAgent делает best-effort save до финального re-raise, см. пилот). Идемпотентно:
уже готовые повторы (есть best_program.json) пропускаются, можно перезапускать.
"""
import json
import os
import subprocess
import sys
import time
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, "p2_repos/RelAgent/src")
import duckdb
from relagent.scientist.validation import _run_feature_queries
from p3_sql_oracle import SqlDiffExecOracle, get_time_cols

ROOT = Path("/home/stas/Documents/GitHub/prestudy/prestudy")
VENV_PY = str(ROOT / ".venv" / "bin" / "python")
MODEL = "openrouter/deepseek/deepseek-v4-flash-0731"
DATASET = "rel-stack"
TASK = "user-engagement"
MAX_TURNS = 20
TEMPERATURE = 0.7
N_REPEATS = 50
MAX_CONCURRENT = 1
ORACLE_SAMPLE = 20

CONDITIONS = {
    "protect": ROOT / "p2_repos" / "RelAgent",
    "noprotect": ROOT / "p2_repos" / "RelAgent_noprotect",
}

RESULTS_PATH = ROOT / "p3_out" / "full" / "results.jsonl"
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
_TIME_COLS = get_time_cols(DATASET)


def already_done(artifact_dir: Path) -> bool:
    return any((artifact_dir).glob("*/best_program.json"))


def run_one(condition: str, idx: int) -> dict:
    relagent_dir = CONDITIONS[condition]
    task_id = f"{condition}_{idx:03d}"
    artifact_dir = ROOT / "p3_out" / "full" / condition / f"run_{idx:03d}"
    scratch_dir = ROOT / "p3_scratch" / task_id

    if already_done(artifact_dir):
        return load_existing_result(condition, idx, artifact_dir, scratch_dir)

    scratch_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["SCRATCH_DIR"] = str(scratch_dir)
    env["PYTHONPATH"] = "src"
    env.setdefault("USER", "stas")
    log_path = artifact_dir.parent / f"{task_id}.log"
    artifact_dir.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    with open(log_path, "w") as logf:
        proc = subprocess.run(
            [VENV_PY, "src/relagent/main.py",
             "--dataset", DATASET, "--task", TASK,
             "--model", MODEL,
             "--max_turns", str(MAX_TURNS),
             "--temperature", str(TEMPERATURE),
             "--artifact_dir", str(artifact_dir),
             "--log_level", "INFO"],
            cwd=str(relagent_dir), env=env,
            stdout=logf, stderr=subprocess.STDOUT,
        )
    dt = time.time() - t0

    result = load_existing_result(condition, idx, artifact_dir, scratch_dir,
                                   exit_code=proc.returncode, wall_seconds=dt)

    # DuckDB-файл этого повтора больше не нужен — освобождаем диск сразу.
    shutil.rmtree(scratch_dir, ignore_errors=True)
    return result


def load_existing_result(condition, idx, artifact_dir, scratch_dir,
                          exit_code=None, wall_seconds=None) -> dict:
    run_subdirs = list(artifact_dir.glob("*"))
    if not run_subdirs:
        return {"condition": condition, "idx": idx, "status": "no_artifacts",
                "exit_code": exit_code, "wall_seconds": wall_seconds}
    run_dir = sorted(run_subdirs)[-1]
    bp_path = run_dir / "best_program.json"
    summary_path = run_dir / "summary.md"
    if not bp_path.exists():
        return {"condition": condition, "idx": idx, "status": "no_best_program",
                "exit_code": exit_code, "wall_seconds": wall_seconds,
                "run_dir": str(run_dir)}

    program = json.loads(bp_path.read_text())
    feature_queries = program.get("feature_queries", [])
    n_trials, best_score = None, None
    if summary_path.exists():
        for line in summary_path.read_text().splitlines():
            if line.startswith("- Total trials:"):
                n_trials = int(line.split(":")[1].strip())
            if line.startswith("- Best score:"):
                try:
                    best_score = float(line.split(":")[1].strip())
                except ValueError:
                    pass

    db_files = list(scratch_dir.glob("*/artifacts/*.duckdb")) if scratch_dir.exists() else []
    oracle_verdict, oracle_detail = "no_db_found", {}
    if db_files and feature_queries:
        try:
            oracle_verdict, oracle_detail = check_program(db_files[0], feature_queries)
        except Exception as e:
            oracle_verdict, oracle_detail = "oracle_error", {"error": str(e)[:300]}

    return {
        "condition": condition, "idx": idx, "status": "ok",
        "exit_code": exit_code, "wall_seconds": wall_seconds,
        "run_dir": str(run_dir), "n_trials": n_trials, "best_score": best_score,
        "n_feature_queries": len(feature_queries),
        "oracle_verdict": oracle_verdict, "oracle_detail": oracle_detail,
    }


def check_program(db_path: Path, feature_queries) -> tuple:
    con = duckdb.connect(str(db_path), read_only=False)
    eval_df = con.execute(
        f'SELECT "OwnerUserId", "timestamp" FROM train_table USING SAMPLE {ORACLE_SAMPLE}'
    ).df()
    oracle = SqlDiffExecOracle(
        con, _TIME_COLS, _run_feature_queries,
        entity_col="OwnerUserId", time_col="timestamp", sql_timeout_seconds=45,
    )
    r = oracle.check_sample(feature_queries, eval_df, n_sample=ORACLE_SAMPLE, seed=0)
    con.close()
    return r["verdict"], {k: v for k, v in r.items() if k != "row_results"}


def main():
    tasks = [(cond, i) for cond in CONDITIONS for i in range(1, N_REPEATS + 1)]
    done_already = 0
    with RESULTS_PATH.open("a") as out, ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
        futures = {pool.submit(run_one, cond, i): (cond, i) for cond, i in tasks}
        for fut in as_completed(futures):
            cond, i = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"condition": cond, "idx": i, "status": "driver_error", "error": str(e)[:300]}
            out.write(json.dumps(res) + "\n")
            out.flush()
            print(f"[{cond} {i:03d}] status={res.get('status')} "
                  f"trials={res.get('n_trials')} best={res.get('best_score')} "
                  f"oracle={res.get('oracle_verdict')} wall_s={res.get('wall_seconds')}")


if __name__ == "__main__":
    main()
