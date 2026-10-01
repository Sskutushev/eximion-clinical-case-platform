"use client";

import { useRouter } from "next/navigation";
import { useId, useTransition } from "react";
import type { ChangeEvent } from "react";

import { setLocale } from "@/app/actions";
import { GlobeIcon } from "@/components/icons";
import { useI18n } from "@/i18n/client";
import { LOCALES, LOCALE_NAME, LOCALE_SHORT, type Locale, isLocale } from "@/i18n/config";

/**
 * Seven languages is past the point where a segmented control works, so this is
 * a native select: it is keyboard accessible, screen-reader correct and renders
 * as the platform picker on mobile for free.
 */
export function LocaleSwitcher() {
  const { locale, t } = useI18n();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const id = useId();

  const choose = (event: ChangeEvent<HTMLSelectElement>) => {
    const next = event.target.value;
    if (!isLocale(next) || next === locale) return;
    startTransition(async () => {
      await setLocale(next as Locale);
      // The translated markup lives in Server Components, so re-render them.
      router.refresh();
    });
  };

  return (
    <div className="select" data-pending={pending}>
      <GlobeIcon className="select__icon" />
      <label className="visually-hidden" htmlFor={id}>
        {t.settings.language}
      </label>
      <select id={id} value={locale} onChange={choose} disabled={pending}>
        {LOCALES.map((option) => (
          <option key={option} value={option}>
            {LOCALE_SHORT[option]} · {LOCALE_NAME[option]}
          </option>
        ))}
      </select>
    </div>
  );
}
