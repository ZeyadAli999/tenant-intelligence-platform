"""Deterministic provider available only through explicit test injection."""

import re

from services.llm.base import LLMProvider
from services.llm.schemas import (
    DocumentGroundedAnswer,
    DocumentQueryPlan,
    GroundedAnswer,
    HybridGroundedAnswer,
    ProviderResult,
    ProviderUsage,
    RequestClassification,
    SourceSelectionContext,
    SQLProposal,
)


class FakeLLMProvider(LLMProvider):
    model = "fake-phase3c-v1"

    async def classify(
        self,
        question: str,
        history: tuple[str, ...],
        source_selection: SourceSelectionContext,
    ) -> ProviderResult[RequestClassification]:
        text = question.casefold()
        if "document" in text or "uploaded file" in text:
            intent = (
                "hybrid"
                if any(term in text for term in ("database", "customer", "invoice"))
                else "document"
            )
        elif any(term in text for term in ("what can you do", "hello", "help")):
            intent = "general"
        elif any(
            term in text for term in ("which one", "that one", "something", "ambiguous")
        ):
            return self._result(
                RequestClassification(
                    intent="clarification",
                    confidence=0.45,
                    clarification_question="Which database information would you like me to retrieve?",
                    short_reason="ambiguous request",
                )
            )
        else:
            intent = "database"
        return self._result(
            RequestClassification(
                intent=intent,
                confidence=0.99,
                clarification_question=None,
                short_reason=f"{intent} request",
            )
        )

    async def propose_sql(
        self,
        question: str,
        schema: str,
        source_selection: SourceSelectionContext | None = None,
    ) -> ProviderResult[SQLProposal]:
        text = question.casefold()
        if "pg_catalog" in text:
            sql = "SELECT usename FROM pg_catalog.pg_user"
        elif "drop table" in text or "after the select" in text:
            sql = "SELECT id FROM business.customers; DROP TABLE business.customers"
        elif "database password" in text or "password" in text:
            sql = "SELECT password FROM business.customers"
        elif "hidden table" in text or "orders" in text:
            sql = "SELECT id FROM business.orders"
        elif "tax" in text or "identifier" in text:
            sql = "SELECT tax_identifier AS protected_value FROM business.customers"
        elif re.search(r"\bcount\b", text) or "how many" in text:
            sql = "SELECT COUNT(id) AS customer_count FROM business.customers"
        elif "average" in text:
            sql = "SELECT AVG(id) AS average_customer_id FROM business.customers"
        elif "minimum" in text:
            sql = "SELECT MIN(id) AS minimum_customer_id FROM business.customers"
        elif "maximum" in text:
            sql = "SELECT MAX(id) AS maximum_customer_id FROM business.customers"
        elif "country" in text or "region" in text:
            sql = "SELECT id, country FROM business.customers ORDER BY id"
        else:
            sql = "SELECT id, country FROM business.customers ORDER BY id"
        return self._result(
            SQLProposal(
                action="generate_sql",
                sql=sql,
                clarification_question=None,
                short_description="deterministic SQL proposal",
                proposed_tables=["business.customers"],
                proposed_columns=[],
            )
        )

    async def repair_sql(
        self,
        question: str,
        schema: str,
        previous_sql: str,
        error_codes: tuple[str, ...],
    ) -> ProviderResult[SQLProposal]:
        return await self.propose_sql(
            question.replace("syntax error", ""), schema, SourceSelectionContext()
        )

    async def generate_answer(
        self, question: str, result: dict[str, object]
    ) -> ProviderResult[GroundedAnswer]:
        count = int(result.get("row_count", 0))
        warnings = ["Results were truncated."] if result.get("truncated") else []
        answer = (
            "No matching rows were returned."
            if count == 0
            else f"The approved database query returned {count} row(s)."
        )
        return self._result(
            GroundedAnswer(
                answer=answer,
                warnings=warnings,
                result_summary_type="zero_rows"
                if count == 0
                else ("truncated" if warnings else "rows"),
            )
        )

    async def rewrite_document_query(
        self, question: str, history: tuple[str, ...]
    ) -> ProviderResult[DocumentQueryPlan]:
        return self._result(
            DocumentQueryPlan(
                search_query=question,
                key_terms=question.casefold().split()[:10],
                answer_language="en",
                short_reason="deterministic document search",
            )
        )

    async def generate_document_answer(
        self, question: str, result: dict[str, object]
    ) -> ProviderResult[DocumentGroundedAnswer]:
        evidence = list(result.get("evidence", []))
        if not evidence:
            return self._result(
                DocumentGroundedAnswer(
                    answer="I could not find sufficient authorized document evidence.",
                    warnings=["Insufficient document evidence."],
                    used_evidence_ids=[],
                    insufficient_evidence=True,
                )
            )
        identifiers = [str(item["id"]) for item in evidence if isinstance(item, dict)]
        return self._result(
            DocumentGroundedAnswer(
                answer=f"The authorized documents supplied {len(identifiers)} relevant evidence item(s).",
                warnings=[],
                used_evidence_ids=identifiers,
                insufficient_evidence=False,
            )
        )

    async def generate_hybrid_answer(
        self, question: str, result: dict[str, object]
    ) -> ProviderResult[HybridGroundedAnswer]:
        identifiers = [
            str(item["id"])
            for item in result.get("evidence", [])
            if isinstance(item, dict) and "id" in item
        ]
        return self._result(
            HybridGroundedAnswer(
                answer=f"The approved database and documents supplied {len(identifiers)} grounded evidence item(s).",
                warnings=[],
                used_evidence_ids=identifiers,
                insufficient_evidence=not identifiers,
            )
        )

    def _result(self, value):
        return ProviderResult(
            value=value, model=self.model, usage=ProviderUsage(10, 10, 1)
        )
