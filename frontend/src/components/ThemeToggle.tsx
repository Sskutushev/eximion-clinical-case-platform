"use client";

import { useCallback, useSyncExternalStore } from "react";

import { MoonIcon, SunIcon } from "@/components/icons";
import { useI18n } from "@/i18n/client";

type Theme = "light" | "dark";

const STORAGE_KEY = "theme";
const CHANGE_EVENT = "themechange";

function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  media?.addEventListener("change", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    media?.removeEventListener("change", onChange);
  };
}

/**
 * Light/dark switch.
 *
 * The theme lives on <html data-theme>, applied by an inline script before
 * first paint (see layout), so there is no flash. This reads that external
 * state rather than duplicating it in React, and renders the light icon on
 * the server where the real theme is not yet knowable.
 */
export function ThemeToggle() {
  const { t } = useI18n();
  const theme = useSyncExternalStore<Theme>(subscribe, currentTheme, () => "light");

  const toggle = useCallback(() => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private mode or blocked storage: the choice just does not persist.
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className="icon-btn"
      onClick={toggle}
      aria-label={t.settings.theme}
      aria-pressed={isDark}
      title={isDark ? t.settings.light : t.settings.dark}
    >
      <span className="icon-btn__swap" data-dark={isDark}>
        <SunIcon />
        <MoonIcon />
      </span>
    </button>
  );
}
