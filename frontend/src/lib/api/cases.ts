import "server-only";

import { api } from "@/lib/api/client";
import type {
  ApiResult,
  CaseList,
  CaseStats,
  PublicClinicalCase,
  ScoreResponse,
} from "@/lib/api/types";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const isUuid = (value: string): boolean => UUID_RE.test(value);

function failure<T>(status: number): ApiResult<T> {
  if (status === 404) return { ok: false, kind: "not_found" };
  if (status === 422) return { ok: false, kind: "invalid" };
  return { ok: false, kind: "unavailable" };
}

export async function listCases(): Promise<ApiResult<CaseList>> {
  try {
    const { data, response } = await api.GET("/api/v1/cases", {
      params: { query: { limit: 50 } },
    });
    return data ? { ok: true, data } : failure(response.status);
  } catch (error) {
    console.error("listCases: backend unreachable", { error: String(error) });
    return { ok: false, kind: "unavailable" };
  }
}

export async function getCase(caseId: string): Promise<ApiResult<PublicClinicalCase>> {
  if (!isUuid(caseId)) return { ok: false, kind: "not_found" };
  try {
    const { data, response } = await api.GET("/api/v1/cases/{case_id}", {
      params: { path: { case_id: caseId } },
    });
    return data ? { ok: true, data } : failure(response.status);
  } catch (error) {
    console.error("getCase: backend unreachable", { error: String(error) });
    return { ok: false, kind: "unavailable" };
  }
}

export async function getCaseStats(caseId: string): Promise<ApiResult<CaseStats>> {
  if (!isUuid(caseId)) return { ok: false, kind: "not_found" };
  try {
    const { data, response } = await api.GET("/api/v1/cases/{case_id}/stats", {
      params: { path: { case_id: caseId } },
    });
    return data ? { ok: true, data } : failure(response.status);
  } catch (error) {
    console.error("getCaseStats: backend unreachable", { error: String(error) });
    return { ok: false, kind: "unavailable" };
  }
}

export async function scoreCase(
  caseId: string,
  answer: string,
): Promise<ApiResult<ScoreResponse>> {
  if (!isUuid(caseId)) return { ok: false, kind: "not_found" };
  try {
    const { data, response } = await api.POST("/api/v1/cases/{case_id}/score", {
      params: { path: { case_id: caseId } },
      body: { answer },
    });
    return data ? { ok: true, data } : failure(response.status);
  } catch (error) {
    console.error("scoreCase: backend unreachable", { error: String(error) });
    return { ok: false, kind: "unavailable" };
  }
}
