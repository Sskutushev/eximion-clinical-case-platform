/** Ordered by the audience this product serves, English first. */
export const LOCALES = ["en", "de", "zh", "ar", "fr", "ru", "uk"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_COOKIE = "locale";

/** Endonyms: a language is listed the way its own speakers write it. */
export const LOCALE_NAME: Record<Locale, string> = {
  en: "English",
  de: "Deutsch",
  zh: "中文",
  ar: "العربية",
  fr: "Français",
  ru: "Русский",
  uk: "Українська",
};

export const LOCALE_SHORT: Record<Locale, string> = {
  en: "EN",
  de: "DE",
  zh: "ZH",
  ar: "AR",
  fr: "FR",
  ru: "RU",
  uk: "UK",
};

/** Arabic is right-to-left; everything else here is left-to-right. */
const RTL_LOCALES: ReadonlySet<Locale> = new Set<Locale>(["ar"]);

export const direction = (locale: Locale): "rtl" | "ltr" =>
  RTL_LOCALES.has(locale) ? "rtl" : "ltr";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}
