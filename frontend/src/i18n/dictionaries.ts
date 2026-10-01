import type { Locale } from "@/i18n/config";

/**
 * UI strings only.
 *
 * Clinical content — case titles, presentations, findings, diagnoses — is served
 * exactly as authored and is never machine-translated. A translated finding is a
 * clinical claim, and this system has no business making one.
 */
export type Dictionary = {
  brand: { name: string; tagline: string };
  nav: { skip: string; back: string };
  home: {
    eyebrow: string;
    title: string;
    lede: string;
    solve: string;
    empty: string;
    unavailableTitle: string;
    unavailableBody: string;
  };
  case: {
    eyebrow: string;
    patient: string;
    notSpecified: string;
    years: string;
    presentation: string;
    findings: string;
    loading: string;
    notFoundTitle: string;
    notFoundBody: string;
    errorTitle: string;
    errorBody: string;
    retry: string;
  };
  sex: Record<"female" | "male" | "other", string>;
  category: Record<
    "history" | "symptom" | "vital_sign" | "physical_exam" | "laboratory" | "imaging" | "other",
    string
  >;
  form: {
    eyebrow: string;
    heading: string;
    label: string;
    placeholder: string;
    hint: string;
    submit: string;
    pending: string;
    tooLong: string;
    gone: string;
    rejected: string;
    unavailable: string;
  };
  result: {
    correct: string;
    partially_correct: string;
    incorrect: string;
    answered: string;
    score: (score: number, max: number) => string;
  };
  stats: {
    heading: string;
    attempts: string;
    solved: string;
    average: string;
    distribution: string;
  };
  composition: { heading: string; findings: string; categories: string };
  settings: { theme: string; language: string; light: string; dark: string };
  footer: string;
};

const en: Dictionary = {
  brand: { name: "Eximion", tagline: "Clinical Olympics" },
  nav: { skip: "Skip to content", back: "All cases" },
  home: {
    eyebrow: "Case library",
    title: "Clinical cases",
    lede: "Read the presentation, weigh the findings, commit to a diagnosis. Scoring is instant and the same every time.",
    solve: "Solve",
    empty: "No cases yet. Create one with POST /api/v1/cases or run make seed.",
    unavailableTitle: "Cases are unavailable right now.",
    unavailableBody: "The case service did not respond. Please try again shortly.",
  },
  case: {
    eyebrow: "Clinical case",
    patient: "Patient",
    notSpecified: "Not specified",
    years: "years",
    presentation: "Presentation",
    findings: "Findings",
    loading: "Loading clinical case",
    notFoundTitle: "Case not found",
    notFoundBody: "This case does not exist, or it is no longer available.",
    errorTitle: "Something went wrong",
    errorBody: "The case could not be loaded right now.",
    retry: "Try again",
  },
  sex: { female: "female", male: "male", other: "other" },
  category: {
    history: "History",
    symptom: "Symptoms",
    vital_sign: "Vital signs",
    physical_exam: "Physical examination",
    laboratory: "Laboratory",
    imaging: "Imaging",
    other: "Other",
  },
  form: {
    eyebrow: "Your answer",
    heading: "Your diagnosis",
    label: "Most likely diagnosis",
    placeholder: "Type a diagnosis…",
    hint: "Free text. Capitalisation, extra spaces and trailing punctuation do not matter.",
    submit: "Submit diagnosis",
    pending: "Scoring…",
    tooLong: "Please enter a diagnosis of up to 300 characters.",
    gone: "This case is no longer available.",
    rejected: "The diagnosis could not be accepted. Please revise it.",
    unavailable: "Scoring is temporarily unavailable. Please try again.",
  },
  result: {
    correct: "Correct",
    partially_correct: "Partially correct",
    incorrect: "Incorrect",
    answered: "You answered",
    score: (score, max) => `Score: ${score} out of ${max}`,
  },
  stats: {
    heading: "How others did",
    attempts: "Attempts",
    solved: "Solved",
    average: "Average",
    distribution: "Distribution of outcomes",
  },
  composition: { heading: "Case at a glance", findings: "Findings", categories: "Categories" },
  settings: { theme: "Theme", language: "Language", light: "Light", dark: "Dark" },
  footer: "Synthetic cases for demonstration. Not for clinical use.",
};

const de: Dictionary = {
  brand: { name: "Eximion", tagline: "Klinische Olympiade" },
  nav: { skip: "Zum Inhalt springen", back: "Alle Fälle" },
  home: {
    eyebrow: "Fallsammlung",
    title: "Klinische Fälle",
    lede: "Lesen Sie die Anamnese, gewichten Sie die Befunde, legen Sie sich auf eine Diagnose fest. Die Bewertung erfolgt sofort und immer gleich.",
    solve: "Lösen",
    empty: "Noch keine Fälle. Legen Sie einen über POST /api/v1/cases an oder führen Sie make seed aus.",
    unavailableTitle: "Fälle sind derzeit nicht verfügbar.",
    unavailableBody: "Der Falldienst hat nicht geantwortet. Bitte versuchen Sie es gleich erneut.",
  },
  case: {
    eyebrow: "Klinischer Fall",
    patient: "Patient",
    notSpecified: "Keine Angabe",
    years: "Jahre",
    presentation: "Anamnese",
    findings: "Befunde",
    loading: "Klinischer Fall wird geladen",
    notFoundTitle: "Fall nicht gefunden",
    notFoundBody: "Dieser Fall existiert nicht oder ist nicht mehr verfügbar.",
    errorTitle: "Etwas ist schiefgelaufen",
    errorBody: "Der Fall konnte gerade nicht geladen werden.",
    retry: "Erneut versuchen",
  },
  sex: { female: "weiblich", male: "männlich", other: "divers" },
  category: {
    history: "Vorgeschichte",
    symptom: "Symptome",
    vital_sign: "Vitalparameter",
    physical_exam: "Körperliche Untersuchung",
    laboratory: "Labor",
    imaging: "Bildgebung",
    other: "Sonstiges",
  },
  form: {
    eyebrow: "Ihre Antwort",
    heading: "Ihre Diagnose",
    label: "Wahrscheinlichste Diagnose",
    placeholder: "Diagnose eingeben…",
    hint: "Freitext. Groß- und Kleinschreibung, zusätzliche Leerzeichen und Satzzeichen am Ende spielen keine Rolle.",
    submit: "Diagnose absenden",
    pending: "Wird bewertet…",
    tooLong: "Bitte geben Sie eine Diagnose mit höchstens 300 Zeichen ein.",
    gone: "Dieser Fall ist nicht mehr verfügbar.",
    rejected: "Die Diagnose konnte nicht angenommen werden. Bitte überarbeiten Sie sie.",
    unavailable: "Die Bewertung ist vorübergehend nicht verfügbar. Bitte erneut versuchen.",
  },
  result: {
    correct: "Richtig",
    partially_correct: "Teilweise richtig",
    incorrect: "Falsch",
    answered: "Ihre Antwort",
    score: (score, max) => `Punkte: ${score} von ${max}`,
  },
  stats: {
    heading: "Ergebnisse anderer",
    attempts: "Versuche",
    solved: "Gelöst",
    average: "Durchschnitt",
    distribution: "Verteilung der Ergebnisse",
  },
  composition: { heading: "Fall im Überblick", findings: "Befunde", categories: "Categories" },
  settings: { theme: "Design", language: "Sprache", light: "Hell", dark: "Dunkel" },
  footer: "Synthetische Fälle zu Demonstrationszwecken. Nicht für den klinischen Einsatz.",
};

const zh: Dictionary = {
  brand: { name: "Eximion", tagline: "临床奥林匹克" },
  nav: { skip: "跳至正文", back: "全部病例" },
  home: {
    eyebrow: "病例库",
    title: "临床病例",
    lede: "阅读病史，权衡检查结果，给出诊断。评分即时产生，且每次一致。",
    solve: "作答",
    empty: "暂无病例。可通过 POST /api/v1/cases 创建，或运行 make seed。",
    unavailableTitle: "病例暂时不可用。",
    unavailableBody: "病例服务未响应，请稍后重试。",
  },
  case: {
    eyebrow: "临床病例",
    patient: "患者",
    notSpecified: "未说明",
    years: "岁",
    presentation: "现病史",
    findings: "检查所见",
    loading: "正在加载临床病例",
    notFoundTitle: "未找到病例",
    notFoundBody: "该病例不存在，或已不再可用。",
    errorTitle: "出现问题",
    errorBody: "目前无法加载该病例。",
    retry: "重试",
  },
  sex: { female: "女", male: "男", other: "其他" },
  category: {
    history: "既往史",
    symptom: "症状",
    vital_sign: "生命体征",
    physical_exam: "体格检查",
    laboratory: "实验室检查",
    imaging: "影像学检查",
    other: "其他",
  },
  form: {
    eyebrow: "您的作答",
    heading: "您的诊断",
    label: "最可能的诊断",
    placeholder: "请输入诊断…",
    hint: "自由文本。大小写、多余空格和末尾标点均不影响判定。",
    submit: "提交诊断",
    pending: "评分中…",
    tooLong: "请输入不超过 300 个字符的诊断。",
    gone: "该病例已不再可用。",
    rejected: "该诊断无法被接受，请修改后重试。",
    unavailable: "评分服务暂时不可用，请重试。",
  },
  result: {
    correct: "正确",
    partially_correct: "部分正确",
    incorrect: "不正确",
    answered: "您的答案",
    score: (score, max) => `得分：${score} / ${max}`,
  },
  stats: {
    heading: "其他人的作答",
    attempts: "作答次数",
    solved: "答对率",
    average: "平均分",
    distribution: "结果分布",
  },
  composition: { heading: "病例概览", findings: "检查所见", categories: "Kategorien" },
  settings: { theme: "主题", language: "语言", light: "浅色", dark: "深色" },
  footer: "用于演示的合成病例，不可用于临床。",
};

const ar: Dictionary = {
  brand: { name: "Eximion", tagline: "الأولمبياد السريري" },
  nav: { skip: "تخطَّ إلى المحتوى", back: "كل الحالات" },
  home: {
    eyebrow: "مكتبة الحالات",
    title: "الحالات السريرية",
    lede: "اقرأ الشكوى، وازن الموجودات، ثم حدِّد التشخيص. التقييم فوري ومتطابق في كل مرة.",
    solve: "ابدأ الحل",
    empty: "لا توجد حالات بعد. أنشئ حالة عبر POST /api/v1/cases أو شغِّل make seed.",
    unavailableTitle: "الحالات غير متاحة حاليًا.",
    unavailableBody: "لم تستجب خدمة الحالات. يرجى المحاولة بعد قليل.",
  },
  case: {
    eyebrow: "حالة سريرية",
    patient: "المريض",
    notSpecified: "غير محدد",
    years: "سنة",
    presentation: "الشكوى الحالية",
    findings: "الموجودات",
    loading: "جارٍ تحميل الحالة السريرية",
    notFoundTitle: "الحالة غير موجودة",
    notFoundBody: "هذه الحالة غير موجودة أو لم تعد متاحة.",
    errorTitle: "حدث خطأ ما",
    errorBody: "تعذّر تحميل الحالة في الوقت الحالي.",
    retry: "أعد المحاولة",
  },
  sex: { female: "أنثى", male: "ذكر", other: "آخر" },
  category: {
    history: "السوابق المرضية",
    symptom: "الأعراض",
    vital_sign: "العلامات الحيوية",
    physical_exam: "الفحص السريري",
    laboratory: "التحاليل المخبرية",
    imaging: "التصوير الطبي",
    other: "أخرى",
  },
  form: {
    eyebrow: "إجابتك",
    heading: "تشخيصك",
    label: "التشخيص الأرجح",
    placeholder: "اكتب التشخيص…",
    hint: "نص حر. حالة الأحرف والمسافات الزائدة وعلامات الترقيم في النهاية لا تؤثر على النتيجة.",
    submit: "إرسال التشخيص",
    pending: "جارٍ التقييم…",
    tooLong: "يرجى إدخال تشخيص لا يتجاوز 300 حرف.",
    gone: "لم تعد هذه الحالة متاحة.",
    rejected: "تعذّر قبول التشخيص. يرجى مراجعته.",
    unavailable: "التقييم غير متاح مؤقتًا. يرجى المحاولة مرة أخرى.",
  },
  result: {
    correct: "صحيح",
    partially_correct: "صحيح جزئيًا",
    incorrect: "غير صحيح",
    answered: "إجابتك",
    score: (score, max) => `النتيجة: ${score} من ${max}`,
  },
  stats: {
    heading: "نتائج الآخرين",
    attempts: "المحاولات",
    solved: "نسبة الإجابات الصحيحة",
    average: "المتوسط",
    distribution: "توزيع النتائج",
  },
  composition: { heading: "نظرة عامة على الحالة", findings: "الموجودات", categories: "类别" },
  settings: { theme: "المظهر", language: "اللغة", light: "فاتح", dark: "داكن" },
  footer: "حالات اصطناعية لأغراض العرض فقط. ليست للاستخدام السريري.",
};

const fr: Dictionary = {
  brand: { name: "Eximion", tagline: "Olympiades cliniques" },
  nav: { skip: "Aller au contenu", back: "Tous les cas" },
  home: {
    eyebrow: "Bibliothèque de cas",
    title: "Cas cliniques",
    lede: "Lisez le tableau clinique, pesez les éléments, posez un diagnostic. La notation est instantanée et toujours identique.",
    solve: "Résoudre",
    empty: "Aucun cas pour l’instant. Créez-en un via POST /api/v1/cases ou lancez make seed.",
    unavailableTitle: "Les cas sont indisponibles pour le moment.",
    unavailableBody: "Le service n’a pas répondu. Veuillez réessayer dans un instant.",
  },
  case: {
    eyebrow: "Cas clinique",
    patient: "Patient",
    notSpecified: "Non précisé",
    years: "ans",
    presentation: "Tableau clinique",
    findings: "Éléments cliniques",
    loading: "Chargement du cas clinique",
    notFoundTitle: "Cas introuvable",
    notFoundBody: "Ce cas n’existe pas ou n’est plus disponible.",
    errorTitle: "Une erreur est survenue",
    errorBody: "Le cas n’a pas pu être chargé pour le moment.",
    retry: "Réessayer",
  },
  sex: { female: "féminin", male: "masculin", other: "autre" },
  category: {
    history: "Antécédents",
    symptom: "Symptômes",
    vital_sign: "Constantes",
    physical_exam: "Examen clinique",
    laboratory: "Biologie",
    imaging: "Imagerie",
    other: "Autre",
  },
  form: {
    eyebrow: "Votre réponse",
    heading: "Votre diagnostic",
    label: "Diagnostic le plus probable",
    placeholder: "Saisissez un diagnostic…",
    hint: "Texte libre. La casse, les espaces superflus et la ponctuation finale n’ont aucune incidence.",
    submit: "Envoyer le diagnostic",
    pending: "Notation…",
    tooLong: "Veuillez saisir un diagnostic de 300 caractères maximum.",
    gone: "Ce cas n’est plus disponible.",
    rejected: "Le diagnostic n’a pas pu être accepté. Veuillez le reformuler.",
    unavailable: "La notation est temporairement indisponible. Veuillez réessayer.",
  },
  result: {
    correct: "Correct",
    partially_correct: "Partiellement correct",
    incorrect: "Incorrect",
    answered: "Votre réponse",
    score: (score, max) => `Score : ${score} sur ${max}`,
  },
  stats: {
    heading: "Résultats des autres",
    attempts: "Tentatives",
    solved: "Réussite",
    average: "Moyenne",
    distribution: "Répartition des résultats",
  },
  composition: { heading: "Aperçu du cas", findings: "Éléments", categories: "الفئات" },
  settings: { theme: "Thème", language: "Langue", light: "Clair", dark: "Sombre" },
  footer: "Cas synthétiques à des fins de démonstration. Usage clinique exclu.",
};

const ru: Dictionary = {
  brand: { name: "Eximion", tagline: "Клинические олимпиады" },
  nav: { skip: "Перейти к содержимому", back: "Все кейсы" },
  home: {
    eyebrow: "Библиотека кейсов",
    title: "Клинические кейсы",
    lede: "Прочитайте жалобы, взвесьте находки, поставьте диагноз. Оценка мгновенная и всегда одинаковая.",
    solve: "Решить",
    empty: "Кейсов пока нет. Создайте через POST /api/v1/cases или выполните make seed.",
    unavailableTitle: "Кейсы сейчас недоступны.",
    unavailableBody: "Сервис кейсов не ответил. Попробуйте чуть позже.",
  },
  case: {
    eyebrow: "Клинический кейс",
    patient: "Пациент",
    notSpecified: "Не указано",
    years: "лет",
    presentation: "Жалобы и анамнез",
    findings: "Находки",
    loading: "Загружаем клинический кейс",
    notFoundTitle: "Кейс не найден",
    notFoundBody: "Такого кейса нет или он больше недоступен.",
    errorTitle: "Что-то пошло не так",
    errorBody: "Сейчас не удалось загрузить кейс.",
    retry: "Повторить",
  },
  sex: { female: "женский", male: "мужской", other: "другой" },
  category: {
    history: "Анамнез",
    symptom: "Симптомы",
    vital_sign: "Витальные показатели",
    physical_exam: "Осмотр",
    laboratory: "Лабораторные данные",
    imaging: "Инструментальные исследования",
    other: "Прочее",
  },
  form: {
    eyebrow: "Ваш ответ",
    heading: "Ваш диагноз",
    label: "Наиболее вероятный диагноз",
    placeholder: "Введите диагноз…",
    hint: "Свободный текст. Регистр, лишние пробелы и точка в конце не важны.",
    submit: "Отправить диагноз",
    pending: "Считаем…",
    tooLong: "Введите диагноз длиной до 300 символов.",
    gone: "Этот кейс больше недоступен.",
    rejected: "Диагноз не принят. Проверьте формулировку.",
    unavailable: "Оценка временно недоступна. Попробуйте ещё раз.",
  },
  result: {
    correct: "Верно",
    partially_correct: "Частично верно",
    incorrect: "Неверно",
    answered: "Ваш ответ",
    score: (score, max) => `Баллы: ${score} из ${max}`,
  },
  stats: {
    heading: "Результаты других",
    attempts: "Попыток",
    solved: "Решили верно",
    average: "В среднем",
    distribution: "Распределение результатов",
  },
  composition: { heading: "Кейс кратко", findings: "Находок", categories: "Catégories" },
  settings: { theme: "Тема", language: "Язык", light: "Светлая", dark: "Тёмная" },
  footer: "Синтетические кейсы для демонстрации. Не для клинического применения.",
};

const uk: Dictionary = {
  brand: { name: "Eximion", tagline: "Клінічні олімпіади" },
  nav: { skip: "Перейти до вмісту", back: "Усі кейси" },
  home: {
    eyebrow: "Бібліотека кейсів",
    title: "Клінічні кейси",
    lede: "Прочитайте скарги, зважте знахідки, поставте діагноз. Оцінювання миттєве й завжди однакове.",
    solve: "Розв’язати",
    empty: "Кейсів поки немає. Створіть через POST /api/v1/cases або виконайте make seed.",
    unavailableTitle: "Кейси зараз недоступні.",
    unavailableBody: "Сервіс кейсів не відповів. Спробуйте трохи пізніше.",
  },
  case: {
    eyebrow: "Клінічний кейс",
    patient: "Пацієнт",
    notSpecified: "Не вказано",
    years: "років",
    presentation: "Скарги та анамнез",
    findings: "Знахідки",
    loading: "Завантажуємо клінічний кейс",
    notFoundTitle: "Кейс не знайдено",
    notFoundBody: "Такого кейса немає або він більше недоступний.",
    errorTitle: "Щось пішло не так",
    errorBody: "Зараз не вдалося завантажити кейс.",
    retry: "Повторити",
  },
  sex: { female: "жіноча", male: "чоловіча", other: "інша" },
  category: {
    history: "Анамнез",
    symptom: "Симптоми",
    vital_sign: "Вітальні показники",
    physical_exam: "Огляд",
    laboratory: "Лабораторні дані",
    imaging: "Інструментальні дослідження",
    other: "Інше",
  },
  form: {
    eyebrow: "Ваша відповідь",
    heading: "Ваш діагноз",
    label: "Найімовірніший діагноз",
    placeholder: "Введіть діагноз…",
    hint: "Вільний текст. Регістр, зайві пробіли та крапка в кінці не впливають.",
    submit: "Надіслати діагноз",
    pending: "Оцінюємо…",
    tooLong: "Введіть діагноз довжиною до 300 символів.",
    gone: "Цей кейс більше недоступний.",
    rejected: "Діагноз не прийнято. Перевірте формулювання.",
    unavailable: "Оцінювання тимчасово недоступне. Спробуйте ще раз.",
  },
  result: {
    correct: "Правильно",
    partially_correct: "Частково правильно",
    incorrect: "Неправильно",
    answered: "Ваша відповідь",
    score: (score, max) => `Бали: ${score} з ${max}`,
  },
  stats: {
    heading: "Результати інших",
    attempts: "Спроб",
    solved: "Розв’язали правильно",
    average: "У середньому",
    distribution: "Розподіл результатів",
  },
  composition: { heading: "Кейс стисло", findings: "Знахідок", categories: "Категорий" },
  settings: { theme: "Тема", language: "Мова", light: "Світла", dark: "Темна" },
  footer: "Синтетичні кейси для демонстрації. Не для клінічного застосування.",
};

const DICTIONARIES: Record<Locale, Dictionary> = { en, de, zh, ar, fr, ru, uk };

export const getDictionary = (locale: Locale): Dictionary => DICTIONARIES[locale];
