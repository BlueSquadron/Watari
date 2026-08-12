"""Evidence endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.schemas.evidence import (
    EvidenceRegister,
    EvidenceResponse,
    EvidenceUpdate,
    EvidenceUploadResponse,
)
from src.services import evidence as evidence_service

router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/cases/{case_id}/evidence", tags=["evidence"]
)


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@router.get("", response_model=ApiResponse[list[EvidenceResponse]])
async def list_evidence(
    tenant_id: UUID,
    case_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.EVIDENCE, Action.READ))
    ],
) -> ApiResponse[list[EvidenceResponse]]:
    _check(auth, tenant_id)
    rows, total = await evidence_service.list_evidence(
        db, case_id, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[EvidenceResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@router.post(
    "",
    response_model=ApiResponse[EvidenceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register_evidence(
    tenant_id: UUID,
    case_id: UUID,
    payload: EvidenceRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.EVIDENCE, Action.CREATE))
    ],
) -> ApiResponse[EvidenceResponse]:
    _check(auth, tenant_id)
    ev = await evidence_service.register_evidence(
        db, case_id=case_id, registered_by=auth.user_id, payload=payload
    )
    return ApiResponse(data=EvidenceResponse.model_validate(ev))


@router.post(
    "/{evidence_id}/upload",
    response_model=ApiResponse[EvidenceUploadResponse],
)
async def upload_evidence_file(
    tenant_id: UUID,
    case_id: UUID,
    evidence_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.EVIDENCE, Action.UPDATE))
    ],
    file: Annotated[UploadFile, File(description="The evidence file to upload")],
    password: Annotated[str | None, Form(description="Optional password-protect the file")] = None,
) -> ApiResponse[EvidenceUploadResponse]:
    _check(auth, tenant_id)
    ev = await evidence_service.upload_evidence_file(
        db, evidence_id, file, password=password, actor_id=auth.user_id
    )
    return ApiResponse(
        data=EvidenceUploadResponse(
            evidence=EvidenceResponse.model_validate(ev),
            integrity_verified=bool(ev.integrity_verified),
            integrity_mismatch=ev.integrity_mismatch,
        )
    )


@router.get("/{evidence_id}/download")
async def download_evidence_file(
    tenant_id: UUID,
    case_id: UUID,
    evidence_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.EVIDENCE, Action.READ))
    ],
    password: str | None = None,
) -> Response:
    _check(auth, tenant_id)
    evidence, data = await evidence_service.download_evidence_file(
        db, evidence_id, password=password
    )
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{evidence.filename}"'
        },
    )


@router.patch("/{evidence_id}", response_model=ApiResponse[EvidenceResponse])
async def update_evidence(
    tenant_id: UUID,
    case_id: UUID,
    evidence_id: UUID,
    payload: EvidenceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.EVIDENCE, Action.UPDATE))
    ],
) -> ApiResponse[EvidenceResponse]:
    _check(auth, tenant_id)
    ev = await evidence_service.update_evidence(db, evidence_id, payload)
    return ApiResponse(data=EvidenceResponse.model_validate(ev))


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    tenant_id: UUID,
    case_id: UUID,
    evidence_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.EVIDENCE, Action.DELETE))
    ],
) -> None:
    _check(auth, tenant_id)
    await evidence_service.delete_evidence(db, evidence_id)


__all__ = ["router"]
