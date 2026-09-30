# A7 — технический черновик RQ0 на RelBench

## Статус

Не является основным результатом A7. Эксперимент заблокирован A6: требуемая
per-column карта ещё не получила два независимых человеческих голоса.

## Локальная инвентаризация

Для проверки исполнимости использована временная
`pilot/a6/provisional_operational_map.csv`, явно помеченная как AI-assisted и
не считающаяся человеческой разметкой. На development-моментах найдено пять
программ с воспроизводимым witness:

- три программы rel-event;
- две программы rel-stack.

`stack_user-engagement.sql` исключена: текущая схема rel-stack не содержит
`AcceptedAnswerId`, поэтому программа завершается BinderException на всех трёх
development-моментах и не даёт воспроизводимого witness.

Машинный manifest находится в `pilot/a7_provisional_manifest.json`: `M=5`,
`status=technical_draft_a6_not_adjudicated`,
`publishable_as_primary_a7=false`. Модельный ремонт намеренно не считается
результатом A7 и должен быть перезапущен после adjudication A6.
