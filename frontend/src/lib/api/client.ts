import "server-only";

import createClient from "openapi-fetch";

import type { paths } from "@/generated/api";

/**
 * Typed backend client. Server-side only: the browser never talks to the API
 * directly, so the backend URL is not exposed and no CORS surface is needed.
 */
const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl, cache: "no-store" });
