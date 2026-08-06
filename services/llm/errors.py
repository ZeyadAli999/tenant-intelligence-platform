"""Sanitized LLM boundary failures."""


class LLMError(RuntimeError):
    code = "LLM_FAILED"


class LLMTimeoutError(LLMError):
    code = "LLM_TIMEOUT"


class LLMRefusalError(LLMError):
    code = "LLM_REFUSAL"


class LLMIncompleteError(LLMError):
    code = "LLM_INCOMPLETE"


class LLMOutputError(LLMError):
    code = "LLM_INVALID_OUTPUT"
