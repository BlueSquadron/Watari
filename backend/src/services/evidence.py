"""Evidence service: register, upload, hash verification, password protection."""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case, Evidence
from src.schemas.evidence import EvidenceRegister, EvidenceUpdate

from . import storage
from .timeline_recorder import record_event


async def _get_case_or_404(db: AsyncSession, case_id: UUID) -> Case:
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case {case_id} not found")
    return case


async def _get_evidence_or_404(db: AsyncSession, evidence_id: UUID) -> Evidence:
    ev = (
        await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    ).scalar_one_or_none()
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Evidence {evidence_id} not found")
    return ev


async def list_evidence(
    db: AsyncSession, case_id: UUID, *, limit: int = 100, offset: int = 0
) -> tuple[list[Evidence], int]:
    base = select(Evidence).where(Evidence.case_id == case_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(Evidence.registered_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), int(total)


async def register_evidence(
    db: AsyncSession, *, case_id: UUID, registered_by: UUID, payload: EvidenceRegister
) -> Evidence:
    """Register an evidence record ahead of upload (or for already-uploaded data)."""
    case = await _get_case_or_404(db, case_id)
    evidence = Evidence(
        tenant_id=case.tenant_id,
        case_id=case.id,
        filename=payload.filename,
        type=payload.type.value,
        file_hash_sha256=payload.file_hash_sha256.lower(),
        file_size=payload.file_size,
        description=payload.description,
        tags=list(payload.tags),
        registered_by=registered_by,
    )
    db.add(evidence)
    await db.flush()
    await record_event(
        db,
        tenant_id=case.tenant_id,
        case_id=case.id,
        event_type="evidence_registered",
        description=f"Evidence registered: {evidence.filename}",
        category="evidence",
        actor_id=registered_by,
        metadata={
            "evidence_id": str(evidence.id),
            "sha256": evidence.file_hash_sha256,
            "size": evidence.file_size,
        },
    )
    await db.refresh(evidence)
    return evidence


async def upload_evidence_file(
    db: AsyncSession,
    evidence_id: UUID,
    file: UploadFile,
    *,
    password: str | None = None,
    actor_id: UUID,
) -> Evidence:
    """Upload the binary payload for a previously-registered evidence item."""
    evidence = await _get_evidence_or_404(db, evidence_id)
    raw = await file.read()

    # Compute and compare hashes
    computed_hash = storage.compute_sha256(raw)
    declared_hash = evidence.file_hash_sha256.lower()
    integrity_match = computed_hash == declared_hash

    # Optionally encrypt
    body: bytes
    is_encrypted = False
    if password is not None and password.strip():
        body = storage.encrypt_with_password(raw, password)
        is_encrypted = True
    else:
        body = raw

    storage_key = storage.build_key(
        tenant_id=str(evidence.tenant_id),
        case_id=str(evidence.case_id),
        storage_uuid=str(uuid.uuid4()),
    )
    await storage.upload_bytes(storage_key, body)

    evidence.storage_path = storage_key
    evidence.is_uploaded = True
    evidence.is_encrypted = is_encrypted
    evidence.integrity_verified = integrity_match
    evidence.integrity_mismatch = not integrity_match
    await db.flush()

    await record_event(
        db,
        tenant_id=evidence.tenant_id,
        case_id=evidence.case_id,
        event_type="evidence_uploaded" if integrity_match else "evidence_integrity_mismatch",
        description=(
            f"Evidence file uploaded: {evidence.filename}"
            if integrity_match
            else f"Evidence hash mismatch detected for {evidence.filename}"
        ),
        category="evidence",
        actor_id=actor_id,
        metadata={
            "evidence_id": str(evidence.id),
            "declared_sha256": declared_hash,
            "computed_sha256": computed_hash,
            "integrity_verified": integrity_match,
        },
    )
    # Dispatch platform event for pipeline modules to pick up
    from src.modules.base import PlatformEvent

    from . import events as _events

    await _events.fire(
        db,
        tenant_id=evidence.tenant_id,
        event=PlatformEvent.EVIDENCE_UPLOADED,
        payload={
            "case_id": str(evidence.case_id),
            "evidence_id": str(evidence.id),
            "filename": evidence.filename,
            "type": evidence.type,
        },
        actor_id=actor_id,
    )
    await db.refresh(evidence)
    return evidence


async def download_evidence_file(
    db: AsyncSession, evidence_id: UUID, password: str | None = None
) -> tuple[Evidence, bytes]:
    """Download an evidence file, decrypting if it was password-protected."""
    evidence = await _get_evidence_or_404(db, evidence_id)
    if not evidence.is_uploaded or evidence.storage_path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not yet uploaded")
    data = await storage.download_bytes(evidence.storage_path)
    if evidence.is_encrypted:
        if not password:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Password required for encrypted evidence",
            )
        try:
            data = storage.decrypt_with_password(data, password)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Invalid password"
            ) from exc
    return evidence, data


async def update_evidence(
    db: AsyncSession, evidence_id: UUID, payload: EvidenceUpdate
) -> Evidence:
    evidence = await _get_evidence_or_404(db, evidence_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(evidence, k, v)
    await db.flush()
    await db.refresh(evidence)
    return evidence


async def delete_evidence(db: AsyncSession, evidence_id: UUID) -> None:
    evidence = await _get_evidence_or_404(db, evidence_id)
    if evidence.storage_path:
        await storage.delete_object(evidence.storage_path)
    await db.delete(evidence)
    await db.flush()


__all__ = [
    "list_evidence",
    "register_evidence",
    "upload_evidence_file",
    "download_evidence_file",
    "update_evidence",
    "delete_evidence",
]
