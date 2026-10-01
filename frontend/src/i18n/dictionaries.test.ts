import { describe, expect, it } from "vitest";

import { DEFAULT_LOCALE, LOCALES, LOCALE_NAME, direction } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

type Node = Record<string, unknown>;

/** Every leaf path in an object, e.g. "form.submit". */
function paths(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null) return [prefix];
  return Object.entries(value as Node).flatMap(([key, child]) =>
    paths(child, prefix ? `${prefix}.${key}` : key),
  );
}

function leaves(value: unknown): unknown[] {
  if (typeof value !== "object" || value === null) return [value];
  return Object.values(value as Node).flatMap(leaves);
}

const reference = getDictionary(DEFAULT_LOCALE);

describe("dictionaries", () => {
  it.each(LOCALES)("%s has exactly the keys of the reference locale", (locale) => {
    expect(paths(getDictionary(locale)).sort()).toEqual(paths(reference).sort());
  });

  it.each(LOCALES)("%s has no empty or placeholder strings", (locale) => {
    const values = leaves(getDictionary(locale));
    for (const value of values) {
      if (typeof value === "function") continue;
      expect(typeof value).toBe("string");
      expect((value as string).trim()).not.toBe("");
      expect(value).not.toMatch(/^TODO|^FIXME|^\{\{/);
    }
  });

  it.each(LOCALES)("%s formats the score with both numbers", (locale) => {
    const text = getDictionary(locale).result.score(7, 10);
    expect(text).toContain("7");
    expect(text).toContain("10");
  });

  it("is actually translated, not copied from English", () => {
    const other = LOCALES.filter((l) => l !== DEFAULT_LOCALE);
    for (const locale of other) {
      expect(getDictionary(locale).form.submit).not.toBe(reference.form.submit);
      expect(getDictionary(locale).case.findings).not.toBe(reference.case.findings);
    }
  });

  it("marks Arabic as right-to-left and everything else as left-to-right", () => {
    expect(direction("ar")).toBe("rtl");
    for (const locale of LOCALES.filter((l) => l !== "ar")) {
      expect(direction(locale)).toBe("ltr");
    }
  });

  it("names every locale in its own language", () => {
    for (const locale of LOCALES) {
      expect(LOCALE_NAME[locale].trim()).not.toBe("");
    }
    expect(LOCALE_NAME.zh).toBe("中文");
    expect(LOCALE_NAME.ar).toBe("العربية");
  });
});
