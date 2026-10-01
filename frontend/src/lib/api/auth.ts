import "server-only";

/**
 * Identity token for calling a private Cloud Run service.
 *
 * Granting the caller `roles/run.invoker` does not authenticate a request; it
 * only permits one. A private Cloud Run service still requires a Google-signed
 * ID token whose audience is the target service URL, so this fetches one from
 * the instance metadata server.
 *
 * The metadata server is only reachable on Cloud Run, which is also the only
 * place the backend is private — locally there is no token and no need for one.
 * Using the metadata endpoint directly keeps this dependency-free.
 */

const METADATA_URL =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";

// Tokens last about an hour; refresh early so a request never carries a stale one.
const REFRESH_MARGIN_MS = 5 * 60 * 1000;
const ASSUMED_LIFETIME_MS = 55 * 60 * 1000;
const FETCH_TIMEOUT_MS = 3000;

type CachedToken = { token: string; expiresAt: number };

const cache = new Map<string, CachedToken>();

/** True on Cloud Run, where K_SERVICE is always set. */
export const isCloudRun = (): boolean => Boolean(process.env.K_SERVICE);

async function fetchIdToken(audience: string): Promise<string | null> {
  const url = `${METADATA_URL}?audience=${encodeURIComponent(audience)}`;
  try {
    const response = await fetch(url, {
      headers: { "Metadata-Flavor": "Google" },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
      cache: "no-store",
    });
    if (!response.ok) {
      console.error("identity token request failed", { status: response.status });
      return null;
    }
    const token = (await response.text()).trim();
    return token.length > 0 ? token : null;
  } catch (error) {
    console.error("identity token request failed", { error: String(error) });
    return null;
  }
}

/**
 * Authorization header for a backend request, or nothing outside Cloud Run.
 *
 * A failure returns no header rather than throwing: the request then fails with
 * the backend's own 401/403, which is already handled, instead of crashing the
 * page with an infrastructure error.
 */
export async function authHeaders(audience: string): Promise<Record<string, string>> {
  if (!isCloudRun()) return {};

  const cached = cache.get(audience);
  if (cached && cached.expiresAt - REFRESH_MARGIN_MS > Date.now()) {
    return { Authorization: `Bearer ${cached.token}` };
  }

  const token = await fetchIdToken(audience);
  if (token === null) return {};

  cache.set(audience, { token, expiresAt: Date.now() + ASSUMED_LIFETIME_MS });
  return { Authorization: `Bearer ${token}` };
}

/** Test seam. */
export const __clearTokenCache = (): void => cache.clear();
