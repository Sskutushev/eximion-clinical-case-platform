import type { Locale } from "@/i18n/config";

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
  settings: { theme: string; language: string; light: string; dark: string };
  footer: string;
};

/**
 * UI strings only.
 *
 * Clinical content (case titles, presentations, findings) is served exactly as
 * authored and is never machine-translated — a translated diagnosis would be a
 * clinical claim this system has no business making.
 */
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
    score: (score: number, max: number) => `Score: ${score} out of ${max}`,
  },
  settings: { theme: "Theme", language: "Language", light: "Light", dark: "Dark" },
  footer: "Synthetic cases for demonstration. Not for clinical use.",
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
    score: (score: number, max: number) => `Баллы: ${score} из ${max}`,
  },
  settings: { theme: "Тема", language: "Язык", light: "Светлая", dark: "Тёмная" },
  footer: "Синтетические кейсы для демонстрации. Не для клинического применения.",
};

const DICTIONARIES: Record<Locale, Dictionary> = { en, ru };

export const getDictionary = (locale: Locale): Dictionary => DICTIONARIES[locale];
