"""Test environment setup performed before application modules are imported."""

import os

os.environ["APP_NAME"] = "Tenant Intelligence"
os.environ["APP_VERSION"] = "1.0.0"
os.environ["API_PREFIX"] = "/api"
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://test_user:test_password@localhost:5432/test_database"
)
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "CRITICAL"
os.environ["JWT_SECRET"] = "unit-test-jwt-key-with-strong-diversity-1234567890"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ACCESS_TOKEN_MINUTES"] = "15"
os.environ["JWT_REFRESH_TOKEN_DAYS"] = "30"
os.environ["CONNECTION_ENCRYPTION_KEY"] = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
os.environ["RESULT_MASKING_KEY"] = "test-result-masking-key-with-strong-entropy-123"
os.environ["ALLOW_PRIVATE_DATABASE_HOSTS"] = "false"
os.environ["GROQ_API_KEY"] = "gsk_test_only_inert_key_12345678901234567890"
os.environ["GROQ_MODEL"] = "openai/gpt-oss-120b"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ROOT_USER"] = "test-root-user"
os.environ["MINIO_ROOT_PASSWORD"] = "test-root-password-strong"
os.environ["MINIO_APP_ACCESS_KEY"] = "test-app-access"
os.environ["MINIO_APP_SECRET_KEY"] = "test-app-secret-strong"
