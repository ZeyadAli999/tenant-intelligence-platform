# Phase 2 through Phase 5C Document/Hybrid (Phase 4), Groq, and Frontend Security Notes

Phase 3C and Phase 4 add database, document, and hybrid chat without delegating authorization to the
model. Tenant resolution, schema visibility, SQL validation, row filters, execution,
masking, and persistence authorization remain deterministic backend controls.

Phase 5B adds a strict Next.js BFF and chat workspace without moving trust into
the browser. Access and refresh tokens remain separate HttpOnly cookies. The BFF
uses an explicit path/method allowlist, injects authorization server-side,
rejects cross-origin mutations and client tenant identifiers, performs at most
one refresh attempt, and forwards `text/event-stream` bodies incrementally with
cancellation propagation. It never forwards browser-supplied Authorization
headers. Assistant output is rendered as text, while SQL and citations come only
from validated backend response contracts. Conversation source selection is
immutable, tenant-owned, and revalidated by FastAPI on every request.

## Tenant identity

`tenant_code` is required during login because user email uniqueness is scoped to a
tenant. The same normalized email can belong to two different tenants without creating
an ambiguous identity.

Protected requests do not accept `tenant_id`. The server obtains `tenant_id` only after
verifying the access-token signature and mandatory claims, then confirms the user still
belongs to that active tenant in PostgreSQL. Query parameters and custom tenant headers
cannot replace this context.

Tenant-admin queries always include the authenticated tenant ID. Cross-tenant user and
role identifiers are treated as nonexistent. Composite database foreign keys also bind
user-role assignments to one tenant.

## Passwords and tokens

Passwords are hashed with Argon2id through `pwdlib`. Login returns the same generic
failure for unknown tenants, unknown emails, wrong passwords, and inactive identities.

JWT decoding fixes the accepted algorithm in server configuration and requires `sub`,
`tenant_id`, `token_type`, `jti`, `iat`, and `exp`. Access and refresh token types are not
interchangeable, and claims are never used before signature and lifetime validation.

Refresh tokens are stored only as SHA-256 digests. Successful use locks and revokes the
current database record, then inserts a replacement in the same family. Reuse of a
revoked token revokes every active record in that family.

## Logging and errors

The following values must never be logged:

- passwords or password hashes;
- access or refresh tokens;
- JWT secrets;
- database URLs containing credentials;
- complete `Authorization` headers.

SQLAlchemy always hides bound parameter values. Authentication logs contain only a safe
event label and `X-Request-ID`. Unexpected-error logs omit exception messages and URLs,
while API clients receive a stable sanitized error body without stack traces.

Report suspected credential or token exposure by rotating the affected credentials,
revoking related refresh-token families, preserving audit evidence without copying the
secret, and notifying the system owner through the approved private channel.

## Runtime database credentials

Customer passwords are never stored in plaintext or returned by the API. AES-256-GCM
uses a required base64url 32-byte master key, a random nonce for every operation, and a
versioned payload. Tenant and connection UUIDs are authenticated as associated data, so
ciphertext cannot be transplanted between records. The key has no valid default and must
remain in `.env` only for local development or in a production secret manager.

Decryption occurs only inside connection testing or schema discovery. DSNs are built
server-side with structured fields, SQLAlchemy hides parameters, and engines use
`NullPool` and are disposed after success or failure. Logs and responses contain only
stable categories, never raw driver exceptions, DSNs, hosts with credentials, passwords,
ciphertext, authorization headers, or encryption/JWT keys.

## SSRF and customer-data isolation

Host input cannot contain URL schemes, credentials, paths, queries, or fragments. Every
resolved address is checked; unspecified, loopback, link-local, multicast, reserved, and
metadata-service targets are blocked. Private addresses require
`ALLOW_PRIVATE_DATABASE_HOSTS=true`, which is disabled by default. DNS is resolved again
immediately before connection to narrow DNS-rebinding opportunities. Network-level egress
rules remain a required production defense in depth.

The PostgreSQL adapter queries catalog metadata only. Cache rows contain schema/table/
column structure, relationships, descriptions, and row-count estimates. It never selects
or copies customer business rows and leaves `sample_values` empty. Composite foreign keys
enforce that connections, schemas, tables, and columns remain in one tenant even if a
service-layer check is bypassed.

Schema synchronization reconciles rows by stable natural keys instead of deleting the
cache tree. Unchanged UUIDs survive every sync, stale tables are retained but disabled,
and returning tables are re-enabled with their original UUID. This prevents future
permission relationships from being invalidated. All changes and stale-column removals
remain in one platform transaction.

The disposable integration database has separate identities. `customer_owner` exists
only for initialization. The application uses `customer_reader`, which has LOGIN,
CONNECT, business-schema USAGE, and SELECT grants, but no ownership, role/database
creation, writes, schema creation, or DDL permissions. Both passwords come from local
environment values and are excluded from source and generated archives.

## Permissions and effective schema

Customer-data access is deny-by-default and independent of tenant-administrator status.
A user-specific table permission replaces role-derived permissions for that table. When
there is no user override, readable role grants are unioned; false rows do not negate an
unrelated true grant. Filtered role grants are ORed as complete grants. Disabled objects
are denied, and sensitive objects require explicit grants.

Column permissions separately control reading, filtering, and aggregation. Explicit
column rows form an allowlist; otherwise only non-sensitive columns inherit table access.
Sensitive columns always need an explicit readable grant and an approved mask. The
effective-schema resolver is the only source used by the allowed-schema response, SQL
validator, row-filter compiler, and query executor. Hidden object names and relationships
are removed before this schema can reach a future model.

Composite foreign keys bind permission subjects, connections, tables, and columns to the
same tenant and table hierarchy. Routes never accept `tenant_id`, and cross-tenant IDs
are returned as 404. Database checks require exactly one user/role subject and keep all
write capability flags false in this phase.

## Row authorization and SQL validation

Row filters are a strict version-1 JSON DSL with a fixed operator set, typed literals,
and optional server-resolved user/tenant context. They cannot contain raw SQL. Every
column must belong to the permission's table and be filterable. Empty or invalid filters
are rejected during permission management; runtime compilation uses SQLGlot expression
nodes and bind parameters. Audit data records column IDs and operators but not literal
values.

SQLGlot parses the PostgreSQL AST and applies fail-closed, scope-aware validation. Only a
single comment-free read-only query is accepted. DML, DDL, security statements, COPY,
calls, locking, `SELECT INTO`, system catalogs, stars, inaccessible objects, unauthorized
filter/aggregate uses, unknown functions, unsafe server functions, and over-complex
queries are rejected before any customer connection is opened.

Mandatory predicates are injected after validation by wrapping every protected base-table
occurrence in a filtered subquery. This preserves outer-join semantics and prevents SQL
text from omitting or weakening authorization with aliases, `OR 1=1`, CTEs, subqueries,
UNIONs, or repeated table references. Future SQL generation is therefore never trusted
as an authorization mechanism.

## Controlled execution, masking, and audit records

`SafeQueryService` is an internal boundary; Phase 3B intentionally exposes no public raw
SQL endpoint. It rebuilds the verified tenant context, resolves permissions, validates
and rewrites the AST, decrypts credentials only at the execution boundary, revalidates
the host, then uses a short-lived `NullPool` engine and read-only PostgreSQL transaction.
Connection, statement, lock, row, column, cell, and serialized-result limits are enforced,
and the engine is disposed on every path.

Sensitive projections are masked before service return or audit-preview persistence.
Allowed masks are `redact`, `partial`, `hash`, and `null`; hash masking uses keyed
HMAC-SHA-256 with the required `RESULT_MASKING_KEY`, not a predictable raw digest. The
key must be stored alongside other deployment secrets and never logged or archived.

Mask decisions follow column provenance, not the output label. The lineage analyzer
resolves each final output position through base tables, derived scopes, CTEs, nested
subqueries, set-operation branches, aliases, casts, functions, aggregates, CASE, and
compound expressions. All contributing approved base-column UUIDs are retained and the
strongest applicable mask is selected. Ambiguous or unresolved provenance fails closed.
Result masking consumes the position-aligned plan and verifies adapter column order.
Duplicate final labels are rejected during validation and again defensively by the
PostgreSQL adapter before row mappings are created.

`QueryExecution` stores literal-sanitized generated/normalized SQL, safe validation
codes, approved referenced objects, filter structure without literal values, timing,
counts, masked previews, and stable failure categories. It must never contain raw
credentials, DSNs, tokens, unsafe driver exceptions, row-filter secrets, or unmasked
sensitive values. Operational logs use IDs, timing, truncation state, and stable error
categories only.

The disposable reader also has `TEMPORARY` revoked at database scope (including the
default grant inherited through `PUBLIC`). It retains only CONNECT, schema USAGE, and
SELECT access needed for discovery and controlled reads.

## Phase 3C model and prompt boundary

The model is a proposal component, never an authorization component. Only the verified
tenant context and database-backed effective-permission resolver determine the source
and schema. Schema retrieval ranks approved tables deterministically and includes only
readable columns plus visible foreign-key neighbors within strict caps. Metadata text is
marked untrusted. Prompt text explicitly separates instructions from user, metadata,
history, and result data; prompt injection cannot relax the downstream SQL boundary.

Source-aware routing remains separate from authorization. Requested knowledge bases and
database connections first pass tenant-scoped active/access checks. The classifier then
receives only immutable source-category booleans and bounded counts. Explicit
document-only, database-only, or combined selection deterministically resolves document,
database, or hybrid execution; the model cannot add sources or change tenant scope. No
IDs, names, schemas, credentials, document text, or retrieved chunks enter classification.
Local FastEmbed embeddings, relevance thresholds, and backend-validated citations remain
mandatory, so document routing alone never guarantees evidence or success.

The application uses only Groq Cloud through the official asynchronous Groq SDK and the
Groq-hosted `openai/gpt-oss-120b` model identifier. No OpenAI account, key, billing, SDK,
or provider is used. Every stage uses strict JSON Schema, then Pydantic validation, with
hidden reasoning, disabled storage, bounded timeouts/output/retries, and sanitized error
mapping. There is no provider switch or fallback. `FakeLLMProvider` is a deterministic
test double reachable only through explicit automated-test dependency injection.

`GROQ_API_KEY`, prompts, raw responses, tokens, credentials, authorization headers,
unmasked customer values, and complete SQL driver errors must never be logged or
persisted. Safe persistence is limited to provider `groq`, configured model, aggregate and
per-stage token/latency counts, prompt version, and safe status metadata.

Conversation and message access is constrained by verified tenant ID and authenticated
owner ID. Clients cannot supply tenant IDs. Query executions link to the assistant
message with tenant-aware foreign keys. Conversation deletion is soft so audits are
retained, while deleted conversations cannot accept new messages.

Only masked and result-limited rows cross into answer generation. Persisted message
structured content contains safe warnings, prompt version, and a query-execution ID;
`QueryExecution.result_preview` is already masked before persistence.

## Phase 4 file, retrieval, and evidence boundary

Knowledge-base access is independently checked with verified tenant and owner IDs;
tenant administrators may manage within their tenant. Cross-tenant and unauthorized
objects appear nonexistent. Filenames are display metadata only. Opaque object keys,
private MinIO buckets, streaming size limits, signatures, archive traversal/expansion
checks, macro rejection, SHA-256 integrity checks, and sanitized processing errors form
the upload boundary. Redis jobs contain identifiers only, and temporary files are always
removed. The last successful ingestion generation stays active until a new generation is
atomically committed.

Local 384-dimensional embeddings and PostgreSQL FTS are queried only after tenant,
knowledge-base, file-status, and active-generation predicates. Document text is always
untrusted data: it cannot change system instructions, authorize tools, reveal credentials,
or bypass SQL controls. Final document/hybrid answers may cite only issued `DOC*`/`DB1`
evidence IDs. Unknown IDs fail closed. Database evidence is already permission-filtered,
row-filtered, limited, and masked before merging; raw protected values never cross the
answer boundary. Durable citations preserve authorized provenance without persisting raw
provider requests, prompts, object credentials, or unmasked source values.

Ingestion failures have an explicit taxonomy. Deterministic content, format, parsing,
limit, and embedding-dimension failures are permanent. Temporary MinIO, database,
filesystem, timeout, and embedding-initialization failures are re-raised for Dramatiq's
bounded retry/backoff. Retry and exhausted states persist stable codes, never exception
text, and reprocessing does not replace the last-good active generation prematurely.

The Phase 4 real Groq smoke programs require both the explicit run flag and a valid local
key. They never place the key in arguments or reports, emit sanitized summaries, and
unconditionally attempt cleanup. Automated tests inject a staged flow and make no
external requests.

Live Phase 4 verification uses distinct administrator, normal-user, and second-tenant
access tokens. Chat, files, conversations, SSE, and citations are exercised as the
normal user; setup alone uses administrator authority; denial checks use the unrelated
tenant. Internal inspection emits only counts and booleans for active 384-dimensional
chunks, persisted provider/query metadata, row-filter presence, and masked previews.
