"""Mask sensitive outputs before return, persistence, logging, or future prompts."""

import hashlib
import hmac
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


class ResultMasker:
    def __init__(
        self, key: str, *, max_cell_length: int, max_result_bytes: int
    ) -> None:
        self.key = key.encode()
        self.max_cell_length = max_cell_length
        self.max_result_bytes = max_result_bytes

    def mask_rows(
        self,
        columns: tuple[str, ...],
        rows: tuple[dict[str, object], ...],
        plan: tuple[str | None, ...],
    ) -> tuple[list[dict[str, object]], bool]:
        if len(columns) != len(plan) or len(columns) != len(set(columns)):
            raise ValueError("Unsafe result-column metadata")
        output: list[dict[str, object]] = []
        size = 2
        truncated = False
        for row in rows:
            if tuple(row) != columns:
                raise ValueError("Result columns do not match the masking plan")
            safe: dict[str, object] = {}
            for position, (name, value) in enumerate(row.items()):
                normalized = self._normalize(value)
                mask_type = plan[position]
                safe[name] = (
                    self._mask(normalized, mask_type) if mask_type else normalized
                )
            encoded = json.dumps(
                safe, separators=(",", ":"), ensure_ascii=True
            ).encode()
            if size + len(encoded) > self.max_result_bytes:
                truncated = True
                break
            size += len(encoded) + 1
            output.append(safe)
        return output, truncated

    def _normalize(self, value: object) -> object:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, (date, datetime, UUID, Decimal)):
            value = str(value)
        elif isinstance(value, bytes):
            value = "[binary removed]"
        elif not isinstance(value, (str, list, dict)):
            value = str(value)
        if isinstance(value, str) and len(value) > self.max_cell_length:
            return value[: self.max_cell_length] + "…"
        return value

    def _mask(self, value: object, mask_type: str) -> object:
        if mask_type == "null":
            return None
        if mask_type == "redact":
            return "***"
        rendered = "" if value is None else str(value)
        if mask_type == "partial":
            return "***" if len(rendered) <= 4 else f"{rendered[:2]}***{rendered[-2:]}"
        if mask_type == "hash":
            digest = hmac.new(self.key, rendered.encode(), hashlib.sha256).hexdigest()
            return f"hmac-sha256:{digest}"
        return "***"
