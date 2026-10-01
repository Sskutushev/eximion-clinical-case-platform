/**
 * Domain types are re-exported from the generated OpenAPI contract so the
 * backend schema stays the single source of truth (see `npm run generate:types`).
 */
import type { components } from "@/generated/api";

type Schemas = components["schemas"];

export type PublicClinicalCase = Schemas["PublicClinicalCase"];
export type PublicFinding = Schemas["PublicFinding"];
export type CaseStats = Schemas["CaseStats"];
export type FindingCategory = Schemas["FindingCategory"];
export type CaseSummary = Schemas["CaseSummary"];
export type CaseList = Schemas["CaseList"];
export type ScoreResponse = Schemas["ScoreResponse"];
export type ScoreOutcome = Schemas["ScoreOutcome"];

/** Result of a backend call, with failures modelled explicitly instead of thrown. */
export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; kind: "not_found" }
  | { ok: false; kind: "invalid" }
  | { ok: false; kind: "unavailable" };
