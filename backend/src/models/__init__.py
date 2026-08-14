"""SQLAlchemy models for the Watari case management platform.

All models are imported here so Alembic can detect them for migration generation.
"""

from .alert import Alert
from .asset import Asset
from .attack import AttackMapping, AttackReference
from .audit import AuditLog
from .base import Base, BaseModel, TimestampMixin
from .case import Case
from .enrichment import EnrichmentResult, EnrichmentSource
from .evidence import Evidence
from .module import Module, ModuleExecution
from .note import Note, NoteFolder
from .observable import Observable
from .report import Report, ReportTemplate
from .task import Task
from .template import CaseTemplate
from .tenant import Tenant
from .timeline import TimelineAssetLink, TimelineEntry
from .user import User

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "Tenant",
    "User",
    "CaseTemplate",
    "Case",
    "Task",
    "Observable",
    "Asset",
    "Evidence",
    "TimelineEntry",
    "TimelineAssetLink",
    "Note",
    "NoteFolder",
    "Alert",
    "EnrichmentSource",
    "EnrichmentResult",
    "AttackMapping",
    "AttackReference",
    "AuditLog",
    "Module",
    "ModuleExecution",
    "ReportTemplate",
    "Report",
]
