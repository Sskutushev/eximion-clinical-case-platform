import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { __clearTokenCache, authHeaders, isCloudRun } from "@/lib/api/auth";

const AUDIENCE = "https://eximion-backend-abc.a.run.app";

function mockMetadata(response: Partial<Response> & { text?: () => Promise<string> }) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  __clearTokenCache();
  vi.unstubAllEnvs();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Cloud Run identity token", () => {
  it("adds no header outside Cloud Run", async () => {
    const fetchMock = mockMetadata({ ok: true, text: async () => "token" });

    expect(isCloudRun()).toBe(false);
    expect(await authHeaders(AUDIENCE)).toEqual({});
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("requests a token for the backend audience and sends it as a bearer", async () => {
    vi.stubEnv("K_SERVICE", "eximion-frontend");
    const fetchMock = mockMetadata({ ok: true, text: async () => "signed-token\n" });

    expect(await authHeaders(AUDIENCE)).toEqual({ Authorization: "Bearer signed-token" });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(encodeURIComponent(AUDIENCE));
    expect((init.headers as Record<string, string>)["Metadata-Flavor"]).toBe("Google");
  });

  it("caches the token instead of asking on every request", async () => {
    vi.stubEnv("K_SERVICE", "eximion-frontend");
    const fetchMock = mockMetadata({ ok: true, text: async () => "signed-token" });

    await authHeaders(AUDIENCE);
    await authHeaders(AUDIENCE);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to no header when the metadata server fails", async () => {
    vi.stubEnv("K_SERVICE", "eximion-frontend");
    mockMetadata({ ok: false, status: 500, text: async () => "" });

    // The call then fails with the backend's own 401, which the UI handles,
    // rather than crashing the page with an infrastructure error.
    expect(await authHeaders(AUDIENCE)).toEqual({});
  });

  it("falls back to no header when the token is empty", async () => {
    vi.stubEnv("K_SERVICE", "eximion-frontend");
    mockMetadata({ ok: true, text: async () => "   " });

    expect(await authHeaders(AUDIENCE)).toEqual({});
  });
});
