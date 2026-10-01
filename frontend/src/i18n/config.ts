export const LOCALES = ["en", "ru"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_COOKIE = "locale";

export const LOCALE_LABEL: Record<Locale, string> = {
  en: "EN",
  ru: "RU",
};

export const LOCALE_NAME: Record<Locale, string> = {
  en: "English",
  ru: "Русский",
};

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}
