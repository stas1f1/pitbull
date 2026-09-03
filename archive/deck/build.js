const pptxgen = require("pptxgenjs");

const P = {
  navy:   "1E2761",
  deep:   "141B3D",
  ice:    "CADCFC",
  white:  "FFFFFF",
  paper:  "FFFFFF",
  tint:   "F1F4FB",
  gray:   "5B6478",
  dark:   "1B2233",
  green:  "1F7A55",
  greenL: "E3F3EC",
  amber:  "B57314",
  amberL: "FBF0DC",
  red:    "A62B22",
  redL:   "FAE7E5",
};

const HF = "Cambria";
const BF = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "AutoDS research review";
pres.title = "Agentic AutoML / AutoDS — перспективные направления";

const W = 13.3, H = 7.5;

// ---------- helpers ----------
function darkSlide() {
  const s = pres.addSlide();
  s.background = { color: P.deep };
  return s;
}
function lightSlide(title, kicker) {
  const s = pres.addSlide();
  s.background = { color: P.paper };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: 0.6, y: 0.36, w: 12.1, h: 0.26,
      fontFace: BF, fontSize: 11, bold: true, color: P.gray, charSpacing: 2, margin: 0,
    });
  }
  if (title) {
    s.addText(title, {
      x: 0.6, y: kicker ? 0.64 : 0.45, w: 10.4, h: 0.7,
      fontFace: HF, fontSize: 32, bold: true, color: P.navy, margin: 0, valign: "top",
    });
  }
  return s;
}
// verdict chip = repeated visual motif
function chip(s, x, y, kind) {
  const map = {
    green: [P.green, P.greenL, "СВОБОДНО"],
    amber: [P.amber, P.amberL, "ЧАСТИЧНО"],
    red:   [P.red,   P.redL,   "ЗАНЯТО"],
  };
  const [fg, bg, label] = map[kind];
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w: 1.5, h: 0.34, fill: { color: bg }, line: { color: fg, width: 1 }, rectRadius: 0.17,
  });
  s.addText(label, {
    x, y, w: 1.5, h: 0.34, align: "center", valign: "middle",
    fontFace: BF, fontSize: 10, bold: true, color: fg, charSpacing: 1, margin: 0,
  });
}
function proCon(s, x, y, w, kind, title, items) {
  const fg = kind === "pro" ? P.green : P.red;
  const bg = kind === "pro" ? P.greenL : P.redL;
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 0.36, fill: { color: bg }, line: { type: "none" }, rectRadius: 0.08,
  });
  s.addText(title, {
    x: x + 0.16, y, w: w - 0.3, h: 0.36, valign: "middle",
    fontFace: BF, fontSize: 12, bold: true, color: fg, margin: 0,
  });
  s.addText(
    items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i !== items.length - 1 } })),
    {
      x: x + 0.16, y: y + 0.46, w: w - 0.3, h: 2.5,
      fontFace: BF, fontSize: 11.5, color: P.dark, lineSpacing: 15,
      paraSpaceAfter: 5, margin: 0, valign: "top",
    }
  );
}
function statTile(s, x, y, w, big, label, accent) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 1.72, fill: { color: P.tint }, line: { type: "none" }, rectRadius: 0.1,
  });
  s.addText(big, {
    x: x + 0.18, y: y + 0.16, w: w - 0.36, h: 0.78,
    fontFace: HF, fontSize: 34, bold: true, color: accent || P.navy, margin: 0, valign: "middle",
  });
  s.addText(label, {
    x: x + 0.18, y: y + 0.92, w: w - 0.36, h: 0.68,
    fontFace: BF, fontSize: 11.5, color: P.gray, margin: 0, valign: "top", lineSpacing: 14,
  });
}
function footer(s, txt) {
  s.addText(txt, {
    x: 0.6, y: 6.95, w: 12.1, h: 0.3,
    fontFace: BF, fontSize: 9.5, color: "9AA1B1", italic: true, margin: 0,
  });
}

// ============ 1. TITLE ============
{
  const s = darkSlide();
  s.addShape(pres.ShapeType.roundRect, {
    x: 0.75, y: 1.5, w: 0.9, h: 0.9, fill: { color: P.ice }, line: { type: "none" }, rectRadius: 0.18,
  });
  s.addText("AI", {
    x: 0.75, y: 1.5, w: 0.9, h: 0.9, align: "center", valign: "middle",
    fontFace: HF, fontSize: 26, bold: true, color: P.deep, margin: 0,
  });
  s.addText("Agentic AutoML и AutoDS", {
    x: 0.75, y: 2.65, w: 11.5, h: 0.95,
    fontFace: HF, fontSize: 46, bold: true, color: P.white, margin: 0,
  });
  s.addText("Перспективные направления: аргументы за и против", {
    x: 0.75, y: 3.6, w: 11.5, h: 0.55,
    fontFace: BF, fontSize: 20, color: P.ice, margin: 0,
  });
  s.addText(
    "Обзор ~90 работ за 2024–2026 · по 14 направлениям проверили, что уже занято · цель — демо-трек ICDM 2026",
    { x: 0.75, y: 4.35, w: 11.5, h: 0.5, fontFace: BF, fontSize: 13.5, color: "8E9AC4", margin: 0 }
  );
  s.addShape(pres.ShapeType.line, {
    x: 0.78, y: 5.15, w: 2.2, h: 0, line: { color: P.ice, width: 2 },
  });
  s.addText("Август 2026", {
    x: 0.75, y: 5.35, w: 6, h: 0.35, fontFace: BF, fontSize: 12, color: "8E9AC4", margin: 0,
  });
  s.addNotes("Обзор области за 2025-2026 и ранжированный список направлений под демо-трек ICDM 2026.");
}

// ============ 2. РАМКА ============
{
  const s = lightSlide("Условия, в которых мы выбираем", "Ограничения");
  const y = 1.75;
  statTile(s, 0.6, y, 3.85, "14 дней", "Дедлайн ICDM 2026 Demo — 20 августа 2026, 23:59 AoE. Уведомление 20 сентября.", P.red);
  statTile(s, 4.72, y, 3.85, "4 страницы", "IEEE, две колонки, вместе со списком литературы. С именами авторов. Труды — ICDMW, индексация EI и IEEE Xplore.", P.navy);
  statTile(s, 8.85, y, 3.85, "CPU + API", "Плюс DGX на несколько часов на задачу. Сутки на H100 — не наш вариант.", P.navy);

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 3.85, w: 12.1, h: 1.15, fill: { color: P.navy }, line: { type: "none" }, rectRadius: 0.1,
  });
  s.addText("Жёсткое требование трека: «Demos must be based on fully implemented and tested systems»", {
    x: 0.95, y: 3.85, w: 11.4, h: 1.15, valign: "middle",
    fontFace: BF, fontSize: 15, bold: true, color: P.white, margin: 0,
  });

  s.addText(
    [
      { text: "Планка трека — не рекорд на бенчмарке, а рабочий инструмент, которым практик захочет пользоваться.", options: { bullet: true, breakLine: true } },
      { text: "Для калибровки: в 2024 году приняли всего около 6 демо. Формат — система с собственным именем, решающая конкретную прикладную задачу.", options: { bullet: true, breakLine: true } },
      { text: "Нужно приехать с постером в Шэньян 12–15 ноября. Регистрация по полному авторскому тарифу, студенческий не засчитывается.", options: { bullet: true } },
    ],
    { x: 0.75, y: 5.2, w: 11.8, h: 1.6, fontFace: BF, fontSize: 12.5, color: P.dark, lineSpacing: 17, paraSpaceAfter: 6, margin: 0 }
  );
  footer(s, "Источник: официальный призыв к демо ICDM 2026 (зеркало Stony Brook) и страница дат.");
}

// ============ 3. КАРТА ОБЛАСТИ ============
{
  const s = lightSlide("Четыре линии — и потолок по вычислениям", "Что произошло в 2025–2026");

  const lines = [
    ["A", "Поиск по коду", "AIDE → SELA → ML-Master → AutoMind → MLEvolve. Решение — это скрипт, механизм — поиск по дереву с правками от модели. Задаёт рекорды на MLE-bench."],
    ["B", "Мультиагентные пайплайны", "AutoML-Agent, MLZero, R&D-Agent, MLE-STAR и наш LightAutoDS-Tab. Роли, проверки, поиск по базе знаний. Только здесь работают поверх настоящих AutoML-библиотек."],
    ["C", "Обученные агенты", "ML-Agent, DeepAnalyze-8B, SandMLE, DataPRM. Модель дообучают вместо промптинга. Самая быстрорастущая линия 2026, причина — цена запросов."],
    ["D", "Бенчмарки и контроль", "MLE-bench, FML-bench, DSGym, TML-bench, Ambig-DS. Самые честные и самые полезные для нас выводы."],
  ];
  lines.forEach((L, i) => {
    const y = 1.72 + i * 1.24;
    s.addShape(pres.ShapeType.roundRect, {
      x: 0.6, y, w: 0.52, h: 0.52, fill: { color: P.navy }, line: { type: "none" }, rectRadius: 0.12,
    });
    s.addText(L[0], { x: 0.6, y, w: 0.52, h: 0.52, align: "center", valign: "middle", fontFace: HF, fontSize: 16, bold: true, color: P.white, margin: 0 });
    s.addText(L[1], { x: 1.3, y: y - 0.04, w: 5.6, h: 0.36, fontFace: BF, fontSize: 14, bold: true, color: P.navy, margin: 0 });
    s.addText(L[2], { x: 1.3, y: y + 0.3, w: 5.7, h: 0.8, fontFace: BF, fontSize: 11, color: P.gray, margin: 0, lineSpacing: 13.5 });
  });

  s.addChart(pres.ChartType.bar, [{
    name: "Доля медалей на MLE-bench, %",
    labels: ["AIDE+o1\nокт'24", "R&D-Agent\nмай'25", "ML-Master\nиюн'25", "R&D-Agent\nокт'25", "MLEvolve\nиюн'26"],
    values: [16.9, 22.4, 29.3, 35.1, 65.3],
  }], {
    x: 7.35, y: 1.62, w: 5.4, h: 4.4,
    barDir: "col",
    showTitle: true, title: "Рекорды на MLE-bench — и цена входа", titleFontFace: HF, titleFontSize: 13, titleColor: P.navy,
    chartColors: [P.navy],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: P.dark, dataLabelFontFace: BF,
    catAxisLabelColor: P.gray, catAxisLabelFontSize: 9, catAxisLabelFontFace: BF,
    valAxisLabelColor: P.gray, valAxisLabelFontSize: 9, valAxisMaxVal: 80,
    valGridLine: { color: "E2E6EF", size: 1 }, catGridLine: { style: "none" },
    showLegend: false, valAxisTitle: "",
  });
  footer(s, "Один полный прогон MLE-bench стоит 1800 GPU-часов. MLEvolve считали на H200 по 12 часов на задачу. В эту гонку мы не идём.");
}

// ============ 4. ТРИ НЕГАТИВНЫХ РЕЗУЛЬТАТА ============
{
  const s = lightSlide("Три опровергающих работы 2026 года", "Тревожный сигнал для идеи «добавим модель в эволюцию»");

  const cards = [
    ["FML-bench", "NUS · Tsinghua · Meta", "«Сложность стратегии сама по себе не гарантирует высокого качества: простой жадный подъём почти не уступает лучшему агенту с поиском по дереву.»", "Разнообразие решений и объём вычислений на итог не влияют."],
    ["ZIB Berlin", "121 прогон · 10 672 программы", "Обычная настройка гиперпараметров одной промежуточной программы сравнялась с полным эволюционным прогоном или обошла его в 13 случаях из 15.", "Около 30% добавленных строк кода дословно повторяют ранее удалённые — поиск ходит по кругу."],
    ["Hutter et al.", "Freiburg · Tübingen · KIT", "Классические методы настройки при равном бюджете в 24 часа обошли подходы на одной только модели. Гибрид Centaur обращался к модели лишь в 30% испытаний — и выиграл.", "Отдельно: выигрыш «тёплого старта» — это конфигурация по умолчанию, а не работа модели."],
  ];
  cards.forEach((c, i) => {
    const x = 0.6 + i * 4.12;
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 1.72, w: 3.86, h: 4.2, fill: { color: P.tint }, line: { type: "none" }, rectRadius: 0.1,
    });
    s.addText(c[0], { x: x + 0.24, y: 1.94, w: 3.4, h: 0.4, fontFace: HF, fontSize: 19, bold: true, color: P.red, margin: 0 });
    s.addText(c[1], { x: x + 0.24, y: 2.34, w: 3.4, h: 0.3, fontFace: BF, fontSize: 10, color: P.gray, margin: 0 });
    s.addText(c[2], { x: x + 0.24, y: 2.74, w: 3.4, h: 2.0, fontFace: BF, fontSize: 11.5, color: P.dark, margin: 0, lineSpacing: 15, italic: true });
    s.addText(c[3], { x: x + 0.24, y: 4.95, w: 3.4, h: 0.8, fontFace: BF, fontSize: 10.5, bold: true, color: P.navy, margin: 0, lineSpacing: 13 });
  });

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 6.12, w: 12.1, h: 0.66, fill: { color: P.redL }, line: { color: P.red, width: 1 }, rectRadius: 0.1,
  });
  s.addText("Вывод: идею «модель как оператор мутации» делать можно — но обязательно со сравнением при равном бюджете. Иначе разнесут на рецензии.", {
    x: 0.9, y: 6.12, w: 11.5, h: 0.66, valign: "middle",
    fontFace: BF, fontSize: 13, bold: true, color: P.red, margin: 0,
  });
}

// ============ 5. ГДЕ ТЕРЯЕТСЯ КАЧЕСТВО ============
{
  const s = lightSlide("Где на самом деле теряется качество", "Что все пишут в Limitations");
  s.addText("Не в поиске. В отборе финальной модели и в проверках. Четыре числа из четырёх независимых работ:", {
    x: 0.6, y: 1.45, w: 12.1, h: 0.35, fontFace: BF, fontSize: 14, color: P.gray, margin: 0,
  });

  const y = 1.95;
  statTile(s, 0.6, y, 2.95, "+9–13 п.п.", "медалей дал бы выбор финального решения по тесту, а не по валидации\nAIRA, Meta FAIR", P.green);
  statTile(s, 3.72, y, 2.95, "ρ = 0.71", "корреляция рангов между валидацией и тестом на 10 469 автоматических экспериментах\nOrze", P.amber);
  statTile(s, 6.84, y, 2.95, "~8 975", "из 10 469 экспериментов испорчены тремя незаметными ошибками в конфигурации\nOrze", P.red);
  statTile(s, 9.96, y, 2.74, "39–63%", "случаев агент молча берётся не за ту целевую переменную, если задача неоднозначна\nAmbig-DS", P.red);

  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 3.95, w: 12.1, h: 1.55, fill: { color: P.navy }, line: { type: "none" }, rectRadius: 0.1,
  });
  s.addText(
    "«Агенты на языковых моделях работают на уровне постановки задачи, но не способны проверить, что реально исполнил код. Будущим автономным системам нужны автоматические тесты проверки конфигурации.»",
    { x: 1.0, y: 4.12, w: 11.3, h: 0.95, valign: "top", fontFace: BF, fontSize: 14, italic: true, color: P.white, margin: 0, lineSpacing: 19 }
  );
  s.addText("— Orze, 2026", { x: 1.0, y: 5.08, w: 11.3, h: 0.3, fontFace: BF, fontSize: 11, color: P.ice, margin: 0 });

  s.addText(
    [
      { text: "DSGym: агенты сохраняют высокую точность, даже когда файлы с данными от них спрятали — часть «успеха» вообще не про данные.", options: { bullet: true, breakLine: true } },
      { text: "KramaBench: сокрытие входов роняет качество лишь на 15–18%.", options: { bullet: true, breakLine: true } },
      { text: "Отдельные проверки есть только у MLE-STAR (два контролёра) и AutoKaggle (модульные тесты) — и обе встроены внутрь своего же агента.", options: { bullet: true } },
    ],
    { x: 0.75, y: 5.7, w: 11.8, h: 1.2, fontFace: BF, fontSize: 12, color: P.dark, lineSpacing: 16, paraSpaceAfter: 4, margin: 0 }
  );
}

// ============ 6. МАТРИЦА ============
{
  const s = lightSlide("Все направления одним экраном", "Что уже занято — по состоянию на август 2026");

  const rows = [
    ["Аудит и повторный отбор моделей", "green", "Самый частый пробел в статьях. Не задет опровержениями.", "Развитие нашей же LightAutoDS-Tab"],
    ["Перемотка поиска и разбор решений", "green", "Обзор по воспроизводимости таких систем не нашёл.", "LangGraph даёт половину как обычную настройку"],
    ["Агент добавляет операторы во фреймворк", "amber", "Остаётся постоянный результат; отвечает на ограничение MLZero.", "OMEGA (ICLR'26) неприятно близко"],
    ["Управление остатком бюджета", "amber", "Метод свободен. Опора: 94% разброса качества даёт архитектура.", "Легко получить выигрыш в пределах случайного разброса"],
    ["Точечная доработка по графу пайплайна", "amber", "Проверять вклад узлов по графу дешевле, чем по коду.", "Перенос приёма MLE-STAR — слишком малый шаг"],
    ["Предсказание качества вместо обучения", "amber", "Перенос идеи DSWorld: поиск быстрее в 3–6 раз.", "Предсказатель может не работать на новых датасетах"],
    ["Диагностика впустую потраченного поиска", "amber", "Перенос измерений ZIB на графовый AutoML. Очень дёшево.", "Это измерение, а не метод"],
    ["Досье датасета (память между запусками)", "amber", "Память в таких агентах привязана к задаче, к датасету — ни у кого.", "Три близкие работы вышли за последние 3 месяца"],
    ["Подсказки из истории прошлых запусков", "amber", "Никто не использует собственную историю фреймворка.", "Обе части давно известны; нужен большой эксперимент"],
    ["Модель как оператор мутации в GOLEM", "amber", "Ниша пуста: FEDOT/GOLEM с оператором на модели не публиковали.", "SemPipes; три опровергающих работы 2026"],
    ["Тёплый старт AutoML через модель", "red", "—", "Опубликовано прямое опровержение"],
    ["Разные модели на разные роли агента", "red", "—", "BudgetMLAgent, AgentOpt и работа 2606.20629"],
    ["Эволюция промптов и обвязки агента", "red", "—", "GEPA (ICLR'26 Oral), EvoAgentX, AFlow и ещё восемь"],
    ["Бенчмарк для малого бюджета", "red", "—", "TML-bench (240/600/1200 с, ~$10) уже занял"],
  ];

  const colX = [0.6, 4.65, 6.35, 9.6];
  const colW = [3.9, 1.55, 3.1, 3.1];
  const hdr = ["Направление", "Вердикт", "Главный аргумент ЗА", "Главный аргумент ПРОТИВ"];
  hdr.forEach((h, i) => {
    s.addText(h.toUpperCase(), {
      x: colX[i], y: 1.5, w: colW[i], h: 0.28,
      fontFace: BF, fontSize: 9, bold: true, color: P.gray, charSpacing: 1, margin: 0,
    });
  });

  rows.forEach((r, i) => {
    const y = 1.85 + i * 0.355;
    if (i % 2 === 0) {
      s.addShape(pres.ShapeType.rect, { x: 0.5, y: y - 0.04, w: 12.3, h: 0.345, fill: { color: P.tint }, line: { type: "none" } });
    }
    const vc = r[1] === "green" ? P.green : r[1] === "amber" ? P.amber : P.red;
    const vt = r[1] === "green" ? "СВОБОДНО" : r[1] === "amber" ? "ЧАСТИЧНО" : "ЗАНЯТО";
    s.addText(r[0], { x: colX[0], y, w: colW[0], h: 0.28, fontFace: BF, fontSize: 10.5, bold: r[1] === "green", color: P.dark, margin: 0, valign: "middle" });
    s.addText(vt, { x: colX[1], y, w: colW[1], h: 0.28, fontFace: BF, fontSize: 9, bold: true, color: vc, margin: 0, valign: "middle", charSpacing: 0.6 });
    s.addText(r[2], { x: colX[2], y, w: colW[2], h: 0.28, fontFace: BF, fontSize: 9.5, color: P.gray, margin: 0, valign: "middle" });
    s.addText(r[3], { x: colX[3], y, w: colW[3], h: 0.28, fontFace: BF, fontSize: 9.5, color: P.gray, margin: 0, valign: "middle" });
  });
  footer(s, "Вердикты получены отдельным придирчивым поиском по arXiv, OpenReview, GitHub и трудам GECCO, AutoML-Conf, KDD, ICDM.");
}

// ============ 7. ЗЕЛЁНОЕ #1 ============
{
  const s = lightSlide("Слой доверия: аудитор и судья", "Направление 1 · основная рекомендация");
  chip(s, 11.2, 0.33, "green");

  s.addText(
    "Обёртка, которая сама ничего не ищет, а проверяет чужой поиск, и работает поверх любого AutoML. Три шага: перед запуском — найти неясности в постановке и задать схему проверки; сам AutoML остаётся чёрным ящиком; после запуска — прогнать проверки на утечки и ошибки и заново выбрать модель по устойчивости, а не по оценке на валидации.",
    { x: 0.6, y: 1.5, w: 12.1, h: 0.95, fontFace: BF, fontSize: 13, color: P.dark, margin: 0, lineSpacing: 18 }
  );

  proCon(s, 0.6, 2.6, 5.95, "pro", "ЗА", [
    "Закрывает две самые частые жалобы во всех статьях: разрыв между валидацией и тестом и отсутствие проверок.",
    "Единственная полностью свободная ниша: статические анализаторы кода и проверка рассуждений агента есть по отдельности, но над AutoML их никто не соединил.",
    "Мы не соревнуемся с поиском — значит три опровергающие работы 2026 года по нам не бьют.",
    "CPU и запросы к модели, около $0.3 за датасет. Работает поверх FEDOT, LightAutoML, AutoGluon и обычного sklearn.",
    "Отлично показывается вживую: подсовываем утечку, лидер по валидации падает, наш выбор держится.",
  ]);
  proCon(s, 6.75, 2.6, 5.95, "con", "ПРОТИВ", [
    "Это развитие нашей же LightAutoDS-Tab: в §6 мы сами написали, что хотим умный разведочный анализ против утечек. Придётся чётко показать, что здесь нового.",
    "Набор проверок конечен: он доказывает наличие утечки, но не её отсутствие.",
    "Веса в формуле отбора задаются вручную, а подбирать их на тесте нельзя — иначе теряется весь смысл.",
    "Есть риск, что вклад сочтут чисто инженерным, если не показать выигрыш на отложенной выборке в числах.",
  ]);
  footer(s, "Опора: AIRA +9–13 п.п. · Orze — корреляция 0.71 и ~8 975 испорченных экспериментов · Ambig-DS 39–63% · DSGym и KramaBench 15–18%.");
}

// ============ 8. ЗЕЛЁНОЕ #2 ============
{
  const s = lightSlide("Перемотка поиска и разбор решений", "Направление 2 · самая сильная научная постановка");
  chip(s, 11.2, 0.33, "green");

  s.addText(
    "Каждый шаг поиска — точка сохранения. Можно вернуться назад вместе с состоянием поиска и памятью агента, пойти другой веткой и в точности повторить прогон. Научная польза: можно померить, во что обошлось одно конкретное решение — сегодня этого не умеет ни одна система.",
    { x: 0.6, y: 1.5, w: 12.1, h: 0.95, fontFace: BF, fontSize: 13, color: P.dark, margin: 0, lineSpacing: 18 }
  );

  proCon(s, 0.6, 2.6, 5.95, "pro", "ЗА", [
    "Самая свободная ниша из всех проверенных. Обзор по воспроизводимости в агентах (2606.04990) не нашёл ни одной системы с точным повтором прогона и ветвлением.",
    "Проблему признают сами авторы: CodeEvolve пишет, что точную последовательность решений повторить нельзя; в работе ZIB повтор удачных запросов даёт нулевое совпадение кода, хотя качество восстанавливается примерно на 76%.",
    "Отлично показывается вживую: отматываем поиск и идём другим путём прямо на глазах у зрителя.",
    "Естественно встраивается в аудитор как модуль — отдельная система не нужна.",
  ]);
  proCon(s, 6.75, 2.6, 5.95, "con", "ПРОТИВ", [
    "Causal Agent Replay (июнь 2026) уже умеет вернуться к точке решения и переиграть её с учётом случайности — надо явно объяснить, чем мы отличаемся.",
    "LangGraph уже даёт сохранение, ветвление и продолжение как обычную настройку: половина функциональности достаётся бесплатно.",
    "Легко прочитать как инженерную удобность. Вклад должен быть в связке с состоянием популяции поиска плюс измеримый научный результат.",
  ]);
}

// ============ 9. ИДЕЯ РУКОВОДИТЕЛЯ ============
{
  const s = lightSlide("Идея руководителя: две версии", "Авто-эволюция FEDOT внешним агентом");

  // v1
  s.addShape(pres.ShapeType.roundRect, { x: 0.6, y: 1.5, w: 5.95, h: 4.9, fill: { color: P.tint }, line: { type: "none" }, rectRadius: 0.1 });
  s.addText("Версия 1 — «в лоб»", { x: 0.9, y: 1.72, w: 4.2, h: 0.4, fontFace: HF, fontSize: 19, bold: true, color: P.navy, margin: 0 });
  chip(s, 4.85, 1.75, "amber");
  s.addText("Языковая модель как оператор мутации внутри эволюционного цикла GOLEM над графом пайплайна.", {
    x: 0.9, y: 2.18, w: 5.35, h: 0.6, fontFace: BF, fontSize: 12, color: P.dark, margin: 0, lineSpacing: 16,
  });
  s.addText([
    { text: "ЗА: ниша пуста — связку FEDOT/GOLEM с оператором на модели не публиковали нигде. Отличие от SemPipes и LMX: мы меняем типизированный граф, а не текст кода, поэтому результат корректен по построению.", options: { bullet: true, breakLine: true } },
    { text: "ЗА: дёшево, только CPU и запросы к модели. GOLEM позволяет подменять мутации из коробки.", options: { bullet: true, breakLine: true } },
    { text: "ПРОТИВ: самый высокий научный риск. Три опровергающие работы 2026 года бьют ровно сюда.", options: { bullet: true, breakLine: true } },
    { text: "ПРОТИВ: заметная вероятность, что честное сравнение при равном бюджете не покажет выигрыша.", options: { bullet: true } },
  ], { x: 0.9, y: 2.78, w: 5.35, h: 3.4, fontFace: BF, fontSize: 11, color: P.dark, margin: 0, lineSpacing: 14.5, paraSpaceAfter: 6 });

  // v2
  s.addShape(pres.ShapeType.roundRect, { x: 6.75, y: 1.5, w: 5.95, h: 4.9, fill: { color: P.greenL }, line: { color: P.green, width: 1 }, rectRadius: 0.1 });
  s.addText("Версия 2 — «Operator Forge»", { x: 7.05, y: 1.72, w: 4.5, h: 0.4, fontFace: HF, fontSize: 19, bold: true, color: P.green, margin: 0 });
  chip(s, 11.0, 1.75, "amber");
  s.addText("Агент не переписывает код фреймворка, а расширяет его набор операторов: пишет новый элементарный оператор и регистрирует его в пространстве поиска.", {
    x: 7.05, y: 2.18, w: 5.35, h: 0.75, fontFace: BF, fontSize: 12, color: P.dark, margin: 0, lineSpacing: 16,
  });
  s.addText([
    { text: "ЗА: единственная незанятая формулировка этой идеи. Остаётся постоянный результат — настоящий PR в FEDOT, что идеально ложится в требование «работающая система».", options: { bullet: true, breakLine: true } },
    { text: "ЗА: прямо отвечает на ограничение MLZero — «качество ограничено набором подключённых библиотек» — и на планы Хуттера по совместному развитию пространств поиска.", options: { bullet: true, breakLine: true } },
    { text: "ПРОТИВ: OMEGA (ICLR'26) уже собирает сгенерированные моделью алгоритмы в библиотеку. Наше отличие — регистрация оператора в пространстве поиска эволюционного AutoML.", options: { bullet: true, breakLine: true } },
    { text: "ПРОТИВ: возня с описанием операторов и правилами совместимости — риск не успеть за 14 дней.", options: { bullet: true } },
  ], { x: 7.05, y: 3.0, w: 5.35, h: 3.25, fontFace: BF, fontSize: 11, color: P.dark, margin: 0, lineSpacing: 14.5, paraSpaceAfter: 6 });

  footer(s, "Рекомендация: если держаться идеи руководителя — брать версию 2, а версию 1 добавлять модулем и обязательно сравнивать при равном бюджете.");
}

// ============ 10. ЧЕТЫРЕ ЖИВЫХ ============
{
  const s = lightSlide("Ещё четыре живых направления", "Заняты частично — годятся как модули");

  const items = [
    ["Управление остатком бюджета", "Агент перераспределяет оставшееся время между этапами: разведка данных → признаки → структура → настройка → ансамбль.",
      "ЗА: опирается на измеренный факт — 94% разброса качества даёт архитектура и лишь 6% гиперпараметры. Метод свободен, TML-bench занял только бенчмарк.",
      "ПРОТИВ: легко получить выигрыш в пределах случайного разброса. Нужно много запусков и доверительные интервалы."],
    ["Точечная доработка по графу", "Дешёвая проверка вклада узлов находит самый важный узел, и модель переделывает только его.",
      "ЗА: приём MLE-STAR стоит $0.24 за задачу, а по графу проверять вклад узлов ещё проще и дешевле, чем по коду — это честный аргумент.",
      "ПРОТИВ: это перенос чужого приёма, шаг небольшой. Лучше как модуль, а не как главная идея."],
    ["Предсказание качества вместо обучения", "Маршрутизатор решает: реально обучить пайплайн или предсказать его качество по признакам датасета и структуре графа.",
      "ЗА: перенос идеи DSWorld — обучение быстрее в 14 раз, поиск в 3–6. История запусков GOLEM сама даёт обучающую выборку.",
      "ПРОТИВ: предсказатель может не переноситься на новые датасеты. Смягчение — предсказывать не оценку, а лучше кандидат родителя или хуже."],
    ["Диагностика впустую потраченного поиска", "Записывать, откуда взялась каждая мутация в GOLEM, и померить, какая доля поиска ходит по кругу.",
      "ЗА: перенос сильного измерения ZIB на графовый AutoML, где этого никто не делал. Почти без запросов к модели, очень дёшево.",
      "ПРОТИВ: это измерение, а не метод. Само по себе тянет на воркшоп, но не на полноценный вклад."],
  ];

  items.forEach((it, i) => {
    const x = 0.6 + (i % 2) * 6.15;
    const y = 1.5 + Math.floor(i / 2) * 2.62;
    s.addShape(pres.ShapeType.roundRect, { x, y, w: 5.95, h: 2.42, fill: { color: P.tint }, line: { type: "none" }, rectRadius: 0.1 });
    s.addShape(pres.ShapeType.roundRect, { x: x + 0.26, y: y + 0.24, w: 0.42, h: 0.42, fill: { color: P.navy }, line: { type: "none" }, rectRadius: 0.1 });
    s.addText(String(i + 1), { x: x + 0.26, y: y + 0.24, w: 0.42, h: 0.42, align: "center", valign: "middle", fontFace: HF, fontSize: 14, bold: true, color: P.white, margin: 0 });
    s.addText(it[0], { x: x + 0.82, y: y + 0.22, w: 4.9, h: 0.4, fontFace: BF, fontSize: 14, bold: true, color: P.navy, margin: 0, valign: "middle" });
    s.addText(it[1], { x: x + 0.26, y: y + 0.72, w: 5.45, h: 0.5, fontFace: BF, fontSize: 10.5, color: P.gray, margin: 0, lineSpacing: 13 });
    s.addText(it[2], { x: x + 0.26, y: y + 1.24, w: 5.45, h: 0.6, fontFace: BF, fontSize: 10, color: P.green, margin: 0, lineSpacing: 12.5 });
    s.addText(it[3], { x: x + 0.26, y: y + 1.84, w: 5.45, h: 0.5, fontFace: BF, fontSize: 10, color: P.red, margin: 0, lineSpacing: 12.5 });
  });
}

// ============ 11. ЕЩЁ ТРИ ============
{
  const s = lightSlide("Три направления, где мы не одни", "Кто-то уже идёт туда же — или это мы сами");

  const items = [
    ["Досье датасета", "Постоянная память, привязанная к датасету и доступная человеку для правки: типы колонок, найденные утечки, группы, история пайплайнов. Устаревает сама, если данные изменились.",
      "Память в таких агентах привязана к задаче или навыку — к датасету ни у кого. MALMAS показателен: его память привязана к датасету, но исчезает в конце сессии.",
      "HASTE, CBR-R&D-Agent и EA-Graph вышли за последние три месяца и подходят с трёх сторон. Своим остаётся только привязка к датасету и автоматическое устаревание."],
    ["Подсказки из истории запусков", "Посчитать, какие операторы чаще встречаются вместе в выигравших пайплайнах, и класть это знание прямо в запрос к модели.",
      "Никто не использует собственную историю: DS-Agent берёт разборы людей, MLE-STAR — веб-поиск. Материал уже готов: PIPES и история запусков GOLEM.",
      "Обе части давно известны по отдельности. После работы про пользу хороших примеров в промпте это ожидаемый ход. Нужен эксперимент со сравнением трёх вариантов."],
    ["Композитные пайплайны для рядов", "Агент предлагает разложение ряда, схему лагов и связку статистики с ML; GOLEM развивает композицию. Настоящее преимущество FEDOT.",
      "GenAutoML и Nexus строят монолитные архитектуры — композитных эволюционных пайплайнов для рядов с агентом нет ни у кого.",
      "Заголовок «агентный AutoML для рядов» занят несколько раз. И это наш же заявленный план в §6 LightAutoDS-Tab — надо согласовать внутри, кто этим занимается."],
  ];

  items.forEach((it, i) => {
    const x = 0.6 + i * 4.12;
    s.addShape(pres.ShapeType.roundRect, { x, y: 1.5, w: 3.86, h: 5.05, fill: { color: P.tint }, line: { type: "none" }, rectRadius: 0.1 });
    s.addText(it[0], { x: x + 0.26, y: 1.72, w: 3.35, h: 0.72, fontFace: HF, fontSize: 16, bold: true, color: P.navy, margin: 0, valign: "top", lineSpacing: 20 });
    chip(s, x + 0.26, 2.46, "amber");
    s.addText(it[1], { x: x + 0.26, y: 2.94, w: 3.35, h: 1.0, fontFace: BF, fontSize: 10.5, color: P.dark, margin: 0, lineSpacing: 13.5 });
    s.addText("ЗА", { x: x + 0.26, y: 3.98, w: 3.35, h: 0.2, fontFace: BF, fontSize: 9.5, bold: true, color: P.green, charSpacing: 1, margin: 0 });
    s.addText(it[2], { x: x + 0.26, y: 4.2, w: 3.35, h: 1.05, fontFace: BF, fontSize: 10, color: P.gray, margin: 0, lineSpacing: 13 });
    s.addText("ПРОТИВ", { x: x + 0.26, y: 5.3, w: 3.35, h: 0.2, fontFace: BF, fontSize: 9.5, bold: true, color: P.red, charSpacing: 1, margin: 0 });
    s.addText(it[3], { x: x + 0.26, y: 5.52, w: 3.35, h: 1.0, fontFace: BF, fontSize: 10, color: P.gray, margin: 0, lineSpacing: 13 });
  });
}

// ============ 12. ЧЕГО НЕ ДЕЛАТЬ ============
{
  const s = lightSlide("Чего делать не надо", "Направления, где уже опубликованы опровержения");
  chip(s, 11.2, 0.33, "red");

  const rows = [
    ["Тёплый старт AutoML через языковую модель", "Опубликовано прямое опровержение: выигрыш модели — это на самом деле конфигурация по умолчанию, а не её работа. Дайте классическому поиску тот же старт, и модель отстаёт на 0.37 п.п. к двенадцатой попытке."],
    ["Разные модели на разные роли: дешёвая разведка, сильная запись", "BudgetMLAgent уже показал такой каскад в ML-агенте и −94% цены. AgentOpt (апрель 2026) подбирает модели по этапам и выдаёт границу «цена — качество». Работа 2606.20629 разбирает роли с полным анализом вклада каждой."],
    ["Эволюция промптов и обвязки агента через AutoML-оптимизатор", "Ниша забита до предела: GEPA (ICLR'26 Oral), EvoAgentX, AgentSquare, AFlow, MermaidFlow, LoongFlow. Заменить AFlow на GOLEM — инженерная подмена, а не научный вклад."],
    ["Бенчмарк агентного AutoML под малый бюджет", "TML-bench (март 2026) сделал ровно это: жёсткие лимиты 240 / 600 / 1200 секунд, весь набор за ~$10. Свободен только метод, но не бенчмарк."],
  ];
  rows.forEach((r, i) => {
    const y = 1.6 + i * 1.28;
    s.addShape(pres.ShapeType.roundRect, { x: 0.6, y, w: 12.1, h: 1.12, fill: { color: P.redL }, line: { type: "none" }, rectRadius: 0.1 });
    s.addShape(pres.ShapeType.roundRect, { x: 0.85, y: y + 0.33, w: 0.46, h: 0.46, fill: { color: P.red }, line: { type: "none" }, rectRadius: 0.11 });
    s.addText("✕", { x: 0.85, y: y + 0.33, w: 0.46, h: 0.46, align: "center", valign: "middle", fontFace: BF, fontSize: 15, bold: true, color: P.white, margin: 0 });
    s.addText(r[0], { x: 1.5, y: y + 0.16, w: 10.9, h: 0.32, fontFace: BF, fontSize: 13.5, bold: true, color: P.red, margin: 0 });
    s.addText(r[1], { x: 1.5, y: y + 0.5, w: 10.9, h: 0.58, fontFace: BF, fontSize: 11, color: P.dark, margin: 0, lineSpacing: 14 });
  });
  footer(s, "Каждая строка — не мнение, а ссылка на опубликованный контролируемый эксперимент или на работу, уже занявшую нишу.");
}

// ============ 13. GRAFT / EMPRYO ============
{
  const s = lightSlide("Что забираем у Graft и Empryo", "Инструменты для программирующих агентов: сначала структура, потом модель");

  s.addText(
    "Обе — не про данные: это контекстный слой и редактор кода для программирующих агентов. Но обе независимо пришли к одному принципу: сначала детерминированная структура, потом модель, и модель необязательна. Для ML-пайплайнов такого нет вообще — это самая пустая ниша из всех проверенных.",
    { x: 0.6, y: 1.45, w: 12.1, h: 0.85, fontFace: BF, fontSize: 13, color: P.dark, margin: 0, lineSpacing: 18 }
  );

  const map = [
    ["граф кода строится без модели, проходы модели необязательны и кэшируются", "постоянный набор проверок, слой модели сверху необязателен, и обязательный замер: сколько даёт модель"],
    ["кэш по контрольной сумме файла, обновляется только изменившееся", "приём DS-Agent «дорого один раз, дальше дёшево» ($1.60 → $0.135), но на уровне датасета"],
    ["радиус поражения: что сломается, если изменить узел", "точечная доработка по типизированному графу — считается дешевле, чем по коду"],
    ["важность символов по PageRank и по истории совместных правок", "важность операторов по тому, как часто они встречаются вместе в выигравших пайплайнах"],
    ["сжатие контекста по структуре, без запросов к модели", "дешевле, чем сжатие через модель, как в EvoDS"],
  ];

  s.addText("ПРИЁМ У НИХ", { x: 0.6, y: 2.5, w: 5.7, h: 0.26, fontFace: BF, fontSize: 9.5, bold: true, color: P.gray, charSpacing: 1.4, margin: 0 });
  s.addText("ЧТО ЭТО В НАШЕЙ ОБЛАСТИ", { x: 6.85, y: 2.5, w: 5.85, h: 0.26, fontFace: BF, fontSize: 9.5, bold: true, color: P.gray, charSpacing: 1.4, margin: 0 });

  map.forEach((m, i) => {
    const y = 2.85 + i * 0.72;
    if (i % 2 === 0) s.addShape(pres.ShapeType.rect, { x: 0.5, y: y - 0.06, w: 12.3, h: 0.7, fill: { color: P.tint }, line: { type: "none" } });
    s.addText(m[0], { x: 0.6, y, w: 5.7, h: 0.58, fontFace: BF, fontSize: 11, color: P.gray, margin: 0, valign: "middle", lineSpacing: 13.5 });
    s.addText("→", { x: 6.35, y, w: 0.4, h: 0.58, fontFace: BF, fontSize: 14, bold: true, color: P.navy, margin: 0, valign: "middle", align: "center" });
    s.addText(m[1], { x: 6.85, y, w: 5.85, h: 0.58, fontFace: BF, fontSize: 11, bold: true, color: P.dark, margin: 0, valign: "middle", lineSpacing: 13.5 });
  });

  s.addShape(pres.ShapeType.roundRect, { x: 0.6, y: 6.5, w: 12.1, h: 0.62, fill: { color: P.amberL }, line: { color: P.amber, width: 1 }, rectRadius: 0.1 });
  s.addText("Их способ измерять берём: агент один и тот же, меняем только контекст, в цене учитываем кэш. Их статистику — нет: у Graft на SWE-bench всего 9 задач, у Empryo раунды на 9 и 10 багах.", {
    x: 0.9, y: 6.5, w: 11.5, h: 0.62, valign: "middle", fontFace: BF, fontSize: 11.5, bold: true, color: P.amber, margin: 0,
  });
}

// ============ 14. РЕКОМЕНДАЦИЯ ============
{
  const s = darkSlide();
  s.addText("РЕКОМЕНДАЦИЯ", { x: 0.7, y: 0.55, w: 11.9, h: 0.28, fontFace: BF, fontSize: 11, bold: true, color: P.ice, charSpacing: 2, margin: 0 });
  s.addText("Одна система, три модуля, никакой гонки за рекордами", {
    x: 0.7, y: 0.88, w: 11.9, h: 0.7, fontFace: HF, fontSize: 32, bold: true, color: P.white, margin: 0,
  });

  const mods = [
    ["Ядро", "Аудитор и судья", "Постоянный набор проверок плюс проверки, которые модель пишет под конкретный датасет. Финальный выбор — по устойчивости, а не по оценке на валидации.", P.ice],
    ["Модуль A", "Память", "Отчёт становится досье с версиями: правки человека переживают перегенерацию, а находки устаревают, если данные изменились.", "9FB0E8"],
    ["Модуль B", "Перемотка", "Возврат к точке решения не как удобство, а как измерительный прибор: показать, во сколько пунктов на отложенной выборке обошлось конкретное решение.", "9FB0E8"],
  ];
  mods.forEach((m, i) => {
    const x = 0.7 + i * 4.07;
    s.addShape(pres.ShapeType.roundRect, { x, y: 1.95, w: 3.82, h: 2.55, fill: { color: "232C55" }, line: { type: "none" }, rectRadius: 0.1 });
    s.addText(m[0].toUpperCase(), { x: x + 0.28, y: 2.18, w: 3.3, h: 0.26, fontFace: BF, fontSize: 9.5, bold: true, color: "7C8AC0", charSpacing: 1.4, margin: 0 });
    s.addText(m[1], { x: x + 0.28, y: 2.48, w: 3.3, h: 0.42, fontFace: HF, fontSize: 19, bold: true, color: m[3], margin: 0 });
    s.addText(m[2], { x: x + 0.28, y: 2.98, w: 3.3, h: 1.35, fontFace: BF, fontSize: 11, color: "C6CFEA", margin: 0, lineSpacing: 15 });
  });

  s.addText("Почему именно так", { x: 0.7, y: 4.75, w: 11.9, h: 0.35, fontFace: BF, fontSize: 14, bold: true, color: P.ice, margin: 0 });
  s.addText([
    { text: "Единственная свободная ниша из четырнадцати проверенных, и её подпирают самые сильные числа во всём обзоре.", options: { bullet: true, breakLine: true } },
    { text: "Мы не соревнуемся с поиском — значит три опровергающие работы 2026 года, которые убивают сюжеты вида «добавим модель в эволюцию», по нам не бьют.", options: { bullet: true, breakLine: true } },
    { text: "CPU и запросы к модели, работает поверх любого фреймворка, легко превращается в живое демо — а трек требует именно работающую систему.", options: { bullet: true } },
  ], { x: 0.85, y: 5.15, w: 11.7, h: 1.6, fontFace: BF, fontSize: 12.5, color: "C6CFEA", margin: 0, lineSpacing: 17, paraSpaceAfter: 5 });

  s.addText("Запасной вариант, если держаться идеи руководителя: агент, который выращивает набор операторов FEDOT.", {
    x: 0.85, y: 6.85, w: 11.7, h: 0.35, fontFace: BF, fontSize: 11, italic: true, color: "7C8AC0", margin: 0,
  });
}

// ============ 15. ПЛАН ============
{
  const s = lightSlide("План на 14 дней", "До 20 августа, 23:59 AoE");

  const steps = [
    ["6–8 авг", "Выбор и стенд", "Окончательно выбрать направление. Собрать 15–20 датасетов: OpenML-CC18, 3–5 на регрессию, 2–3 временных ряда и 4 с заранее внедрёнными утечками. Поднять три фреймворка в одной среде."],
    ["8–13 авг", "Ядро системы", "Постоянные проверки, генератор проверок в песочнице, повторный отбор моделей. Адаптеры к FEDOT, LightAutoML и AutoGluon, которые достают все модели-кандидаты, а не только победителя."],
    ["12–15 авг", "Интерфейс", "Streamlit или Gradio — так быстрее всего. FEDOT.LLM уже на Streamlit, часть переиспользуем. Обязательно режим без интернета с кэшем: связь на площадке не гарантирована."],
    ["14–17 авг", "Эксперименты", "Запуски минимум на пяти случайных инициализациях с доверительными интервалами. Главная таблица: выбор по валидации против нашего выбора на отложенной выборке. Три варианта для сравнения, включая «проверки без модели»."],
    ["16–19 авг", "Текст", "Четыре страницы в формате IEEE. Раздел про ограничения писать обязательно: в этой области его систематически пропускают, и его наличие читается как признак качества."],
    ["20 авг", "Подача", "Через CyberChair, одним PDF. Видео необязательно, но уйдёт на IEEE Xplore рядом со статьёй."],
  ];

  steps.forEach((st, i) => {
    const y = 1.5 + i * 0.87;
    s.addShape(pres.ShapeType.roundRect, { x: 0.6, y, w: 1.35, h: 0.62, fill: { color: i === 5 ? P.red : P.navy }, line: { type: "none" }, rectRadius: 0.1 });
    s.addText(st[0], { x: 0.6, y, w: 1.35, h: 0.62, align: "center", valign: "middle", fontFace: BF, fontSize: 11.5, bold: true, color: P.white, margin: 0 });
    s.addText(st[1], { x: 2.15, y: y - 0.02, w: 2.5, h: 0.32, fontFace: BF, fontSize: 13, bold: true, color: P.navy, margin: 0 });
    s.addText(st[2], { x: 2.15, y: y + 0.28, w: 10.55, h: 0.56, fontFace: BF, fontSize: 10.5, color: P.gray, margin: 0, lineSpacing: 13 });
  });
  footer(s, "Решение по статье 20 сентября · финальная версия 5 октября · конференция 12–15 ноября, Шэньян.");
}

// ============ 16. ФИНАЛ ============
{
  const s = darkSlide();
  s.addText("Итог одной строкой", { x: 0.85, y: 1.9, w: 11.6, h: 0.45, fontFace: BF, fontSize: 14, bold: true, color: P.ice, charSpacing: 1.5, margin: 0 });
  s.addText("Не строить ещё один AutoML-агент.\nПостроить слой доверия над любым из них.", {
    x: 0.85, y: 2.5, w: 11.6, h: 1.7, fontFace: HF, fontSize: 38, bold: true, color: P.white, margin: 0, lineSpacing: 46,
  });
  s.addShape(pres.ShapeType.line, { x: 0.88, y: 4.45, w: 2.2, h: 0, line: { color: P.ice, width: 2 } });
  s.addText(
    "Область три года улучшала поиск и упёрлась в его потолок. Отбор финальной модели, проверки и воспроизводимость остались нетронутыми — при том что именно на них авторы сами указывают в каждом разделе про ограничения.",
    { x: 0.85, y: 4.7, w: 11.0, h: 1.2, fontFace: BF, fontSize: 15, color: "C6CFEA", margin: 0, lineSpacing: 21 }
  );
  s.addText("Полный отчёт: обзор ~90 работ, сводка ограничений, 14 направлений с проверкой занятости, черновик демо-статьи.", {
    x: 0.85, y: 6.3, w: 11.6, h: 0.4, fontFace: BF, fontSize: 11, italic: true, color: "7C8AC0", margin: 0,
  });
}

pres.writeFile({ fileName: "/home/claude/deck/agentic_automl_directions.pptx" }).then(() => console.log("written"));
