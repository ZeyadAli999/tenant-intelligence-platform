"""Domain model registry.

Phase 1 intentionally defines no business entities. Later migration phases will import
all model modules here so Alembic can discover their metadata.
"""

from database.base import Base
from models.conversation import Conversation, Message
from models.database_connection import DatabaseConnection
from models.database_schema import DatabaseColumn, DatabaseSchema, DatabaseTable
from models.document import DocumentChunk, KnowledgeBase, MessageCitation, StoredFile
from models.permission import ColumnPermission, TablePermission
from models.query_execution import QueryExecution
from models.refresh_token import RefreshToken
from models.role import Role, UserRole
from models.tenant import EntityStatus, Tenant
from models.user import User

__all__ = [
    "Base",
    "ColumnPermission",
    "Conversation",
    "DatabaseColumn",
    "DatabaseConnection",
    "DatabaseSchema",
    "DatabaseTable",
    "DocumentChunk",
    "EntityStatus",
    "KnowledgeBase",
    "Message",
    "MessageCitation",
    "QueryExecution",
    "RefreshToken",
    "Role",
    "StoredFile",
    "TablePermission",
    "Tenant",
    "User",
    "UserRole",
]
