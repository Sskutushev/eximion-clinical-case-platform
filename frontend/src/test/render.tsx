import { render as rtlRender } from "@testing-library/react";
import type { ReactElement } from "react";

import { DEFAULT_LOCALE, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { I18nProvider } from "@/i18n/client";

/** Renders inside the i18n provider, the way the app always does. */
export function render(ui: ReactElement, { locale = DEFAULT_LOCALE }: { locale?: Locale } = {}) {
  return rtlRender(<I18nProvider locale={locale}>{ui}</I18nProvider>);
}

export const dict = (locale: Locale = DEFAULT_LOCALE) => getDictionary(locale);

export * from "@testing-library/react";
export { render as rtlRender } from "@testing-library/react";
