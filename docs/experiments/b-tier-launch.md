# Tier B — журнал запуска

Дата запуска: 27 сентября 2026 года.

## Состояние gate

| Шаг | Состояние | Следующее условие |
|---|---|---|
| B1 | provisional complete | human validation заменена AI-assisted: heuristic exact 94.4%, LLM 80.4%; «LLM не хуже» не подтверждено |
| B2 | running | карта B1 собрана; восстанавливается повреждённый rel-amazon review.parquet перед локальной инвентаризацией |
| B3 | выполнен агентом, требуется авторское принятие | 324/324 вызова, 0 API-ошибок; основной F0.5: recall 90.7%, FPR 38.7%, порог не пройден |
| B4 | running | завершить пять RelBench-баз и объединить с Olist; rel-f1 уже 9/9 canary, 0/3 negative controls; rel-stack smoke 1/2 canary, 0/2 controls |
| B5 | выполнен агентом, требуется авторское принятие | принять строку runtime rel-amazon |
| B6 | in review | 10/16 отобраны и обёрнуты; 9/10 smoke-call успешны; ручной stopwatch не был запущен |
| B7 | provisional complete | 2 независимых LLM-рецензента × 20 слепых случаев; внешний человеческий критерий не выполнен |

## Запущенные артефакты

- B3: `pilot/b3_manifest.json`, `pilot/b3_fetch.py`, `pilot/b3_score.py`,
  `pilot/b3_results.json`, `docs/experiments/b3-rq2a-prompt-robustness.md`.
- B4: `pilot/b4_canary_sql.py`, `pilot/b4_download_relbench.py`,
  `pilot/b4_f1_canary.json`.
- B5: `pilot/b5_results.json`, `docs/experiments/b5-rel-amazon-cost.md`.
- B6: `pilot/b6_candidates.csv`, `pilot/b6_results.json`, адаптеры в
  `pilot/b6_wrappers/`, отчёты `docs/experiments/b6-real-code-protocol.md` и
  `docs/experiments/b6-real-code-funnel.md`.
- B7: `pilot/b7/manifest.json`, слепые case-пакеты и две заполненные proxy-формы.
- B7 result: `pilot/b7/results.json`, заполненные формы `reviewer_1.csv` и
  `reviewer_2.csv`, отчёт `docs/experiments/b7-ai-assisted-repair-assessment.md`.

В B3 код не исполнялся внешней моделью, но текст feature-программ входил в
prompt. Вызовы выполнены после отдельного явного разрешения пользователя.
