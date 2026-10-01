"use server";

import { cookies } from "next/headers";

import { LOCALE_COOKIE, type Locale, isLocale } from "@/i18n/config";

const ONE_YEAR = 60 * 60 * 24 * 365;

/** Persists the chosen UI language. Rejects anything outside the known set. */
export async function setLocale(locale: Locale): Promise<void> {
  if (!isLocale(locale)) return;
  (await cookies()).set(LOCALE_COOKIE, locale, {
    maxAge: ONE_YEAR,
    sameSite: "lax",
    path: "/",
    httpOnly: false,
  });
}
