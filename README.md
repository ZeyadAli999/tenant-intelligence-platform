# Tenant Intelligence

## Instructor Evaluation Access

> [!IMPORTANT]
> The private credentials document is located inside the same Google Drive folder whose link was submitted separately through the Google Form together with the certificates:
>
> **`00 — INSTRUCTOR ACCESS & LOGIN CREDENTIALS`**
>
> This private document contains:
> - The dedicated **Groq API Key** (`GROQ_API_KEY`)
> - The **Administrator Password**
> - The exact instructor tenant and account login information

### Groq API Key Options

The assigned instructor has two valid options:
- **Option 1:** Create and use a personal free Groq API key from [https://console.groq.com/keys](https://console.groq.com/keys).
- **Option 2:** To avoid account creation or if any external issue occurs, use the dedicated instructor-only Groq API key supplied in the private document **`00 — INSTRUCTOR ACCESS & LOGIN CREDENTIALS`**, located inside the same Google Drive folder whose link was submitted separately through the Google Form together with the certificates.

### Quick Setup Steps for the Instructor

1. Clone the repository and open PowerShell in the root directory:
   ```powershell
   cd <path-to-downloaded-repository>
   ```
2. Run the automated reviewer setup script:
   ```powershell
   .\scripts\reviewer-setup.ps1
   ```
3. When securely prompted:
   - Provide your chosen **Groq API Key** (Option 1 or Option 2).
   - Paste the **Administrator Password** from the private document.
4. Open the application in your browser at [http://localhost:3000](http://localhost:3000).
5. Log in using the instructor credentials from the private document:
   - **Tenant Code:** `instructor-review`
   - **Email:** `instructor@demo.example`
   - **Password:** *(the password supplied in the private document)*

---

## Reviewer Quick Start

The canonical reviewer path starts the complete platform (Next.js frontend, FastAPI backend, PostgreSQL, Redis, MinIO, and Dramatiq worker) in Docker with **one command**. Host Python or Node installation is **not required**.

### Prerequisites

- **Docker Desktop** with Docker Compose v2+ (running)
- A valid **Groq Cloud API Key** (provided in the private instructor evaluation document)

### Windows (PowerShell)

1. Clone the repository and open PowerShell in the root directory:
   ```powershell
   cd <path-to-downloaded-repository>
   ```
2. Run the automated reviewer setup script:
   ```powershell
   .\scripts\reviewer-setup.ps1
   ```
3. Enter your **Groq API Key** and desired **Administrator Password** when securely prompted.
4. Open the displayed frontend URL in your browser:
   - **Application URL:** [http://localhost:3000](http://localhost:3000)
   - **API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
5. Log in with:
   - **Tenant Code:** `instructor-review`
   - **Email:** `instructor@demo.example`
   - **Password:** *(the password supplied in the private document)*

### Linux / macOS (Bash)

1. Clone the repository and open terminal in the root directory:
   ```bash
   cd <path-to-downloaded-repository>
   ```
2. Run the automated reviewer setup script:
   ```bash
   chmod +x ./scripts/reviewer-setup.sh
   ./scripts/reviewer-setup.sh
   ```
3. Enter your **Groq API Key** and desired **Administrator Password** when prompted.
4. Open [http://localhost:3000](http://localhost:3000) and log in with `instructor-review` / `instructor@demo.example`.

---

### Startup Details & Service Health

- **First Run Duration:** Approximately 2 to 5 minutes (downloads base images and builds containers). Subsequent starts take under 15 seconds.
- **Frontend Health Endpoint:** `http://localhost:3000/api/health`
- **Backend Liveness Endpoint:** `http://localhost:8000/api/health/live`
- **Backend Readiness Endpoint:** `http://localhost:8000/api/health/ready`
- **Re-running Setup:** Both setup scripts are fully **idempotent**. You can re-run `.\scripts\reviewer-setup.ps1` at any time without creating duplicate users or losing database state.

### Troubleshooting & Diagnostic Commands

- **Inspect Service Liveness:**
  ```powershell
  docker compose ps
  ```
- **View Container Logs:**
  ```powershell
  docker compose logs api
  docker compose logs frontend
  ```
- **Groq API Key Requirement:**
  > [!IMPORTANT]
  > A valid Groq Cloud API key (`GROQ_API_KEY`) is required for application startup. If missing or invalid:
  > - **Missing Key:** Setup script will prompt for it interactively.
  > - **Invalid/Rate-Limited Key:** Backend logs will report `401 Unauthorized` or `429 Rate Limit` from Groq Cloud. Update `GROQ_API_KEY` in `.env` and run `docker compose restart api`.

---

### Evidence-Based Demo Data Matrix

After clean setup, the following initial state is active:

| Demo Item | Exists After Clean Setup | Creation Source | Reviewer Action Needed |
| --- | --- | --- | --- |
| **Tenant (`instructor-review`)** | Yes | `scripts/reviewer-setup.ps1` / `scripts/bootstrap.py` | None (Automatic) |
| **Administrator (`instructor@demo.example`)** | Yes | `scripts/reviewer-setup.ps1` / `scripts/bootstrap.py` | Log in using credentials from private document |
| **Platform DB & Migrations** | Yes | Docker API container startup (`alembic upgrade head`) | None (Automatic) |
| **Customer DB Connection** | No | Tenant Administrator | Connect customer database via `/databases` workspace |
| **Table & Column Permissions** | No | Tenant Administrator | Configure table/column access rules via `/permissions` |
| **Document Knowledge Base** | No | Tenant Administrator / User | Upload PDF/DOCX document via `/knowledge` workspace |
| **Chat Conversations** | No | Authenticated User | Click **New Conversation** via `/chat` workspace |

---

## Phase 5B chat workspace

The Next.js frontend now includes the production-oriented Phase 5B Chat

Workspace and Phase 5D Database Management surface in `frontend/`. It provides persisted tenant-owned conversations,
immutable source selection, progressive SSE answers, cancellation, safe SQL
inspection, database/document citations, usage metadata, responsive
conversation and evidence drawers, and complete database connection management,
schema discovery, schema exploration, table inspection, and permitted schema access.
Permissions and Settings are production-quality workspaces for managing database/column/row permissions and tenant/account settings.

The browser never receives tokens in JavaScript-visible storage. Next.js Route
Handlers proxy authentication to FastAPI and keep access and refresh tokens in
separate HttpOnly, SameSite=Lax cookies (`Secure` in production). A failed API
request is refreshed once; refresh failure clears the session and sends the user
back to `/login`. The backend URL is server-only. The strict BFF allowlists only
the methods and paths needed for health, conversations, chat streaming, message
evidence, and source discovery. Browser Authorization headers and client tenant
identifiers are rejected or discarded; the BFF injects the HttpOnly session
token.

Local HTTP Compose explicitly sets `COOKIE_SECURE=false`; production deployments
must omit that override (or set it to `true`) and terminate HTTPS before Next.js.

### Frontend setup

```bash
cd frontend
copy .env.example .env.local
npm ci
npm run dev
```

For host development, set `BACKEND_INTERNAL_URL=http://127.0.0.1:8000` in the
local frontend environment. Do not put Groq, JWT, database, or storage secrets in
frontend environment files. Open the frontend at `http://localhost:3000`; the
backend Swagger UI remains at `http://localhost:8000/docs`.

Docker starts the complete stack with:

```bash
docker compose up --build -d
```

The frontend container reaches FastAPI at `http://api:8000` and exposes a health
endpoint at `http://localhost:3000/api/health`.

Routes are `/login`, `/dashboard`, `/chat`, `/knowledge`, `/databases`, `/users`,
`/permissions`, and `/settings`. All routes are functionally complete and backed by real backend/BFF contracts without mock data.

### Frontend capabilities through Phase 5D

The product interface now uses a consistent Tenant Intelligence identity,
two-column desktop sign-in composition, real platform-readiness display,
grouped application navigation, and a structured dashboard showing the live
workspace identity, system health, governed workflow, platform capability
areas, verified security controls, and getting-started path. Chat adds a
three-pane desktop workspace, mobile conversation/evidence sheets, source-aware
conversation creation, keyboard-safe composition, ordered incremental SSE
parsing, persisted-history reconciliation, and explicit failed/cancelled states.
Databases adds connection listing, connection creation (requiring password),
connection editing (omitting blank password to preserve existing secret), connection deletion,
SSRF-resistant connection testing, schema synchronization, schema exploration, table inspection,
and allowed-schema inspection workflows for tenant administrators.
Assistant text is rendered as plain text; raw HTML, prompts, tokens, credentials,
and unvalidated provider data are never rendered. Responsive and Axe checks
cover desktop, tablet, and mobile layouts in both light and dark themes.

Conversation source selections are fixed at creation. General conversations use
no source, database conversations select at most one active tested connection,
document conversations select up to ten active knowledge bases, and hybrid
conversations combine those limits. The evidence inspector shows only
backend-approved normalized SQL and citations. Database citations identify
approved tables and columns; document citations show safe file and location
metadata without exposing hidden chunks.

Quality checks:

```bash
cd frontend
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
npm run test:e2e
```

The configured Playwright acceptance suite uses disposable real identities:

```bash
set PLAYWRIGHT_EXTERNAL_SERVER=1
set E2E_TENANT_CODE=<disposable-tenant>
set E2E_USER_EMAIL=<disposable-user>
set E2E_USER_PASSWORD=<temporary-password>
npm run test:e2e -- --workers=1
```

Those values are local test inputs only and must never be committed or packaged.
Ordinary Vitest tests make no external Groq calls. Real Groq browser acceptance
is explicit, minimal, and runs only with the existing secured backend runtime.

If sign-in reports service unavailability, verify FastAPI's
`/api/health/live` and `/api/health/ready` endpoints and confirm the server-only
`BACKEND_INTERNAL_URL` matches the runtime environment. Theme preference is the
only value persisted in browser storage.

This repository implements Phase 1 through Phase 4 of the backend assignment:

- FastAPI, PostgreSQL, async SQLAlchemy 2, Alembic, Docker, health probes, request IDs,
  and safe error handling.
- Authentication, tenants, users, roles, tenant-isolated administration, Argon2id
  passwords, signed JWTs, and rotating refresh-token sessions.
- Tenant-isolated runtime PostgreSQL connections, AES-256-GCM credential encryption,
  SSRF-resistant connection testing, catalog-only schema discovery, and metadata caching.
- Explicit table/column permissions, a strict row-filter DSL, SQLGlot AST validation and
  authorization-filter injection, controlled read-only execution, masking, and audit traces.
- Groq Cloud strict structured LLM calls, deterministic allowed-schema retrieval,
  LangGraph database-chat orchestration, owner-scoped conversations/messages, grounded
  masked answers, safe SQL metadata, and SSE streaming.
- Tenant-isolated knowledge bases, bounded uploads, MinIO object storage, Dramatiq/Redis
  processing, structure-aware parsers and chunks, local FastEmbed embeddings, pgvector
  plus PostgreSQL lexical retrieval, grounded document answers, and durable citations.
- Hybrid database/document orchestration that merges only masked database results and
  authorized document chunks, validates evidence IDs, and streams one grounded answer.

Current limitations: PostgreSQL is the only customer database adapter. OCR, scanned-PDF
recognition, images, legacy Office formats, macro-enabled Office documents, and document
sharing beyond owner/tenant-admin policy are not supported. Embeddings are CPU-local;
the first real processing run may need to download the configured model. Qdrant is not
used because tenant-filtered pgvector and PostgreSQL full-text search are implemented.

## Multi-Tenancy Model and Administrative Scope

### Tenant Definition

A tenant represents one isolated organization or workspace using the shared platform.

Each tenant owns tenant-scoped resources such as:

- users
- roles
- permissions
- database connections
- catalog metadata
- conversations
- uploaded documents
- document-processing records
- knowledge records
- tenant configuration

The platform may serve multiple organizations while preserving strict logical isolation between them.

Tenant identity is resolved from the authenticated session and trusted backend context.

The browser is never allowed to choose, override, or submit an arbitrary tenant identity.

### Tenant Administrator Scope

The current Administrator role is a Tenant Administrator.

A Tenant Administrator can manage resources belonging only to the currently authenticated tenant, including:

- tenant users
- user roles
- database permissions
- masking rules
- row-level filters
- connected customer databases
- tenant documents
- tenant conversations

A Tenant Administrator is not a platform-wide Super Administrator.

The current Administrator cannot create, modify, suspend, or manage unrelated organizations.

### Why Tenant Profile is Read-Only

The Tenant Profile page intentionally presents organization identity and isolation context as read-only information.

The current backend does not expose a secure tenant-update endpoint.

Displaying editable controls without a real audited backend workflow would create fake functionality and could weaken tenant isolation.

The organization display name may become editable in a future release through a dedicated Administrator-only backend endpoint with:

- authorization
- validation
- audit logging
- safe conflict handling
- tenant isolation enforcement

The current release intentionally avoids pretending that unsupported editing exists.

### Why Tenant UUID is Not Editable

The tenant UUID is the permanent internal identifier for the organization.

It is used to scope tenant-owned records such as:

- users
- roles
- permissions
- conversations
- documents
- database connections
- catalog metadata

The UUID must remain stable even if the organization display name changes.

Allowing the browser or a normal Administrator to modify this identifier could break references or create a tenant-isolation vulnerability.

The tenant UUID must never be treated as a normal editable profile field.

### Why Tenant Code is Not Casually Editable

The tenant code is a canonical unique identifier.

It may be referenced by:

- provisioning workflows
- integration configuration
- routing logic
- audit records
- operational tooling
- external references

Changing it safely would require a dedicated backend workflow with:

- global uniqueness validation
- authorization
- conflict handling
- audit logging
- migration of dependent references

Therefore, it is displayed as read-only in the current release.

### Why There is No Create Tenant Button

Creating a tenant is a platform-provisioning operation, not a normal Tenant Administrator operation.

A complete Create Tenant workflow would require:

1. A Platform Administrator or Super Administrator role.
2. Globally unique tenant-code validation.
3. Creation of the tenant's first Administrator.
4. Initialization of default roles and permission policies.
5. Storage and data-isolation setup.
6. Default configuration provisioning.
7. Audit logging.
8. Activation, suspension, and lifecycle controls.
9. Protection against unauthorized or unlimited tenant creation.
10. Secure rollback if provisioning fails.

This platform-administration layer is intentionally outside the current project scope.

The absence of a simple Create Tenant button is therefore an explicit security and scope decision, not an overlooked interface feature.

### Current Release Scope

The evaluated release uses a provisioned tenant and demonstrates:

- tenant-scoped authentication
- tenant-scoped users and roles
- tenant-scoped database connections
- table permissions
- column permissions
- data masking
- row-level filtering
- connected database catalogs
- document knowledge
- conversations
- session isolation

The architecture is designed so additional tenants can later be provisioned through a separate platform-administration layer without weakening the current tenant-security model.

### Reviewer Summary

"The current Administrator is a Tenant Administrator, not a platform-wide Super Administrator. Tenant identity is part of the platform security boundary and is intentionally read-only in this release. Creating a new tenant requires a separate audited provisioning workflow, so adding a simple Create Tenant button would be incomplete and insecure."

## Architecture

```mermaid
flowchart LR
    Client["API client"] --> Middleware["Request ID and safe errors"]
    Middleware --> API["FastAPI /api router"]
    API --> Auth["Authentication service"]
    API --> Context["Verified tenant context"]
    Context --> Admin["Tenant-admin users, roles, connections"]
    Context --> Read["Tenant-scoped cached metadata"]
    Context --> Permission["Effective permission resolver"]
    Context --> Chat["Owner-scoped conversations and chat"]
    Chat --> Graph["LangGraph classifier and source routing"]
    Graph --> Groq["Groq Cloud: openai/gpt-oss-120b"]
    Graph --> Retrieval["Tenant-filtered hybrid document retrieval"]
    Retrieval --> Vector["pgvector + PostgreSQL FTS"]
    Worker["Dramatiq worker"] --> Parser["PDF DOCX XLSX CSV TXT parsers"]
    Parser --> Embed["Local FastEmbed 384 dimensions"]
    Embed --> Vector
    API --> MinIO["Private MinIO objects"]
    API --> Redis["Redis identifier-only queue"]
    Redis --> Worker
    Graph --> Schema["Deterministic allowed-schema retriever"]
    Schema --> Generator["Structured SQL proposal"]
    Generator --> Validator
    Permission --> Validator["SQLGlot validation and AST row filters"]
    Validator --> Executor["Read-only bounded executor and masking"]
    Executor --> Answer["Grounded masked answer"]
    Answer --> Chat
    Admin --> Service["Connection orchestration"]
    Service --> Registry["Generic adapter registry"]
    Registry --> PG["PostgreSQL adapter"]
    PG --> Customer["Customer PostgreSQL catalogs only"]
    Auth --> Security["Argon2id and signed JWTs"]
    Auth --> Repository["Identity repository"]
    Admin --> Repository
    Context --> Repository
    Repository --> DB["Application PostgreSQL"]
    Alembic["Alembic migrations"] --> DB
```

Routes and orchestration depend on the generic adapter interface. PostgreSQL is the only
registered adapter; MySQL, SQL Server, and Oracle are rejected with HTTP 400.
A future adapter implements `DatabaseAdapter` and is registered in `AdapterRegistry`,
without route changes. The platform database stores only connection metadata, encrypted
credentials, and discovered catalog metadata—never customer business rows.

The Phase 3B authorization boundary remains shared by allowed-schema generation, SQL
validation, AST rewriting, and controlled execution. Phase 3C calls that boundary from
LangGraph; there is deliberately no public raw-SQL execution endpoint.

## Security model

The full security rationale is in `SECURITY.md`. The central rules are:

- Login requires `tenant_code` because email addresses are unique inside a tenant, not
  globally. The same email may validly belong to multiple tenants.
- Protected requests never accept `tenant_id`. Tenant identity comes only from a
  signature-verified access token and matching active database records.
- Every protected request revalidates the user, tenant membership, user status, tenant
  status, administrator flag, and roles. Deactivation or deletion takes effect without
  waiting for the access token to expire.
- Passwords use Argon2id and are never stored directly.
- Access and refresh tokens have distinct required types and cannot be interchanged.
- Only a SHA-256 digest of each refresh token is stored. Rotation revokes the used token;
  detected replay revokes every active token in that rotation family.
- Database constraints pair `tenant_id` with both users and roles in `user_roles`, so a
  cross-tenant role assignment is rejected even if service validation is bypassed.
- Request bodies forbid unknown fields. Supplying `tenant_id` to a protected create or
  update operation returns HTTP 400.
- SQL parameter values are hidden from logs. Passwords, password hashes, JWT secrets,
  raw tokens, and complete authorization headers must never be logged.
- Customer passwords use AES-256-GCM with a new random 96-bit nonce per encryption and
  a versioned `v1` payload bound to the tenant and connection IDs as authenticated data.
- Hosts are resolved before use and again immediately before connecting. Special-purpose
  addresses are always blocked; private destinations require an explicit setting.
- Query authority comes only from stored permissions. Tenant administrators receive no
  implicit customer-data access, and future generated SQL cannot grant itself access.
- Mandatory row filters are parameterized SQLGlot AST nodes injected after validation.
  Sensitive values are masked before service return or audit-preview storage.

## Prerequisites

Choose one workflow:

- Docker Desktop with Docker Compose, or
- Python 3.12 plus PostgreSQL 16.

## Configuration

Copy the example file:

```powershell
Copy-Item .env.example .env
```

The example JWT value is intentionally rejected. Generate a secret with at least 32
random bytes and replace `JWT_SECRET` before starting the application:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not paste the generated value into source control, terminal transcripts, tickets, or
logs.

Generate the separate 32-byte connection-encryption key as base64url and keep it only in
the local `.env` or a production secret manager:

```powershell
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode())"
```

| Variable | Purpose | Example/default |
| --- | --- | --- |
| `APP_NAME` | OpenAPI and health service name | `Tenant Intelligence` |
| `APP_VERSION` | Health and OpenAPI version | `1.0.0` |
| `API_PREFIX` | Enforced public API prefix | `/api` |
| `ENVIRONMENT` | Runtime environment | `development` |
| `DEBUG` | Must remain false to prevent traceback responses | `false` |
| `LOG_LEVEL` | Process log threshold | `INFO` |
| `DATABASE_ECHO` | SQL statement logging; parameter values remain hidden | `false` |
| `DATABASE_URL` | Async PostgreSQL URL using `postgresql+asyncpg` | See `.env.example` |
| `JWT_SECRET` | HMAC key; required, non-placeholder, at least 32 bytes | No default |
| `JWT_ALGORITHM` | Explicit symmetric algorithm allowlist | `HS256` |
| `JWT_ACCESS_TOKEN_MINUTES` | Access-token lifetime, 1-60 minutes | `15` |
| `JWT_REFRESH_TOKEN_DAYS` | Refresh-token lifetime, 1-90 days | `30` |
| `CONNECTION_ENCRYPTION_KEY` | Required base64url AES-256 key | No default |
| `ALLOW_PRIVATE_DATABASE_HOSTS` | Permit resolved private customer hosts | `false` |
| `CUSTOMER_DATABASE_CONNECT_TIMEOUT_SECONDS` | Customer connection timeout | `5` |
| `CUSTOMER_DATABASE_COMMAND_TIMEOUT_SECONDS` | Customer catalog command timeout | `5` |
| `GROQ_API_KEY` | Required Groq Cloud secret; no placeholder or default | No default |
| `GROQ_MODEL` | Sole supported Groq-hosted model | `openai/gpt-oss-120b` |
| `GROQ_TIMEOUT_SECONDS` | Per-Groq-call timeout | `30` |
| `GROQ_MAX_OUTPUT_TOKENS` | Structured response output bound | `1200` |
| `GROQ_MAX_RETRIES` | Bounded transient-failure retry count | `2` |
| `LLM_SCHEMA_MAX_TABLES` | Allowed-schema prompt table cap | `8` |
| `LLM_SCHEMA_MAX_COLUMNS` | Allowed-schema prompt column cap | `60` |
| `CHAT_MAX_MESSAGE_LENGTH` | User message length limit | `4000` |
| `CHAT_HISTORY_MESSAGES` | Prior safe-message history cap | `10` |
| `CHAT_GRAPH_RECURSION_LIMIT` | LangGraph recursion bound | `20` |
| `POSTGRES_DB` | Compose database name | `text_to_sql` |
| `POSTGRES_USER` | Compose database user | `text_to_sql` |
| `POSTGRES_PASSWORD` | Compose database password | `change-me` |
| `POSTGRES_PORT` | PostgreSQL host port | `5432` |
| `API_PORT` | FastAPI host port | `8000` |

Missing or placeholder JWT secrets and malformed encryption keys fail configuration.
Pydantic error output is configured not to echo rejected secret values.

## Run with Docker Compose

After creating `.env`, replacing development passwords and secrets, and adding a local
`GROQ_API_KEY`:

```powershell
docker compose up --build
```

Compose waits for PostgreSQL, runs `alembic upgrade head`, and starts the API. OpenAPI
documentation is available at <http://localhost:8000/docs> and the schema at
<http://localhost:8000/openapi.json>.

Stop services without deleting the database volume:

```powershell
docker compose down
```

## Run locally

```powershell
docker compose up -d postgres
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Replace JWT_SECRET and development passwords in .env.
alembic upgrade head
uvicorn app.main:app --reload
```

The `.env.example` database URL uses `localhost`, which is correct when FastAPI runs on
the host. Compose supplies the internal `postgres` hostname to the API container.

## Migrations

```powershell
alembic heads
alembic history
alembic upgrade head
alembic current
```

Phase 2 migration `20260803_0002` creates tenants, users, roles, tenant-consistent
user-role assignments, and hashed refresh-token sessions. Its downgrade removes only
those Phase 2 tables and returns to the Phase 1 baseline:

```powershell
alembic downgrade 20260803_0001
alembic upgrade head
```

Do not run downgrades against production without a reviewed backup and recovery plan.

Phase 3A migration `20260803_0003` creates `database_connections`,
`database_schemas`, `database_tables`, and `database_columns`, including composite
tenant-aware foreign keys and PostgreSQL JSONB fields.

Phase 3B migration `20260803_0004` adds `table_permissions`, `column_permissions`, and
`query_executions`. Composite tenant-aware foreign keys bind every permission to its
subject, connection, table, and column; partial unique indexes prevent duplicate user or
role grants for a table.

## Runtime customer database workflow

Mutation, testing, and synchronization require a tenant administrator. Any authenticated
tenant user may list safe connection metadata and cached metadata in their tenant. A
cross-tenant identifier always appears as HTTP 404, and no endpoint accepts `tenant_id`.

Create a connection (the password is accepted only here and never returned):

```powershell
$connection = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/database-connections `
  -Headers $headers -ContentType application/json -Body (@{
    name = "Reporting PostgreSQL"; database_type = "postgresql"
    host = "db.example.internal"; port = 5432; database_name = "reporting"
    username = "catalog_reader"; password = "supply-from-a-secret-source"
    ssl_enabled = $true; ssl_settings = @{ mode = "verify-full" }
    connection_options = @{ application_name = "schema-discovery" }
  } | ConvertTo-Json -Depth 4)

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/database-connections/$($connection.id)/test" -Headers $headers
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/database-connections/$($connection.id)/sync-schema" -Headers $headers
Invoke-RestMethod -Uri "http://localhost:8000/api/database-connections/$($connection.id)/schemas?page=1&page_size=50" -Headers $headers
Invoke-RestMethod -Uri "http://localhost:8000/api/database-connections/$($connection.id)/tables?schema_name=public&table_type=table&search=order" -Headers $headers
```

Connection testing decrypts credentials only inside the tester, validates DNS immediately
before connecting, builds the DSN server-side, uses a short-lived `NullPool` engine with
strict timeouts, executes read-only `SELECT 1`, sanitizes the result, and disposes the
engine. Synchronization is allowed only after success and reconciles catalog metadata in
one platform transaction. Existing schemas, tables, and columns retain their UUIDs;
missing tables are disabled and returning tables reuse their original UUID. Missing
columns on a still-present table are removed. It reads PostgreSQL catalogs for schemas, tables/views,
columns, PKs, FKs, and estimates; it never selects customer rows or fills `sample_values`.

Local Compose database names resolve to private container addresses, so integration mode
explicitly enables private destinations. Normal startup retains the secure `false`
default. Never enable this broadly in production without network egress controls.

```powershell
docker compose --env-file .env -f docker-compose.yml -f docker-compose.integration.yml up --build -d
```

## Phase 3B permission and safe-query boundary

### Permission resolution

Access is deny-by-default. A direct user `TablePermission` replaces all role grants for
that table. Otherwise, readable role grants form a union; an unrelated role row with
`can_read=false` cannot cancel another role's grant. Multiple filtered role grants form
an OR of complete grants, while clauses inside one grant form an AND. An unfiltered
readable role grant means that role grants the whole permitted table row set. Removed
roles stop contributing immediately. Disabled metadata is always denied.

Column capabilities are separate: `can_read`, `can_filter`, and `can_aggregate`. If a
table permission has column rows, they are an explicit allowlist. Without column rows,
only non-sensitive columns inherit table read/filter/aggregate access. Sensitive columns
always need an explicit readable grant and a mask (`redact`, `partial`, keyed `hash`, or
`null`). Sensitive tables likewise need an explicit table permission; administrators do
not receive implicit data access. The allowed schema removes hidden object names and FK
relationships whose endpoints are not both visible.

### Row-filter DSL

`row_filter` is versioned backend authorization data, never SQL:

```json
{
  "version": 1,
  "all": [
    {
      "column_id": "11111111-1111-1111-1111-111111111111",
      "operator": "eq",
      "value": {"source": "literal", "value": "Egypt"}
    }
  ]
}
```

Allowed operators are `eq`, `neq`, `in`, `not_in`, `gt`, `gte`, `lt`, `lte`,
`is_null`, and `is_not_null`. Values may be literals or the server-resolved contexts
`current_user_id` and `current_tenant_id`; clients can name a context but cannot supply
its runtime value. Unknown fields, versions, operators, malformed structures,
cross-table columns, and non-filterable columns are rejected. Compilation creates
parameter placeholders and SQLGlot expressions—literal values are never concatenated
into SQL or copied to `QueryExecution.applied_row_filters`.

### Validation, injection, execution, and masking

The PostgreSQL SQLGlot pipeline accepts exactly one comment-free, read-only query and
validates every scope, alias, join, CTE, subquery, and set-operation branch against the
effective schema. It rejects stars, ambiguous or hidden objects, system schemas,
write/DDL/security statements, `SELECT INTO`, locks, `EXPLAIN ANALYZE`, unknown functions,
and unsafe PostgreSQL functions. The explicit safe function allowlist is `ABS`, `AVG`,
`CAST`, `COALESCE`, `COUNT`, `DATE_TRUNC`, `EXTRACT`, `GREATEST`, `LEAST`, `LENGTH`,
`LOWER`, `MAX`, `MIN`, `NULLIF`, `ROUND`, `SUM`, and `UPPER`.

After validation, each protected base-table occurrence is wrapped in a filtered
subquery. This preserves outer-join placement and makes omission, `OR 1=1`, aliases,
CTEs, subqueries, repeated references, and UNION branches unable to weaken mandatory
filters. SQL is then executed through the PostgreSQL adapter using a fresh `NullPool`
engine, a read-only transaction, immediate host revalidation, statement and lock
timeouts, a row sentinel (`maximum + 1`), column/result/cell limits, and unconditional
engine disposal. Result masking happens before return and before the maximum ten-row
audit preview. Hash masking uses keyed HMAC-SHA-256 with `RESULT_MASKING_KEY`.

Masking is provenance-aware and output-position based. `ColumnLineageAnalyzer` walks
SQLGlot scopes and traces every final projection through aliases, CTEs, subqueries,
set-operation positions, casts, scalar/aggregate functions, and compound expressions to
the approved base-column UUIDs that contribute to it. Renaming or transforming a value
cannot remove its mask; when several protected sources contribute, the strongest mask
wins. Ambiguous or unresolved derived provenance is rejected. Duplicate final output
labels are rejected as `DUPLICATE_OUTPUT_COLUMN` before database execution so mapping a
row to a dictionary cannot silently overwrite one result position.

`QueryExecution` records validation/execution status, approved referenced objects,
literal-sanitized SQL, safe filter structure, timings, counts, masked preview, and stable
error codes. It stores no credentials, DSNs, raw row-filter literals, or unmasked
sensitive values.

### Permission API examples

All permission mutations require a tenant administrator and infer the tenant from the
verified access token. The subject object contains exactly one of `user_id` or `role_id`.

```powershell
$permission = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/permissions/tables -Headers $headers `
  -ContentType application/json -Body (@{
    connection_id = $connection.id; table_id = $customersTableId
    role_id = $analystRoleId; can_read = $true
    row_filter = @{ version = 1; all = @(@{
      column_id = $countryColumnId; operator = "eq"
      value = @{ source = "literal"; value = "Egypt" }
    }) }
  } | ConvertTo-Json -Depth 8)

Invoke-RestMethod -Method Put `
  -Uri "http://localhost:8000/api/permissions/tables/$($permission.id)/columns" `
  -Headers $headers -ContentType application/json -Body (@{
    items = @(
      @{ column_id = $nameColumnId; can_read = $true; can_filter = $true; can_aggregate = $false },
      @{ column_id = $taxColumnId; can_read = $true; can_filter = $false; can_aggregate = $false; mask_type = "hash" }
    )
  } | ConvertTo-Json -Depth 5)

Invoke-RestMethod `
  -Uri "http://localhost:8000/api/database-connections/$($connection.id)/allowed-schema" `
  -Headers $userHeaders
```

List/get/update/delete use `/api/permissions/tables` and
`/api/permissions/tables/{permission_id}`; column grants use the `/columns` suffix.
There is no public SQL execution endpoint in Phase 3B.

## Bootstrap the first tenant administrator

The password is accepted only through the process environment so it does not appear in
the command line or process list. Values are examples, not hardcoded application data:

```powershell
$env:BOOTSTRAP_ADMIN_PASSWORD = "choose-a-strong-temporary-password"
python -m scripts.bootstrap `
  --tenant-name "Example Tenant" `
  --tenant-code "example-tenant" `
  --admin-email "admin@example-tenant.example" `
  --admin-full-name "Example Administrator" `
  --role "analyst"
Remove-Item Env:BOOTSTRAP_ADMIN_PASSWORD
```

The command normalizes the tenant code, email, and role names; hashes the password with
Argon2id; and idempotently creates or finds the canonical Administrator role and its
assignment. Repeated runs report separate created and already-existing counts. It never
prints the password or password hash.

## Authentication flow

1. The client sends tenant code, email, and password to `/api/auth/login`.
2. The server normalizes tenant code and email, performs constant-work password
   verification, and returns the same `Invalid credentials` response for every identity
   failure.
3. A short-lived access JWT and longer-lived refresh JWT are signed with required `sub`,
   `tenant_id`, `token_type`, `jti`, `iat`, and `exp` claims.
4. Only the refresh-token digest is stored in PostgreSQL.
5. Protected endpoints verify the signature and token type, then rebuild tenant context
   from current database records.
6. Refresh rotates the session under a database row lock, revokes the old token, and
   returns a replacement pair. Reuse of the old token revokes the active family.

### Login

```powershell
$loginBody = @{
  tenant_code = "example-tenant"
  email = "admin@example-tenant.example"
  password = "the-bootstrap-password"
} | ConvertTo-Json

$tokens = Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/auth/login `
  -ContentType application/json `
  -Body $loginBody
```

Response fields:

```json
{
  "access_token": "signed-access-token",
  "refresh_token": "signed-refresh-token",
  "token_type": "bearer",
  "access_token_expires_in": 900
}
```

### Current authenticated identity

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri http://localhost:8000/api/auth/me `
  -Headers @{ Authorization = "Bearer $($tokens.access_token)" }
```

### Refresh and rotate tokens

```powershell
$refreshBody = @{ refresh_token = $tokens.refresh_token } | ConvertTo-Json
$tokens = Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/auth/refresh `
  -ContentType application/json `
  -Body $refreshBody
```

The old refresh token must be discarded immediately. Reusing it is treated as replay.

## Tenant-administrator examples

Every endpoint below derives its tenant from the verified access token. None accepts
`tenant_id`.

Create a user:

```powershell
$headers = @{ Authorization = "Bearer $($tokens.access_token)" }
$user = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/users `
  -Headers $headers -ContentType application/json -Body (@{
    email = "analyst@example-tenant.example"
    full_name = "Example Analyst"
    password = "choose-another-strong-password"
  } | ConvertTo-Json)
```

List users with pagination:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/users?page=1&page_size=50" `
  -Headers $headers
```

Create and list roles:

```powershell
$role = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/roles `
  -Headers $headers -ContentType application/json -Body (@{
    name = "analyst"
    description = "Read-only business analyst"
  } | ConvertTo-Json)

Invoke-RestMethod -Uri "http://localhost:8000/api/roles?page=1&page_size=50" `
  -Headers $headers
```

Replace a user's roles:

```powershell
Invoke-RestMethod -Method Put `
  -Uri "http://localhost:8000/api/users/$($user.id)/roles" `
  -Headers $headers -ContentType application/json `
  -Body (@{ role_ids = @($role.id) } | ConvertTo-Json)
```

## Health and request IDs

```powershell
Invoke-RestMethod http://localhost:8000/api/health/live
Invoke-RestMethod http://localhost:8000/api/health/ready
```

Every response includes `X-Request-ID`. A supplied ID is preserved; otherwise, the API
generates a UUIDv4. The legacy `/health` and `/health/ready` paths return HTTP 404.

## Tests

Run all fast unit and API tests without PostgreSQL:

```powershell
python -m pytest -m "not integration"
```

Run lint, formatting, and syntax checks:

```powershell
python -m ruff check app api core database models repositories schemas scripts services tests migrations
python -m ruff format --check app api core database models repositories schemas scripts services tests migrations
python -m compileall -q app api core database models repositories schemas scripts services tests migrations
```

Run PostgreSQL integration tests only against a disposable dedicated database whose
name contains `test`. The tests perform an Alembic downgrade and must never target a
shared or production database:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_password@localhost:5432/text_to_sql_test"
python -m pytest -m integration
Remove-Item Env:TEST_DATABASE_URL
```

Customer-adapter integration tests additionally use the disposable service:

```powershell
$env:CUSTOMER_TEST_HOST = "customer-postgres"
$env:CUSTOMER_TEST_PORT = "5432"
$env:CUSTOMER_TEST_DATABASE = $env:CUSTOMER_POSTGRES_DB
$env:CUSTOMER_TEST_USERNAME = $env:CUSTOMER_POSTGRES_READER_USER
$env:CUSTOMER_TEST_PASSWORD = $env:CUSTOMER_POSTGRES_READER_PASSWORD
python -m pytest -m integration
```

Run this inside the Compose network, as done by CI/live verification. The integration
customer database uses tmpfs. `customer_owner` initializes `customers`, `orders`,
`invoices`, and one view, then provisions `customer_reader` with CONNECT, schema USAGE,
and SELECT only. Runtime API connections use only `customer_reader`; tests prove it is
not the owner or a privileged role and cannot write or perform DDL.
The initializer also revokes PostgreSQL's default database `TEMPORARY` privilege from
`PUBLIC`; live tests prove `customer_reader` cannot create temporary tables while SELECT
and catalog discovery still work. Phase 3B's live service test validates row filtering,
masking, alias/CTE/subquery/UNION bypass resistance, audit records, and unchanged source
row counts.

Run the full suite, with PostgreSQL tests skipped when `TEST_DATABASE_URL` is absent:

```powershell
python -m pytest
```

## Phase 3C database chat and Phase 4 document/hybrid chat

Phase 3C adds owner-scoped conversations and messages plus a database LangGraph
workflow. The graph classifies the request, selects exactly one tenant-owned active
connection, retrieves a small deterministic subset of the effective allowed schema,
asks the provider for structured SQL, and sends that SQL through the existing Phase 3B
validator/rewriter/executor. The model never receives credentials, full catalog data,
hidden object names, row-filter literals, raw customer rows, or unmasked values.

```text
Client -> FastAPI -> LangGraph -> Classifier -> Allowed Schema Retriever
       -> SQL Generator -> Phase 3B Safety Boundary -> Customer PostgreSQL
       -> Masked Result -> Grounded Answer Generator -> Conversation Persistence
```

The running application always constructs `GroqProvider` with the official asynchronous
Groq SDK. Groq Cloud is the only real application provider, and
`openai/gpt-oss-120b` is a Groq-hosted model identifier: this project does not use an
OpenAI account, key, billing relationship, SDK, or application provider. No provider switch
or fallback exists. `FakeLLMProvider` is reachable only when automated tests
explicitly inject it through dependency overrides. Timeouts, retries, output size,
schema size, history, and graph recursion are bounded. Provider refusal, malformed or
incomplete structured output, and provider errors fail safely.

Explicit source categories constrain executable routing deterministically: documents
only routes to document RAG, a database only routes to database chat, and both route to
hybrid chat. With no selected sources, genuine general conversation remains general and
source-requiring model classifications clarify rather than inventing a source. Routing is
not authorization: every supplied ID is first validated against the authenticated tenant,
active state, ownership, and access policy. The classifier receives only immutable source
category booleans and bounded counts—never IDs, names, schemas, credentials, or document
content. Document routing does not guarantee relevant evidence; local FastEmbed retrieval
thresholds and backend citation validation still apply. Sources are never selected
automatically.

Create a conversation and send a request:

```powershell
$conversation = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/conversations -Headers $headers `
  -ContentType application/json `
  -Body (@{ title = "Customer questions"; database_connection_ids = @($connection.id) } | ConvertTo-Json)

$chat = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/chat `
  -Headers $headers -ContentType application/json `
  -Body (@{ conversation_id = $conversation.id; message = "How many customers are there?" } | ConvertTo-Json)

Invoke-RestMethod -Uri "http://localhost:8000/api/messages/$($chat.message_id)/sql" -Headers $headers
```

Use `POST /api/chat/stream` with the same body for SSE events (`started`,
`classified`, `query_executed`, `answer_delta`, `completed`, or sanitized `error`).
List/detail/delete endpoints are `GET/POST /api/conversations`,
`GET /api/conversations/{id}`, and `DELETE /api/conversations/{id}`. Delete is soft;
messages and query audits remain retained. Every conversation lookup is constrained by
both verified tenant and authenticated owner. Phase 4 validates every knowledge-base ID
against that same tenant/owner boundary before retrieval.

The graph permits one SQL repair only for a syntax validation category. Permission,
hidden-object, unsafe-operation, row-filter, and policy failures are never repairable.
Answers are generated only from the already masked, size-limited result. Zero-row and
single-scalar answers are deterministic. Citations contain approved database table
labels only, and the SQL inspection endpoint returns sanitized normalized SQL and audit
metadata—not raw values.

Successful database answers use `sources_used: ["database"]`; approved qualified table
names remain in `citations`. Assistant messages persist the same category in
`selected_sources`. Provider prompt tokens, completion tokens, and latency are summed
across classification, SQL proposal, an optional repair, and answer generation. Safe
per-stage counters are retained without prompts or raw provider responses.

SSE `answer_delta` events are bounded ordered chunks. Concatenating their `text` values
reconstructs the `completed.answer` exactly. Proposed SQL is never emitted; only the
normalized SQL may appear after the deterministic validator has accepted it.

Run the offline deterministic evaluation corpus:

```powershell
python scripts/evaluate_text_to_sql.py
```

This offline report measures deterministic fixture routing and structured-contract
correctness; it is not a claim about natural-language model quality. For database-backed
acceptance, malicious rejection, execution, expected results, row filters, and masking,
run the PostgreSQL integration evaluation with the disposable customer service as
documented in the Tests section.

The evaluator keeps three modes separate:

- `python scripts/evaluate_text_to_sql.py` is the injected test-double per-case
  regression and makes no model-quality claim.
- `python scripts/evaluate_text_to_sql.py --live` invokes the disposable PostgreSQL
  safety suite for real validation, execution, row-filter, and masking assertions.
- `python scripts/evaluate_text_to_sql.py --real-groq` is an explicit credentialed,
  case-by-case Groq model evaluation; it is never part of automated tests. Use
  `--live --real-groq` only in the disposable integration environment.

An explicit three-call real Groq smoke test is available and never runs in the normal
suite. Configure the key only in the local environment or a secret manager:

```powershell
$env:GROQ_API_KEY = "<local-secret-manager-value>"
$env:RUN_REAL_GROQ_VERIFICATION = "1"
python scripts/smoke_groq_phase3c.py
Remove-Item Env:RUN_REAL_GROQ_VERIFICATION
Remove-Item Env:GROQ_API_KEY
```

Without a valid local key it prints `Real Groq verification not executed`. A successful
run performs strict classification, read-only SQL proposal, and grounded-answer parsing,
and prints only sanitized provider/model/usage totals. Groq plan availability and limits
are controlled by Groq and are not guaranteed to remain unlimited. Without a key,
automated tests still run via explicit test injection, but the application never pretends
that a real Groq call occurred.

Create a portable archive with normalized POSIX entry names and built-in traversal,
secret, cache, and artifact checks:

```powershell
python scripts/package_project.py --output outputs/phase4-document-hybrid-project.zip
```

## Phase 4 document infrastructure and APIs

Normal Compose startup runs PostgreSQL 16 with pgvector, the FastAPI service, Redis,
private MinIO storage, a one-shot bucket/user initializer, and a Dramatiq worker. Set the
MinIO credentials only in local `.env`; object keys are opaque tenant/file identifiers,
not client filenames. Uploaded bytes stream to a bounded temporary file, are hashed, and
are checked by extension, signature, archive paths, expansion ratio, macro/script
payloads, and format structure before private storage. Queue messages carry only tenant,
file, and ingestion-generation IDs. The worker downloads and revalidates size, SHA-256,
type, and container structure before parsing.

Supported parsers are PyMuPDF text extraction for PDF (no OCR), python-docx for DOCX,
openpyxl read-only/data-only mode for XLSX, bounded CSV parsing, and decoded plain text.
Chunking uses deterministic whitespace-token windows while preserving page, section,
sheet, and row-range provenance. Reprocessing keeps `active_ingestion_version` on the
last successful generation until the replacement is committed; failed replacement work
cannot expose partial chunks or remove the last good generation.

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` runs locally through
FastEmbed on CPU and produces exactly 384 dimensions. Dense cosine candidates and
lexical `simple`-configuration `tsvector` candidates are each selected only after tenant,
knowledge-base, active-file, and active-generation filters. Reciprocal-rank fusion is
deterministic and final evidence count/character/relevance limits are enforced. Customer
document bytes remain in MinIO; the application database stores extracted bounded text
chunks and embeddings, never an unrestricted copy or a public object URL.

Knowledge-base endpoints are `POST/GET /api/knowledge-bases`,
`GET/PUT/DELETE /api/knowledge-bases/{id}`, plus
`POST /api/knowledge-bases/{id}/files`. File endpoints are
`POST /api/files/upload`, `GET /api/files`, `GET/DELETE /api/files/{id}`, and
`POST /api/files/{id}/reprocess`. Upload responses are HTTP 202. Owners and tenant
administrators can manage; other users see HTTP 404. No request accepts `tenant_id`.

Example document conversation and chat (with an existing uploaded, ready file):

```powershell
$kb = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/knowledge-bases `
  -Headers $headers -ContentType application/json -Body '{"name":"contracts"}'
$conversation = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/conversations `
  -Headers $headers -ContentType application/json `
  -Body (@{title="Contract questions"; knowledge_base_ids=@($kb.id)} | ConvertTo-Json)
$answer = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/chat `
  -Headers $headers -ContentType application/json `
  -Body (@{conversation_id=$conversation.id; message="Search the document for termination terms"} | ConvertTo-Json)
Invoke-RestMethod -Uri "http://localhost:8000/api/messages/$($answer.message_id)/citations" -Headers $headers
```

Document content is untrusted evidence, not instructions. The rewrite stage receives no
chunks. Final generation sees only authorized bounded chunks labeled `DOC1...`; returned
IDs must be a subset or the answer fails closed. Hybrid chat additionally sends only
already validated, filtered, bounded, masked database evidence as `DB1`. SQL always
passes the unchanged Phase 3B safety boundary. `sources_used` contains source categories
(`documents`, `database`), while citations retain file/chunk provenance or approved table
labels. Deleting a file is a soft tombstone, so prior citation display remains traceable.

SSE keeps the public event contract. No proposal SQL or unvalidated model data is
streamed. Ordered bounded `answer_delta` chunks concatenate exactly to the persisted
`completed.answer`; hybrid query events expose normalized SQL only after validation.

Automated tests inject fake LLM and embedding services and never download a model or call
Groq. Run `python -m pytest -q`; provide a disposable test PostgreSQL URL through
`TEST_DATABASE_URL` for migration, pgvector, constraints, and live retrieval coverage.
Run `python scripts/evaluate_phase4.py --mode deterministic` for the injected test-double
per-case report. It records retrieval, evidence, citation, injection, and applicable
hybrid controls independently for every case and makes no real-model quality claim.
`--mode postgresql` requires `TEST_DATABASE_URL` and executes pgvector-distance and
PostgreSQL full-text probes plus tenant-scoped repository retrieval and citation
persistence per applicable case. `--mode fastembed` requires
`RUN_REAL_FASTEMBED_EVALUATION=1`; without it, the evaluator reports
`Real FastEmbed evaluation not executed`. `--mode groq` requires both the Groq run flag
and a valid local key. Neither optional mode runs implicitly.
Real document/hybrid smoke verification is opt-in only and requires both a valid local
`GROQ_API_KEY` and `RUN_REAL_GROQ_VERIFICATION=1`. A key alone never triggers it.

The smoke programs are executable staged flows. They use separate administrator,
normal-user, and second-tenant tokens. Required checkpoints perform database vector
inspection, public SSE reconstruction, malicious-document questioning, cross-tenant
denial requests, persisted SafeQuery/citation inspection, six independent attacks, and
before/after customer-schema fingerprints. Exit code 0 is a successful real-smoke claim
only when every required stage and detectable cleanup assertion passes.

Optional local FastEmbed retrieval evaluation (downloads/runs the configured local model):

```powershell
$env:RUN_REAL_FASTEMBED_EVALUATION = "1"
python scripts/evaluate_phase4.py --mode fastembed
Remove-Item Env:RUN_REAL_FASTEMBED_EVALUATION
```

```powershell
$env:RUN_REAL_GROQ_VERIFICATION = "1"
python scripts/smoke_groq_phase4_document.py
python scripts/smoke_groq_phase4_hybrid.py
Remove-Item Env:RUN_REAL_GROQ_VERIFICATION
```

```sh
RUN_REAL_GROQ_VERIFICATION=1 python scripts/smoke_groq_phase4_document.py
RUN_REAL_GROQ_VERIFICATION=1 python scripts/smoke_groq_phase4_hybrid.py
```

Deterministic content, format, parsing, limit, and embedding-dimension failures are
permanent. Temporary storage, filesystem, timeout, embedding-initialization, and database
operational failures are re-raised for Dramatiq's bounded backoff. Final exhaustion uses
a stable code, and a last-good active ingestion generation remains available.

## Error contract

- HTTP 400: invalid or unexpected request fields.
- HTTP 401: generic authentication failure.
- HTTP 403: authenticated user lacks tenant-admin authority.
- HTTP 404: a tenant-scoped user or role does not exist inside the authenticated tenant.
- HTTP 404: a connection or cached resource is outside the authenticated tenant.
- HTTP 409: tenant-scoped uniqueness conflict.
- HTTP 500: `{"detail":"Internal server error"}` without stack traces or database details.

## References and acknowledgements

The assignment PDF is the primary source of truth. No external project implementation
was copied. Public interfaces and security behavior were checked against the official
documentation for [FastAPI](https://fastapi.tiangolo.com/),
[SQLAlchemy](https://docs.sqlalchemy.org/en/20/),
[Alembic](https://alembic.sqlalchemy.org/),
[pwdlib](https://frankie567.github.io/pwdlib/),
[PyJWT](https://pyjwt.readthedocs.io/en/stable/),
[PostgreSQL](https://www.postgresql.org/docs/), and
[Docker Compose](https://docs.docker.com/compose/).
