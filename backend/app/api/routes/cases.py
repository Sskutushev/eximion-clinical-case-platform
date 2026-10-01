import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep, require_admin
from app.schemas.cases import (
    CaseCreated,
    CaseList,
    CaseStats,
    ClinicalCaseCreate,
    ErrorResponse,
    PublicClinicalCase,
    ScoreRequest,
    ScoreResponse,
)
from app.services import cases as service

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])

_NOT_FOUND: dict[int | str, dict[str, Any]] = {status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
    summary="Create a clinical case with its answer key (authoring)",
)
def create_case(
    payload: ClinicalCaseCreate, session: SessionDep, response: Response
) -> CaseCreated:
    case_id = service.create_case(session, payload)
    response.headers["Location"] = f"{router.prefix}/{case_id}"
    return CaseCreated(id=case_id)


@router.get("", summary="List cases (newest first)")
def list_cases(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> CaseList:
    return service.list_cases(session, limit=limit, offset=offset)


@router.get(
    "/{case_id}",
    responses=_NOT_FOUND,
    summary="Get a case for solving (never includes the answer key)",
)
def get_case(case_id: uuid.UUID, session: SessionDep) -> PublicClinicalCase:
    return service.get_public_case(session, case_id)


@router.get(
    "/{case_id}/stats",
    responses=_NOT_FOUND,
    summary="Aggregate attempt statistics (counts only, never answers)",
)
def case_stats(case_id: uuid.UUID, session: SessionDep) -> CaseStats:
    return service.get_case_stats(session, case_id)


@router.post(
    "/{case_id}/score",
    responses=_NOT_FOUND,
    summary="Submit a diagnosis and receive a deterministic score",
)
def score_case(case_id: uuid.UUID, payload: ScoreRequest, session: SessionDep) -> ScoreResponse:
    return service.submit_answer(session, case_id, payload.answer)
