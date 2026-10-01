import "server-only";

import createClient from "openapi-fetch";

import type { paths } from "@/generated/api";
import { authHeaders } from "@/lib/api/auth";

/**
 * Typed backend client. Server-side only: the browser never talks to the API
 * directly, so the backend URL is not exposed and no CORS surface is needed.
 */
const baseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl, cache: "no-store" });

// On Cloud Run the backend runs with internal ingress and
// --no-allow-unauthenticated, so every call needs a Google-signed ID token
// whose audience is the backend URL. Locally this adds nothing.
api.use({
  async onRequest({ request }) {
    for (const [name, value] of Object.entries(await authHeaders(baseUrl))) {
      request.headers.set(name, value);
    }
    return request;
  },
});
