"use client";

import { useCallback, useRef } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";

const MAX_TILT_DEG = 7;

/**
 * Pointer-tracked 3D tilt plus a spotlight that follows the cursor.
 *
 * Writes CSS custom properties instead of re-rendering: the pointer moves far
 * more often than React should. Everything degrades to a plain card when the
 * pointer is coarse or the viewer asked for reduced motion (handled in CSS).
 */
export function TiltCard({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const frame = useRef<number>(0);

  const handleMove = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el || event.pointerType !== "mouse") return;

    cancelAnimationFrame(frame.current);
    const { clientX, clientY } = event;
    frame.current = requestAnimationFrame(() => {
      const rect = el.getBoundingClientRect();
      const px = (clientX - rect.left) / rect.width;
      const py = (clientY - rect.top) / rect.height;

      el.style.setProperty("--tilt-x", `${(0.5 - py) * 2 * MAX_TILT_DEG}deg`);
      el.style.setProperty("--tilt-y", `${(px - 0.5) * 2 * MAX_TILT_DEG}deg`);
      el.style.setProperty("--spot-x", `${px * 100}%`);
      el.style.setProperty("--spot-y", `${py * 100}%`);
      el.style.setProperty("--spot-opacity", "1");
    });
  }, []);

  const handleLeave = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    cancelAnimationFrame(frame.current);
    el.style.setProperty("--tilt-x", "0deg");
    el.style.setProperty("--tilt-y", "0deg");
    el.style.setProperty("--spot-opacity", "0");
  }, []);

  return (
    <div
      ref={ref}
      className={className}
      onPointerMove={handleMove}
      onPointerLeave={handleLeave}
    >
      {children}
    </div>
  );
}
