"use client";

import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import { DEFAULT_LOCALE, type Locale } from "@/i18n/config";
import { type Dictionary, getDictionary } from "@/i18n/dictionaries";

type I18n = { locale: Locale; t: Dictionary };

const I18nContext = createContext<I18n>({
  locale: DEFAULT_LOCALE,
  t: getDictionary(DEFAULT_LOCALE),
});

/** Server layout resolves the locale once and hands it to the client tree. */
export function I18nProvider({ locale, children }: { locale: Locale; children: ReactNode }) {
  return (
    <I18nContext.Provider value={{ locale, t: getDictionary(locale) }}>
      {children}
    </I18nContext.Provider>
  );
}

export const useI18n = (): I18n => useContext(I18nContext);
