#!/usr/bin/env bash
# One-Command Reviewer Setup Script for Tenant Intelligence Copilot (Unix/macOS Bash).
# Configures environment secrets, builds Docker services, applies migrations,
# and bootstraps the Tenant Administrator without host Python dependencies.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

TENANT_NAME="${TENANT_NAME:-Instructor Evaluation}"
TENANT_CODE="${TENANT_CODE:-instructor-review}"
ADMIN_EMAIL="${ADMIN_EMAIL:-instructor@demo.example}"
ADMIN_FULL_NAME="${ADMIN_FULL_NAME:-Instructor Reviewer}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
GROQ_API_KEY="${GROQ_API_KEY:-}"
NON_INTERACTIVE="${NON_INTERACTIVE:-0}"

generate_secret() {
  local bytes="${1:-32}"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes($bytes)).rstrip(b'=').decode())"
  elif command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 "$bytes" | tr '+/' '-_' | tr -d '=\n'
  else
    head -c 64 /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 48 | head -n 1
  fi
}

is_placeholder() {
  local val="$1"
  if [ -z "$val" ]; then return 0; fi
  local lower
  lower="$(echo "$val" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    replace-*|change-me*|changeme*|your-*) return 0 ;;
    *) return 1 ;;
  esac
}

is_groq_valid() {
  local val="$1"
  if is_placeholder "$val"; then return 1; fi
  if [ "${#val}" -lt 20 ]; then return 1; fi
  return 0
}

set_env_var() {
  local file="$1"
  local key="$2"
  local val="$3"
  if [ ! -f "$file" ]; then touch "$file"; fi
  if grep -q "^\s*${key}\s*=" "$file"; then
    sed -i.bak "s|^\s*${key}\s*=.*|${key}=${val}|" "$file" && rm "${file}.bak"
  else
    echo "${key}=${val}" >> "$file"
  fi
}

get_env_var() {
  local file="$1"
  local key="$2"
  if [ -f "$file" ]; then
    grep "^\s*${key}\s*=" "$file" | head -n 1 | cut -d '=' -f 2- | tr -d '\r"'
  fi
}

echo "======================================================================"
echo "TENANT INTELLIGENCE COPILOT — REVIEWER SETUP"
echo "======================================================================"

# Stage 1: Checking prerequisites
echo "[Stage 1/7] Checking prerequisites..."
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is required but not found in PATH. Please install Docker." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: Docker Compose v2 is required but 'docker compose' failed." >&2
  exit 1
fi

if [ ! -f "docker-compose.yml" ] || [ ! -f ".env.example" ]; then
  echo "Error: Required project files not found in $REPO_ROOT" >&2
  exit 1
fi

# Stage 2: Preparing configuration
echo "[Stage 2/7] Preparing configuration..."
ENV_PATH="$REPO_ROOT/.env"
if [ ! -f "$ENV_PATH" ]; then
  cp "$REPO_ROOT/.env.example" "$ENV_PATH"
  echo "Created .env from .env.example"
fi

JWT_SECRET="$(get_env_var "$ENV_PATH" "JWT_SECRET")"
if is_placeholder "$JWT_SECRET" || [ "${#JWT_SECRET}" -lt 32 ]; then
  NEW_JWT="$(generate_secret 48)"
  set_env_var "$ENV_PATH" "JWT_SECRET" "$NEW_JWT"
  echo "Generated secure JWT_SECRET"
fi

CONN_KEY="$(get_env_var "$ENV_PATH" "CONNECTION_ENCRYPTION_KEY")"
if is_placeholder "$CONN_KEY"; then
  NEW_CONN="$(generate_secret 32)"
  set_env_var "$ENV_PATH" "CONNECTION_ENCRYPTION_KEY" "$NEW_CONN"
  echo "Generated secure CONNECTION_ENCRYPTION_KEY"
fi

MASK_KEY="$(get_env_var "$ENV_PATH" "RESULT_MASKING_KEY")"
if is_placeholder "$MASK_KEY" || [ "${#MASK_KEY}" -lt 32 ]; then
  NEW_MASK="$(generate_secret 48)"
  set_env_var "$ENV_PATH" "RESULT_MASKING_KEY" "$NEW_MASK"
  echo "Generated secure RESULT_MASKING_KEY"
fi

CURRENT_GROQ="$(get_env_var "$ENV_PATH" "GROQ_API_KEY")"
if [ -n "$GROQ_API_KEY" ]; then
  set_env_var "$ENV_PATH" "GROQ_API_KEY" "$GROQ_API_KEY"
  CURRENT_GROQ="$GROQ_API_KEY"
fi

if ! is_groq_valid "$CURRENT_GROQ"; then
  if [ "$NON_INTERACTIVE" = "1" ]; then
    echo "Error: GROQ_API_KEY is missing or invalid in .env and script is in NonInteractive mode." >&2
    exit 1
  fi
  echo ""
  echo "A valid Groq API key is required for the AI Text-to-SQL and document-chat features."
  printf "Please enter your GROQ_API_KEY: "
  stty -echo
  read -r ENTERED_GROQ
  stty echo
  echo ""
  if ! is_groq_valid "$ENTERED_GROQ"; then
    echo "Error: Invalid GROQ_API_KEY entered. Key must be at least 20 characters and non-placeholder." >&2
    exit 1
  fi
  set_env_var "$ENV_PATH" "GROQ_API_KEY" "$ENTERED_GROQ"
  echo "GROQ_API_KEY updated successfully."
fi

if [ -z "$ADMIN_PASSWORD" ]; then
  if [ "$NON_INTERACTIVE" = "1" ]; then
    echo "Error: ADMIN_PASSWORD parameter is required in NonInteractive mode." >&2
    exit 1
  fi
  printf "Enter desired Administrator password (min 12 chars): "
  stty -echo
  read -r ADMIN_PASSWORD
  stty echo
  echo ""
fi

if [ -z "$ADMIN_PASSWORD" ] || [ "${#ADMIN_PASSWORD}" -lt 12 ]; then
  echo "Error: Administrator password must be at least 12 characters." >&2
  exit 1
fi

if ! docker compose config --quiet; then
  echo "Error: Docker Compose configuration validation failed. Please check .env values." >&2
  exit 1
fi

# Stage 3: Building services
echo "[Stage 3/7] Building and starting services..."
docker compose up --build -d

# Stage 4 & 5: Waiting for readiness
echo "[Stage 4/7] Waiting for database and services..."
echo "[Stage 5/7] Applying migrations and verifying API readiness..."

TIMEOUT=120
ELAPSED=0
BACKEND_READY=0
FRONTEND_READY=0

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
  if [ "$BACKEND_READY" -eq 0 ]; then
    if curl -sf "http://localhost:8000/api/health/ready" | grep -q '"status":"ready"'; then
      BACKEND_READY=1
    fi
  fi
  if [ "$FRONTEND_READY" -eq 0 ]; then
    if curl -sf "http://localhost:3000/api/health" | grep -q '"status":"ok"'; then
      FRONTEND_READY=1
    fi
  fi
  if [ "$BACKEND_READY" -eq 1 ] && [ "$FRONTEND_READY" -eq 1 ]; then
    break
  fi
  sleep 3
  ELAPSED=$((ELAPSED + 3))
done

if [ "$BACKEND_READY" -ne 1 ] || [ "$FRONTEND_READY" -ne 1 ]; then
  echo "Error: Services did not report ready within $TIMEOUT seconds." >&2
  echo "Diagnostic commands:" >&2
  echo "  docker compose logs api" >&2
  echo "  docker compose logs frontend" >&2
  echo "  docker compose ps" >&2
  exit 1
fi

# Stage 6: Provisioning workspace administrator
echo "[Stage 6/7] Provisioning workspace administrator..."
export BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD"
trap 'unset BOOTSTRAP_ADMIN_PASSWORD; ADMIN_PASSWORD=""' EXIT INT TERM

if ! docker compose exec -T -e BOOTSTRAP_ADMIN_PASSWORD api python -m scripts.bootstrap \
    --tenant-name "$TENANT_NAME" \
    --tenant-code "$TENANT_CODE" \
    --admin-email "$ADMIN_EMAIL" \
    --admin-full-name "$ADMIN_FULL_NAME"; then
  echo "Error: Administrator provisioning failed safely." >&2
  unset BOOTSTRAP_ADMIN_PASSWORD
  ADMIN_PASSWORD=""
  exit 1
fi

unset BOOTSTRAP_ADMIN_PASSWORD
ADMIN_PASSWORD=""
trap - EXIT INT TERM

# Stage 7: Verifying login readiness
echo "[Stage 7/7] Verifying login readiness..."
if ! curl -sf "http://localhost:8000/api/health/live" >/dev/null; then
  echo "Error: API liveness check failed after bootstrap." >&2
  exit 1
fi

echo ""
echo "======================================================================"
echo "INSTRUCTOR EVALUATION WORKSPACE READY"
echo "======================================================================"
echo "Application URL:         http://localhost:3000"
echo "API Documentation URL:   http://localhost:8000/docs"
echo "Tenant Code:             $TENANT_CODE"
echo "Administrator Email:     $ADMIN_EMAIL"
echo "Administrator Full Name: $ADMIN_FULL_NAME"
echo "Password:                (The password supplied in the private document)"
echo "======================================================================"
