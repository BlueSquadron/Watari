"""SQLAlchemy models for the Watari case management platform.

All models are imported here so Alembic can detect them for migration generation.
"""

from .base import Base, BaseModel, TimestampMixin

from .tenant import Tenant
from .user import User
from .template import CaseTemplate
from .case import Case
from .task import Task
from .observable import Observable
from .asset import Asset
from .evidence import Evidence
from .timeline import TimelineAssetLink, TimelineEntry
from .note import Note, NoteFolder
from .alert import Alert
from .enrichment import EnrichmentResult, EnrichmentSource
from .attack import AttackMapping, AttackReference
from .audit import AuditLog
from .module import Module, ModuleExecution
from .report import Report, ReportTemplate

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
