"use client";

import { useEffect, useRef } from "react";

const DURATION_MS = 900;
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * Counts from 0 up to `value` once, on mount.
 *
 * Writes to the DOM node directly instead of through state: this ticks once per
 * frame and must not re-render the tree. The server renders the final value, so
 * it is correct before hydration and if JavaScript never runs.
 *
 * The score is also announced as static text elsewhere in the result, so a
 * screen reader never hears the intermediate numbers.
 */
export function CountUp({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    if (reduced || value === 0) {
      el.textContent = String(value);
      return;
    }

    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / DURATION_MS, 1);
      el.textContent = String(Math.round(easeOut(progress) * value));
      if (progress < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <span ref={ref}>{value}</span>;
}
