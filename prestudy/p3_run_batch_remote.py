"""
Полный прогон абляции RelAgent на удалённом сервере (94 ГБ RAM, 18 CPU, без GPU).
Данные и venv на /var/essdata (сетевой FS, места много) -- локальный диск сервера
почти полон (430 МБ), туда не пишем вообще ничего, кроме символических путей.

OpenRouter доступен только через SOCKS5-прокси (LLM_PROXY) -- передаём его
дочерним процессам как HTTPS_PROXY/HTTP_PROXY, которые читает httpx внутри litellm.
"""
import json
import os
import subprocess
import sys
import time
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/var/essdata/s_chumakov/prestudy_p3")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "p2_repos" / "RelAgent" / "src"))
# Важно: не только для дочерних RelAgent-процессов (через _ENV_BASE ниже), но и
# для самого драйвера -- check_program()/get_time_cols() дёргают relbench в ЭТОМ
# процессе напрямую, без этого лезли за датасетом в сеть и падали по таймауту.
os.environ["RELBENCH_CACHE_DIR"] = str(ROOT / "relbench_cache")

VENV_PY = str(ROOT / ".venv" / "bin" / "python")
MODEL = "openrouter/deepseek/deepseek-v4-flash-0731"
DATASET = "rel-stack"
TASK = "user-engagement"
MAX_TURNS = 20
TEMPERATURE = 0.7
N_REPEATS_PER_CONDITION = {"protect": 8, "noprotect": 16}  # protect держим на 8
                # (уже готовы, новых не запускаем), noprotect расширяем до 16 --
                # интереснее увидеть больше noprotect раньше. Остаток 9-50 обоих
                # условий -- прогнать позже, подняв оба числа.
MAX_CONCURRENT = int(os.environ.get("P3_MAX_CONCURRENT", "6"))
ORACLE_SAMPLE = 20
# Жёсткий потолок на прогон, чтобы 100 повторов гарантированно уложились в сутки.
# 1800с оказалось мало -- прогоны обрубались на 2-6 трайлах вместо обычных 20-34.
# max_turns=20 и step_timeout=900s это не ограничивают (шаг может длиться часами
# без единой ошибки) -- это внешний потолок поверх них. При параллелизме 6 и
# 100 повторах потолок 3600с даёт максимум ~17ч в худшем случае -- укладываемся
# в сутки, но даём агенту реально доработать до сходимости.
RUN_TIMEOUT_SECONDS = 3600

CONDITIONS = {
    "protect": ROOT / "p2_repos" / "RelAgent",
    "noprotect": ROOT / "p2_repos" / "RelAgent_noprotect",
}

RESULTS_PATH = ROOT / "p3_out" / "full" / "results.jsonl"
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

# ВАЖНО: считать один раз при старте модуля, а не на каждый check_program().
# get_time_cols() тянет get_dataset(...).get_db() -- полную загрузку rel-stack
# (сотни МБ parquet в pandas) в память ДРАЙВЕРА. Раньше вызывался при каждой
# проверке оракулом -> RSS драйвера разрастался безгранично (утечка, дошло до
# 13.6ГБ после 5 проверок) и параллельно душило GIL так, что остальные 5 из 6
# воркеров зависали внутри этого вызова вместо запуска новых прогонов.
import duckdb  # noqa: E402
from relagent.scientist.validation import _run_feature_queries  # noqa: E402
from p3_sql_oracle import SqlDiffExecOracle, get_time_cols  # noqa: E402

_TIME_COLS = get_time_cols(DATASET)

_ENV_BASE = dict(os.environ)
_ENV_BASE["HTTPS_PROXY"] = os.environ["LLM_PROXY"]
_ENV_BASE["HTTP_PROXY"] = os.environ["LLM_PROXY"]
_ENV_BASE["RELBENCH_CACHE_DIR"] = str(ROOT / "relbench_cache")
_ENV_BASE["PYTHONPATH"] = "src"
_ENV_BASE.setdefault("USER", "s_chumakov")


def already_done(artifact_dir: Path) -> bool:
    if any(artifact_dir.glob("*/best_program.json")):
        return True
    for trials_path in artifact_dir.glob("*/trials.jsonl"):
        for line in trials_path.read_text().splitlines():
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            if t.get("error") is None and t.get("primary_score") not in (None, float("-inf")):
                return True
    return False


def run_one(condition: str, idx: int) -> dict:
    relagent_dir = CONDITIONS[condition]
    task_id = f"{condition}_{idx:03d}"
    artifact_dir = ROOT / "p3_out" / "full" / condition / f"run_{idx:03d}"
    scratch_dir = ROOT / "p3_scratch" / task_id

    if already_done(artifact_dir):
        return load_existing_result(condition, idx, artifact_dir, scratch_dir)

    scratch_dir.mkdir(parents=True, exist_ok=True)
    env = dict(_ENV_BASE)
    env["SCRATCH_DIR"] = str(scratch_dir)
    log_path = artifact_dir.parent / f"{task_id}.log"
    artifact_dir.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    timed_out = False
    with open(log_path, "w") as logf:
        try:
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
                timeout=RUN_TIMEOUT_SECONDS,
            )
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = "timeout"
    dt = time.time() - t0

    result = load_existing_result(condition, idx, artifact_dir, scratch_dir,
                                   exit_code=exit_code, wall_seconds=dt)
    if timed_out:
        result["timed_out"] = True
    shutil.rmtree(scratch_dir, ignore_errors=True)
    return result


def load_existing_result(condition, idx, artifact_dir, scratch_dir,
                          exit_code=None, wall_seconds=None) -> dict:
    run_subdirs = list(artifact_dir.glob("*")) if artifact_dir.exists() else []
    if not run_subdirs:
        return {"condition": condition, "idx": idx, "status": "no_artifacts",
                "exit_code": exit_code, "wall_seconds": wall_seconds}
    run_dir = sorted(run_subdirs)[-1]
    bp_path = run_dir / "best_program.json"
    summary_path = run_dir / "summary.md"
    trials_path = run_dir / "trials.jsonl"
    source = "best_program.json"

    if bp_path.exists():
        program = json.loads(bp_path.read_text())
        feature_queries = program.get("feature_queries", [])
    elif trials_path.exists():
        # Прогон убит по таймауту до финального save_best_program() (пишется
        # только в конце run()). trials.jsonl пишется построчно после каждого
        # трайла (log_trial открывает файл в режиме "a") -- переживает kill -9.
        # Берём лучший валидный (error is None) трайл как суррогат "программы".
        best_trial = None
        for line in trials_path.read_text().splitlines():
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            if t.get("error") is not None:
                continue
            score = t.get("primary_score")
            if score is None or score == float("-inf"):
                continue
            if best_trial is None or score > best_trial.get("primary_score", float("-inf")):
                best_trial = t
        if best_trial is None:
            return {"condition": condition, "idx": idx, "status": "no_valid_trial",
                     "exit_code": exit_code, "wall_seconds": wall_seconds,
                     "run_dir": str(run_dir)}
        feature_queries = best_trial.get("feature_queries", [])
        source = "trials.jsonl_fallback"
    else:
        return {"condition": condition, "idx": idx, "status": "no_best_program",
                "exit_code": exit_code, "wall_seconds": wall_seconds,
                "run_dir": str(run_dir)}

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
    elif trials_path.exists():
        n_trials = sum(1 for _ in trials_path.read_text().splitlines())

    db_files = list(scratch_dir.glob("*/artifacts/*.duckdb")) if scratch_dir.exists() else []
    oracle_verdict, oracle_detail = "no_db_found", {}
    trial_verdicts = []
    if db_files and feature_queries:
        try:
            oracle_verdict, oracle_detail = check_program(db_files[0], feature_queries)
        except Exception as e:
            oracle_verdict, oracle_detail = "oracle_error", {"error": str(e)[:300]}
        # Проверяем оракулом КАЖДЫЙ трайл, не только выбранный "лучший" -- иначе
        # не увидим, на каком трайле впервые появляется утечка (см. обсуждение:
        # выбор "лучшего по score" может систематически отбирать именно утёкшие
        # варианты, если утечка завышает validation score).
        if trials_path.exists():
            try:
                trial_verdicts = check_all_trials(db_files[0], trials_path)
            except Exception as e:
                trial_verdicts = [{"error": f"check_all_trials_failed: {str(e)[:200]}"}]

    return {
        "condition": condition, "idx": idx, "status": "ok", "program_source": source,
        "exit_code": exit_code, "wall_seconds": wall_seconds,
        "run_dir": str(run_dir), "n_trials": n_trials, "best_score": best_score,
        "n_feature_queries": len(feature_queries),
        "oracle_verdict": oracle_verdict, "oracle_detail": oracle_detail,
        "trial_verdicts": trial_verdicts,
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


def check_all_trials(db_path: Path, trials_path: Path) -> list:
    con = duckdb.connect(str(db_path), read_only=False)
    eval_df = con.execute(
        f'SELECT "OwnerUserId", "timestamp" FROM train_table USING SAMPLE {ORACLE_SAMPLE}'
    ).df()
    oracle = SqlDiffExecOracle(
        con, _TIME_COLS, _run_feature_queries,
        entity_col="OwnerUserId", time_col="timestamp", sql_timeout_seconds=45,
    )
    results = []
    for line in trials_path.read_text().splitlines():
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        fq = t.get("feature_queries")
        if not fq:
            continue
        try:
            r = oracle.check_sample(fq, eval_df, n_sample=ORACLE_SAMPLE, seed=0)
            verdict, detail = r["verdict"], r["n_leak_rows"]
        except Exception as e:
            verdict, detail = "oracle_error", str(e)[:200]
        results.append({
            "trial_id": t.get("trial_id"), "primary_score": t.get("primary_score"),
            "verdict": verdict, "n_leak_rows_or_error": detail,
        })
    con.close()
    return results


def main():
    tasks = [(cond, i) for cond, n in N_REPEATS_PER_CONDITION.items() for i in range(1, n + 1)]
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
                  f"oracle={res.get('oracle_verdict')} wall_s={res.get('wall_seconds')}", flush=True)


if __name__ == "__main__":
    main()
