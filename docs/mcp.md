# Optional remote MCP (first version)

This adds **five tools**, not an unrestricted REST bridge, using the official
Python MCP SDK 2.3.0 and stateless Streamable HTTP at `/mcp`. It is **off by
default**. Local SQLite/no-login mode cannot enable it. The regular app remains
unchanged when it is off.

This PR is a resource server, **not a ready-to-connect Supabase OAuth setup**.
It does not install an authorization server, register a client, create grants,
issue credentials, or deploy anything. A configured, compatible OAuth provider
and a real client login must be verified before production use.

## Tools and permissions

| Tool | Scope | Effect |
| --- | --- | --- |
| `read_inventory` | `fridge:read` | Paginated inventory, quantities, storage and expiry |
| `search_recipes` | `fridge:read` | Saved/favourite recipe search, live conservative stock annotations |
| `get_current_plan` | `fridge:read` | Newest-created plan and generation status, not necessarily this calendar week |
| `preview_plan_shopping` | Both | Stores an expiring exact shopping preview and returns a human approval URL |
| `import_plan_shopping` | Both | Applies only a first-party human-approved, unchanged preview |

No tool accepts a user ID. Tokens resolve through an explicit administrator
mapping to an existing app user. Nothing creates users or calls paid AI services.
Photos, email, preferences and feedback are not exposed as MCP tools. Ingredient
amounts that cannot be compared remain **check**, not sufficient stock. Expiry
remains an estimate. Recipe and inventory text are untrusted data, not instructions.

## Deployment prerequisites (do not skip)

1. Run normal cloud mode with Supabase authentication and HTTPS. Keep the backend
   port private behind the frontend/reverse proxy; never publish local mode.
2. Use an OAuth 2.1-compatible authorization server with authorization-code + PKCE
   (S256), exact redirect URI registration and authorization-server discovery. It
   must issue **signed RFC 9068 access JWTs**, header `typ=at+jwt` (or `application/at+jwt`), RS256 or ES256,
   with the exact `/mcp` URL as a **single string audience**, trusted `iss`, `sub`,
   `client_id`, nonempty `jti`, space-delimited `scope`, and integer `iat`/`exp` no more than
   15 minutes apart. ID tokens, general Supabase sessions, audience arrays and
   legacy shared-secret tokens are rejected.
3. Configure real API scopes `fridge:read` and optional `fridge:shopping` at that
   provider. Supabase's OAuth OIDC scopes are not these scopes; this version
   deliberately rejects the ordinary Supabase issuer. Do not simply rename an
   OIDC scope or forward a Supabase login token. A dedicated issuer is required.
4. Explicitly verify which provider subject belongs to which Supabase app user,
   then put that subject, registered OAuth client ID and existing app user UUID in
   `MCP_GRANTS`. This is the authorization grant and cross-issuer identity map;
   matching email, UUID shape or an unverified token claim is **not** a mapping.
   Obtain the user's consent before establishing access. Grant read-only unless
   shopping preview/import is needed. Tokens cannot exceed this grant's scopes.
5. Set the environment shown below and restart. Invalid configuration fails
   startup; an unknown/missing app user or unmapped client/subject fails auth.
   Keep these settings server-side, not `VITE_*` variables. Changes to grants
   require restart of all replicas; removing a grant revokes subsequent requests
   after that rollout. For emergency revocation, disable MCP at the proxy first.
6. Serve the nginx `/mcp` and `/.well-known/oauth-protected-resource/mcp` routes;
   they must never return the SPA. SDK metadata advertises the canonical resource,
   issuer and available scopes, and 401 responses provide metadata discovery.
   Preserve the public Host and Origin headers. Only the exact resource host and
   same-origin browser requests are allowed. Configure the intended client to use
   HTTPS and request the resource audience. Cross-origin browser clients are not
   enabled in this first version.

Example non-secret configuration (replace placeholders; do not copy a random UUID):

```dotenv
MCP_ENABLED=true
MCP_RESOURCE_URL=https://fridge.example.com/mcp
MCP_ISSUER_URL=https://example-tenant.us.auth0.com/
MCP_JWKS_URL=https://example-tenant.us.auth0.com/.well-known/jwks.json
MCP_GRANTS=[{"subject":"verified-provider-subject","client_id":"registered-client-id","user_id":"verified-existing-supabase-user-uuid","scopes":["fridge:read","fridge:shopping"]}]
```

One provider option is Auth0, whose API settings offer an RFC 9068 access-token
profile (its default profile is different). Configure a dedicated API identifier
matching the MCP URL, RS256, the two API permissions and <=15-minute token
lifetimes, then register the intended client with code flow, PKCE and exact
redirects. Request only the API scopes, avoiding an extra UserInfo audience.
Use the tenant issuer and JWKS URLs. Enable Auth0’s
[Resource Parameter Compatibility Profile](https://support.auth0.com/center/s/article/mcp-audience-error-with-auth0)
so MCP’s RFC 8707 `resource` parameter selects the API audience. Verify the
actual single-audience token with your client/provider configuration before use;
this example is not a turnkey tenant export or a claim of tested interoperability.
Providers that cannot produce this contract are unsupported.

Supabase browser-login redirect settings must allow the first-party
`https://fridge.example.com/mcp-approvals/*` path for email links to preserve the
approval page. Password login and onboarding already preserve the current path.
No redirect settings are changed by this implementation.

The normal REST API independently validates its Supabase audience and rejects
any OAuth `client_id` claim or RFC 9068 access-token type, including at the approval endpoints.
An MCP token therefore cannot bypass the five-tool boundary through the app API.
No MCP access token is forwarded to Supabase or another service.

## Human approval and retry behavior

1. Preview calculates remaining **suggested** meals only; cooked and delivery
   meals do not add groceries. It snapshots the source state and exact shopping
   merge delta, stores an expiring request, and returns `/mcp-approvals/<id>`.
2. The human opens the first-party app, signs in, reviews the client, plan,
   items, before/after quantities and expiry, then explicitly approves or denies.
   A model saying `confirmed=true`, an approval ID alone, or a request made with
   MCP credentials never approves anything. Login must preserve this deep link.
3. Import checks user/client ownership, scope, status, expiry and unchanged source
   state. If inventory, plan, relevant recipes/staples or shopping state changed,
   obtain a fresh preview and approval. Approval does not itself import anything.
4. Approval consumption, normal plan-import deduplication, shopping changes and
   stored result are committed atomically. Same-ID retries return the saved result.
   The app's original plan import key is shared, so a second preview cannot add the
   same original plan again. The app's intentional “add again” remains separate.

Approvals use the existing database and an Alembic migration. PostgreSQL table
locks serialize the short preview/approve/import critical sections against the
existing UI write paths; this favors correctness over high write throughput.
Do not deploy this first version for a high-volume shared kitchen service without
revisiting that concurrency design.

## Limits and operations

- Inventory and recipe results are paginated, with bounded queries/page sizes.
- Preview/plan services fail closed on oversized source sets; shopping changes
  are never silently truncated. Domain payloads are capped at 64 KiB of compact
  JSON before commit; the adapter also guards the raw result at 128 KiB. SDK
  responses include both readable text and structured JSON, so the actual HTTP
  body is larger than those raw-payload limits.
- MCP request bodies are capped at 16 KiB. Nginx limits all `/mcp` traffic to
  10 requests/second per address (burst 20). Tool execution is additionally limited
  to 60 calls/minute per grant **per process**. For multiple replicas, enforce a
  shared per-principal rate limit at the deployment gateway as well.
- No long-lived MCP HTTP sessions or background subscriptions are enabled.
- Access JWTs expire within 15 minutes. JWKS are cached for five minutes; ordinary
  token revocation is bounded by that token lifetime unless the app grant is removed.
- Approval records contain kitchen snapshots: protect DB backups and access like
  other app data. Do not log tokens or recipe contents. Review retention before a
  large deployment; automatic background cleanup is not included in this version.

## Validation

Run the Docker commands in `AGENTS.md`, including backend pytest and the frontend
lint/tests/build stage. For disposable PostgreSQL, include the migration/smoke and
MCP approval concurrency tests; never use a kitchen DB for those destructive tests.
CI runs backend unit tests, disposable PostgreSQL migrations/smoke, frontend checks
and Docker builds. Test tokens/keys are generated in tests, not real credentials.

Before enabling production, additionally exercise actual PKCE login and denial,
resource metadata/challenges through the public proxy, issuer key rotation,
read-only credentials, revoked grants, cross-user IDs, preview approval across
login/reload, stale previews, concurrent/repeated imports and lost-response retry
with the intended MCP client. Automated local/CI tests do not prove a live provider
or client configuration works.

Protocol references: [official SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0),
[authorization](https://py.sdk.modelcontextprotocol.io/run/authorization/),
[Supabase OAuth scopes](https://supabase.com/docs/guides/auth/oauth-server/oauth-flows),
[Auth0 token profiles](https://auth0.com/docs/secure/tokens/access-tokens/access-token-profiles).
