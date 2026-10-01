import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// `globals: false` means Testing Library cannot auto-register its cleanup hook.
afterEach(cleanup);

// jsdom has no matchMedia; components that check prefers-reduced-motion need it.
vi.stubGlobal("matchMedia", (query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  addListener: vi.fn(),
  removeListener: vi.fn(),
  dispatchEvent: vi.fn(),
}));
