"""Controlled, audited execution boundary for future database agents."""

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.exceptions import ApplicationError, ResourceNotFoundError
from core.encryption import (
    CredentialCipher,
    credential_context,
)
from core.tenant_context import TenantContext
from models import QueryExecution
from repositories.database_connections import DatabaseConnectionRepository
from services.database.adapters.base import QueryLimits
from services.database.column_lineage import ColumnLineageAnalyzer
from services.database.connection_tester import connection_parameters
from services.database.dialect_resolver import AdapterRegistry, build_adapter_registry
from services.database.host_security import HostSecurityValidator
from services.database.permission_resolver import PermissionResolver
from services.database.query_rewriter import QueryRewriter
from services.database.query_validator import QueryValidator, sanitized_sql
from services.database.result_masking import ResultMasker
from services.database.row_filter import RuntimeFilterContext

logger = logging.getLogger(__name__)


class SafeQueryRejectedError(ApplicationError):
    status_code = 400
    detail = "Query rejected"


@dataclass(frozen=True)
class SafeQueryResult:
    query_execution_id: UUID
    normalized_query: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, object], ...]
    row_count: int
    truncated: bool
    execution_time_ms: int
    referenced_tables: tuple[str, ...]
    referenced_columns: tuple[str, ...]


class SafeQueryService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        registry: AdapterRegistry | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.registry = registry or build_adapter_registry()

    async def execute(
        self,
        tenant_context: TenantContext,
        connection_id: UUID,
        sql: str,
        *,
        request_id: str,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> SafeQueryResult:
        tenant_id = tenant_context.tenant.id
        user_id = tenant_context.user.id
        connection = await DatabaseConnectionRepository(self.session).get_connection(
            tenant_id, connection_id
        )
        if connection is None or connection.status != "connected":
            raise ResourceNotFoundError
        allowed = await PermissionResolver(self.session).resolve(
            tenant_id=tenant_id,
            user_id=user_id,
            role_ids=tuple(role.id for role in tenant_context.roles),
            connection_id=connection_id,
        )
        validation = QueryValidator(self.settings).validate(sql, allowed)
        execution = QueryExecution(
            id=uuid4(),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=message_id,
            connection_id=connection_id,
            generated_sql=sanitized_sql(sql),
            normalized_sql=sanitized_sql(validation.normalized_sql or ""),
            query_type="with"
            if sql.lstrip().casefold().startswith("with")
            else "select",
            validation_status="accepted" if validation.accepted else "rejected",
            validation_errors=[
                {"code": item.code, "message": item.message}
                for item in validation.errors
            ],
            applied_row_filters={},
            referenced_tables=list(validation.referenced_tables),
            referenced_columns=list(validation.referenced_columns),
            execution_status="pending" if validation.accepted else "rejected",
        )
        self.session.add(execution)
        await self.session.commit()
        if not validation.accepted or validation.expression is None:
            logger.info(
                "Query validation rejected request_id=%r tenant_id=%s user_id=%s connection_id=%s query_execution_id=%s",
                request_id,
                tenant_id,
                user_id,
                connection_id,
                execution.id,
            )
            raise SafeQueryRejectedError
        try:
            rewritten = QueryRewriter(self.settings).rewrite(
                validation.expression,
                allowed,
                context=RuntimeFilterContext(user_id=user_id, tenant_id=tenant_id),
            )
            cipher = CredentialCipher.from_settings(self.settings)
            password = cipher.decrypt(
                connection.encrypted_password,
                associated_data=credential_context(tenant_id, connection.id),
            )
            adapter = self.registry.resolve(connection.database_type)
            started = perf_counter()
            adapter_result = await adapter.execute_query(
                connection_parameters(connection, password),
                HostSecurityValidator(
                    allow_private=self.settings.allow_private_database_hosts
                ),
                rewritten.sql,
                rewritten.parameters,
                QueryLimits(
                    statement_timeout_ms=int(
                        self.settings.customer_database_command_timeout_seconds * 1000
                    ),
                    lock_timeout_ms=self.settings.safe_query_lock_timeout_ms,
                    max_rows=self.settings.safe_query_max_rows,
                    max_columns=self.settings.safe_query_max_columns,
                ),
            )
            elapsed = int((perf_counter() - started) * 1000)
            masker = ResultMasker(
                self.settings.result_masking_key.get_secret_value(),
                max_cell_length=self.settings.safe_query_max_cell_length,
                max_result_bytes=self.settings.safe_query_max_result_bytes,
            )
            rows, size_truncated = masker.mask_rows(
                adapter_result.columns,
                adapter_result.rows,
                ColumnLineageAnalyzer(allowed)
                .analyze(validation.expression)
                .masking_plan,
            )
            execution.applied_row_filters = rewritten.applied_filters
            execution.execution_status = "succeeded"
            execution.execution_time_ms = elapsed
            execution.returned_row_count = len(rows)
            execution.result_preview = rows[:10]
            truncated = adapter_result.truncated or size_truncated
            execution.result_truncated = truncated
            await self.session.commit()
            logger.info(
                "Query execution succeeded request_id=%r tenant_id=%s user_id=%s connection_id=%s query_execution_id=%s timing_ms=%s truncated=%s",
                request_id,
                tenant_id,
                user_id,
                connection_id,
                execution.id,
                elapsed,
                truncated,
            )
            return SafeQueryResult(
                query_execution_id=execution.id,
                normalized_query=sanitized_sql(validation.normalized_sql or "SELECT"),
                columns=adapter_result.columns,
                rows=tuple(rows),
                row_count=len(rows),
                truncated=truncated,
                execution_time_ms=elapsed,
                referenced_tables=validation.referenced_tables,
                referenced_columns=validation.referenced_columns,
            )
        except Exception as exc:
            await self.session.rollback()
            current = await self.session.get(QueryExecution, execution.id)
            if current is not None:
                current.execution_status = (
                    "timeout" if isinstance(exc, asyncio.TimeoutError) else "failed"
                )
                current.error_code = (
                    "TIMEOUT"
                    if isinstance(exc, asyncio.TimeoutError)
                    else "QUERY_EXECUTION_FAILED"
                )
                current.error_message = "Query execution failed safely"
                await self.session.commit()
            logger.warning(
                "Query execution failed request_id=%r tenant_id=%s user_id=%s connection_id=%s query_execution_id=%s error_code=%s",
                request_id,
                tenant_id,
                user_id,
                connection_id,
                execution.id,
                "TIMEOUT"
                if isinstance(exc, asyncio.TimeoutError)
                else "QUERY_EXECUTION_FAILED",
            )
            raise SafeQueryRejectedError from exc
