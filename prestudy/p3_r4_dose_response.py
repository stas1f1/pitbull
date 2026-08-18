"""
PRESTUDY2_runbook.md R4 -- дозозависимость защиты. Тот же нейтральный промпт
(G0, уже измерен в p3_baseline_run.py), плюс два новых уровня добавленной
инструкции -- G1 (общее упоминание) и G2 (по образцу RelAgent: фильтр у
КАЖДОЙ агрегации + явный запрет подставлять свою дату создания как границу).
Всё остальное идентично G0: те же 2 модели, та же задача, тот же оракул
(TEST_SEEDS), температура 0.7, чистый контекст на каждую генерацию.

n=30 на ячейку, 2 модели x 2 новых уровня = 120 генераций.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import p3_baseline_run as bl  # noqa: E402

N_REPEATS = 30
MAX_CONCURRENT = 8

G1_ADDENDUM = """

Признаки должны рассчитываться на момент предсказания seed_time."""

G2_ADDENDUM = """

Каждая агрегация по любой связанной таблице ОБЯЗАНА включать временной фильтр,
отсекающий события после seed_time (например, событие учитывается только если
его собственная дата/время < seed_time), чтобы не использовать будущие данные.
Накопленное число релевантных событий ДО seed_time часто самый сильный
предиктор. Всегда используй seed_time как временную границу для ВСЕХ
агрегаций -- никогда не используй в качестве границы дату создания самой
сущности (product_id) или любую другую дату, отличную от seed_time."""

LEVELS = {
    "G1": bl.NEUTRAL_PROMPT + G1_ADDENDUM,
    "G2": bl.NEUTRAL_PROMPT + G2_ADDENDUM,
}

OUT_PATH = Path("p3_out/baseline/r4_dose_response.jsonl")


def run_one_level(level: str, tier: str, model_id: str, idx: int) -> dict:
    r = bl.run_one(tier, model_id, idx, prompt=LEVELS[level])
    r["level"] = level
    return r


def main():
    done = set()
    if OUT_PATH.exists():
        for line in OUT_PATH.read_text().splitlines():
            try:
                r = json.loads(line)
                done.add((r["level"], r["tier"], r["idx"]))
            except Exception:
                pass

    tasks = [(level, tier, model_id, idx)
             for level in LEVELS
             for tier, model_id in bl.MODELS.items()
             for idx in range(1, N_REPEATS + 1)
             if (level, tier, idx) not in done]
    print(f"всего задач: {len(tasks)}", flush=True)

    with OUT_PATH.open("a") as out, ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
        futures = {pool.submit(run_one_level, level, tier, model_id, idx): (level, tier, idx)
                   for level, tier, model_id, idx in tasks}
        for fut in as_completed(futures):
            level, tier, idx = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"level": level, "tier": tier, "idx": idx, "status": "driver_error", "error": str(e)[:300]}
            out.write(json.dumps(res, default=str) + "\n")
            out.flush()
            print(f"[{level} {tier:12s} {idx:02d}] status={res.get('status')} "
                  f"verdict={res.get('verdict')}", flush=True)


if __name__ == "__main__":
    main()
