"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { setLocale } from "@/app/actions";
import { LOCALES, LOCALE_LABEL, LOCALE_NAME, type Locale } from "@/i18n/config";
import { useI18n } from "@/i18n/client";

export function LocaleSwitcher() {
  const { locale, t } = useI18n();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const choose = (next: Locale) => {
    if (next === locale) return;
    startTransition(async () => {
      await setLocale(next);
      // Server Components hold the translated markup, so re-render them.
      router.refresh();
    });
  };

  return (
    <div className="segmented" role="group" aria-label={t.settings.language} data-pending={pending}>
      {LOCALES.map((option) => (
        <button
          key={option}
          type="button"
          className="segmented__option"
          aria-pressed={option === locale}
          aria-label={LOCALE_NAME[option]}
          onClick={() => choose(option)}
        >
          {LOCALE_LABEL[option]}
        </button>
      ))}
    </div>
  );
}
