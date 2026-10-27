# MCP: local quickstart and remote setup

Fridge Chef has an **optional MCP resource server** at `/mcp`, built with standalone
[FastMCP 4.1.0](https://gofastmcp.com/) and its compatible MCP SDK 2.3.0 dependency,
both pinned in `backend/requirements.txt`. It uses stateless Streamable HTTP and
exposes exactly five tools. MCP is disabled by default.

- **Try it on your own computer:** the standalone local stack below has an isolated
  SQLite kitchen, no login, and no OAuth or API keys to set up.
- **Use a real cloud kitchen:** retain `MCP_MODE=remote` (the default) and follow the
  [full authenticated setup](#remote-cloud-setup) below. Invalid remote settings fail
  closed; they never fall back to unauthenticated local access.

## Simplest local quickstart

Use a trusted local Docker host and a CLI running on that same computer. From the
repository root, with Docker and Docker Compose installed:

```sh
docker compose -f docker-compose.mcp-local.yml -p fridge-mcp-local up --build -d
docker compose -f docker-compose.mcp-local.yml -p fridge-mcp-local ps
```

Open **http://127.0.0.1:18080** for the app. The MCP URL is exactly
**http://127.0.0.1:18080/mcp**; the API is bound separately to
`127.0.0.1:18000`. Wait for the backend to be healthy before connecting a client.
If either port is occupied by another preview, stop that known preview first;
do not change the local MCP address or ports.

This is a standalone Compose file, not a profile or an override to merge with the
normal/cloud stack. It does not pass a host `.env` file or interpolate credentials
into the containers. It explicitly sets `MCP_ENABLED=true`, `MCP_MODE=local`,
`SUPABASE_URL` empty, and `MCP_RESOURCE_URL=http://127.0.0.1:18080/mcp`. The frontend
is built without Supabase settings. Auth0, client registration, credentials, and
OAuth login are **not needed** for this quickstart.

The project-scoped `local-kitchen` named volume starts empty on first use and is
separate from `./data` and any cloud kitchen. Finish onboarding in the app and add
inventory manually. You can use saved recipes where the existing UI supports them;
recipe imports with structured recipe data can work without AI, but pasted text or
unstructured pages need an AI key. This stack deliberately has no OpenRouter or
Brave keys, so AI photo extraction, meal generation, and AI recipe transcription
are unavailable. MCP itself never makes a paid AI call. Empty inventory/recipe
results are expected initially; `get_current_plan` reports an error until a plan
exists. No demo plan or kitchen data is created by startup.

### Connect one local CLI

Use one of these configurations. Do not add OAuth settings, bearer headers, client
secrets, or an MCP login step. Local mode does not advertise OAuth metadata.
Restart the client's session if it does not reload new servers automatically.

**Claude Code:**

```sh
claude mcp add --transport http fridge-local http://127.0.0.1:18080/mcp
claude mcp get fridge-local
```

**Codex CLI:**

```sh
codex mcp add fridge-local --url http://127.0.0.1:18080/mcp
codex mcp get fridge-local
```

**OpenCode:** merge this entry into your existing `opencode.json` or `opencode.jsonc`,
preserving other settings:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "fridge-local": {
      "type": "remote",
      "url": "http://127.0.0.1:18080/mcp",
      "oauth": false,
      "enabled": true
    }
  }
}
```

Then run `opencode mcp list`. OpenCode's `remote` type means an HTTP connection,
even when the server is on this computer; its `local` type is for stdio commands.
These settings follow the official [Claude Code](https://code.claude.com/docs/en/mcp),
[Codex](https://developers.openai.com/codex/mcp), and
[OpenCode](https://opencode.ai/docs/mcp-servers/#disabling-oauth) docs, checked on
2026-10-12. Configuration examples do not certify an untested client release.

Ask the client: “Use fridge-local to list my inventory, then search my saved
recipes.” It should discover the five tools in the next section. All local CLI
connections share the same single kitchen and local client identity; there is no
per-client OAuth scope or identity boundary in this mode.

### Local shopping still needs review

With a ready plan in this isolated kitchen:

1. Ask the client to call `preview_plan_shopping` for that plan. Preview creates
   an expiring approval record without changing the shopping list.
2. Open the returned `approval_url` on **http://127.0.0.1:18080**. Finish onboarding
   if needed, then review the exact before/add/after quantities in the app. Local
   mode has no sign-in step.
3. Click **Approve these changes** only when correct, or **Decline request**.
4. Ask the client to call `import_plan_shopping` with the same `approval_id`.
   Importing before approval fails; approval alone does not import anything.
5. Check Shopping, then retry that same import once. It returns the saved result
   without adding duplicate quantities. Kitchen changes make an unconsumed preview
   stale; request a fresh preview and review it again.

Only HTTP CLI MCP clients are supported locally. **Any `Origin` header is rejected
at `/mcp`, including the app's own origin**; do not strip browser security headers
or add a browser-MCP exception. The normal browser app and its approval page still
work through the first-party REST routes.

**Local mode is an accident guard, not a security boundary against other programs
on the same host.** The approval screen encourages deliberate human review, but
there is no login isolating it from a local program that can call the REST API.
Other local clients also share the same MCP identity. Only run this on a computer
and Docker host you trust. Loopback port bindings are the exposure boundary;
a `Host` header or a proxy's claimed client IP does not prove that a caller is local.
Never expose this stack through a tunnel, public reverse proxy, remote Docker host,
changed bind address/ports, or a merged cloud Compose configuration. Use the
separate authenticated remote setup for network access.

### Stop or reset the isolated kitchen

Stop the stack while preserving its local kitchen:

```sh
docker compose -f docker-compose.mcp-local.yml -p fridge-mcp-local down
```

To deliberately erase **this isolated kitchen**, add `--volumes`. This permanently
deletes the named volume's inventory, recipes, plans, approvals, and uploaded files;
use it only when that test data is no longer needed:

```sh
docker compose -f docker-compose.mcp-local.yml -p fridge-mcp-local down --volumes
```

Keep the same Compose file and project name in these commands. They do not target
the normal stack's `./data` or cloud database. Removing a CLI entry stops that
client's connection but does not revoke access for other local processes; stop
the stack to turn local access off.

## What you can do

| Tool | Required remote scopes | Inputs | Result / effect |
| --- | --- | --- | --- |
| `read_inventory` | `fridge:read` | `query`, `limit` (1–100), `offset` | Inventory quantities, storage and estimated expiry |
| `search_recipes` | `fridge:read` | `query`, `favorites_only`, `limit` (1–50), `offset` | Saved/favourite recipes with current stock annotations; no AI call |
| `get_current_plan` | `fridge:read` | None | Newest-created plan, dates, recipes and generation status |
| `preview_plan_shopping` | Both scopes | Optional `plan_id` | Stores an expiring exact shopping preview and returns an approval URL |
| `import_plan_shopping` | Both scopes | `approval_id` from that preview | Applies a human-approved, unchanged preview; retry-safe |

`query` is at most 100 characters and `offset` is 0–10000. Missing `plan_id` uses
the newest-created plan, which may not be this calendar week. Shopping preview
requires a ready plan. Only its remaining **suggested** meals contribute groceries;
cooked meals and delivery nights do not.

No tool accepts a user ID or creates an account. Photos, email, preferences and
feedback have no MCP tools. Unknown quantities or incompatible units stay **check**,
not “in stock”; expiry remains an estimate. Recipe and inventory text is untrusted
data, never instructions. In remote mode, tool availability in a client is not proof
of permission: a read-only grant may discover all five tools, but cannot execute
either shopping tool. Local mode makes all five available to the one local kitchen;
shopping import still requires the persisted approval.

## Remote cloud setup

The remaining numbered setup steps are for `MCP_MODE=remote`. The repository does
not provision an OAuth provider, register clients, create account mappings, or deploy
anything. The Auth0 recipe below is based on official documentation, not a completed
live tenant/client acceptance test. Verify your intended client before exposing a
real kitchen; the local quickstart is not a substitute for these checks.

## 1. Prepare the cloud app

1. Finish [normal cloud setup](../README.md#cloud-mode-with-supabase): working Supabase
   login, PostgreSQL and HTTPS, with `SUPABASE_URL` set. Do not replace the app's
   Supabase configuration with Auth0 configuration.
2. Sign in to the real app as the kitchen owner and load a page. The backend creates
   its `users` row on the first authenticated request; an Auth-only account that
   has never used the app is insufficient for an MCP grant.
3. Choose one canonical public URL, for example `https://fridge.example.com/mcp`.
   Use that exact value everywhere, including the `/mcp` path and **no trailing
   slash**, alternate hostname, query or fragment. All configured MCP URLs must
   be HTTPS. Keep port 8000 private and retain the normal loopback Compose binds.
4. Keep `MCP_ENABLED=false` until the provider, client and mapping are ready. Use a
   separate staging deployment and synthetic kitchen for acceptance testing.

There are two independent logins: the OAuth provider authorizes the MCP client;
Supabase signs the human into the Fridge Chef website to review shopping changes.
The app's REST API rejects delegated OAuth credentials, including at approval
endpoints. MCP tokens are never forwarded to Supabase or another service.

## 2. Configure a dedicated OAuth provider (Auth0 example)

The provider must support authorization code with PKCE/S256, discovery, exact
redirect registration, and the access-token contract below. Supabase's current
OAuth server supports OIDC scopes, not custom `fridge:*` API scopes. This server
therefore rejects the normal Supabase issuer. Do not substitute an ordinary
Supabase session or add a client-side “scope” label to it.
([Supabase scopes](https://supabase.com/docs/guides/auth/oauth-server/oauth-flows#available-scopes))

### Create the API

In Auth0 Dashboard → Applications → APIs, create a dedicated API:

| Setting | Example / required value |
| --- | --- |
| Name | `Fridge Chef MCP` |
| Identifier | `https://fridge.example.com/mcp` |
| JWT signing algorithm | `RS256` |
| JWT profile | `RFC 9068` |
| Maximum access-token lifetime | `900` seconds or less |
| Implicit/hybrid token lifetime | `900` seconds or less; those flows are not used |
| JSON Web Encryption | Off; this resource server accepts signed JWTs, not JWE |
| API permissions | `fridge:read` and `fridge:shopping` |
| Allow skipping user consent | Off for this setup |

Save the changes. The default Auth0 token profile is incompatible: the RFC 9068
profile supplies the required access-token type, `client_id` and `jti`.
([API settings](https://auth0.com/docs/get-started/apis/api-settings),
[token profiles](https://auth0.com/docs/secure/tokens/access-tokens/access-token-profiles))

Enable RBAC for this API, then assign `fridge:read` to the intended Auth0 user
through User Management → Users → the user → Permissions. Assign
`fridge:shopping` only when they want shopping access. The server reads the JWT's
`scope` string, not a separate `permissions` array: with RBAC, requested scopes must
also be assigned to that user. Do not assume defining an API permission grants it.
([Enable RBAC](https://auth0.com/docs/get-started/apis/enable-role-based-access-control-for-apis),
[assign permissions](https://auth0.com/docs/manage-users/access-control/configure-core-rbac/rbac-users/assign-permissions-to-users))

In tenant Settings → Advanced → Settings, enable **Resource Parameter
Compatibility Profile**. MCP clients send RFC 8707 `resource`; this makes Auth0
use it to select the API audience. A tenant-wide change should be reviewed for its
other applications before enabling it.
([Auth0 MCP resource compatibility](https://support.auth0.com/center/s/article/mcp-audience-error-with-auth0))

### Register one public native client per CLI

Create a separate Auth0 **Native** application for each client you intend to use,
for example `Fridge Chef – Claude Code`, `Fridge Chef – Codex` and
`Fridge Chef – OpenCode`. Record each generated **Client ID**. Use public-client
authentication (`token_endpoint_auth_method=none`), enable Authorization Code,
and ensure the intended identity connection is enabled for that application.
Do not use the API's automatically generated machine-to-machine test application.
Do not distribute a client secret to a CLI.
([Application settings](https://auth0.com/docs/get-started/applications/application-settings),
[Native PKCE settings](https://support.auth0.com/center/s/article/Login-failed-PKCE-NOT-ALLOWED-error-after-logging-in-on-a-Native-application))

Register the exact **Allowed Callback URL** from the client section below.
`localhost` and `127.0.0.1` are different redirect hosts. These HTTP loopback
callbacks are on the CLI user's computer; the MCP server and issuer remain HTTPS.
Use the browser on that same computer for the first test. Do not register a wildcard
callback or the Fridge Chef approval URL as the CLI callback.

Start without offline access. A 15-minute token may require another browser login.
If you intentionally enable refresh tokens later, review Auth0's refresh-token
rotation/expiry settings and the chosen client's behavior. Refresh tokens do not
remove the app's per-request grant checks.

### Required token contract

Before production, obtain a real access token through the registered client's
PKCE flow and confirm that the server accepts it. If inspecting claims locally,
never paste a real token into an online decoder, issue, chat or log. Decoding alone
does not verify identity or signature. The verifier requires all of:

- Header `typ` = `at+jwt` or `application/at+jwt`; algorithm `RS256` or `ES256`
- `iss` exactly equals `MCP_ISSUER_URL`, including the trailing slash if present
- `aud` is the **single string** `https://fridge.example.com/mcp`; arrays fail
- Nonempty string `sub`, `client_id` and `jti`
- Integer `iat` and `exp`, with `0 < exp - iat <= 900`, valid current timestamps
- Space-delimited string `scope`, containing at least `fridge:read`
- A matching `(sub, client_id)` grant and an existing app `users.id`

Request only `fridge:read` initially; add `fridge:shopping` for shopping access.
Avoid `openid`, `profile` and `email` in this setup: an additional Auth0 UserInfo
audience can produce an audience array, which this implementation rejects. An ID
token is not an access token. If a provider/client cannot issue this exact contract,
it is unsupported; do not weaken the verifier to make login appear to work.

## 3. Verify the identity mapping and grant access

`MCP_GRANTS` is the authorization allowlist. It lives in backend environment
configuration, **not in a database grants table**. Each row binds an OAuth provider
subject and registered client to exactly one existing Fridge Chef user.

1. In the Supabase dashboard's Authentication → Users, identify the kitchen owner
   and copy their **User UID**. Verify this is the account they use in the app.
2. In Auth0 User Management → Users, verify that the same person controls the
   intended provider account and copy its **User ID**, such as `auth0|…`. Preserve
   the full value, including its prefix; never invent it or substitute an email.
3. Have the person confirm the account association and requested access. Use known
   account records and authenticated account ownership; matching email addresses,
   UUID-shaped text or an unverified JWT are not sufficient proof.
4. Verify the app row exists. An administrator can inspect the `users` table or
   run this read-only query in the app's PostgreSQL database, replacing the fake ID:

   ```sql
   SELECT id, created_at, last_seen_at
   FROM public.users
   WHERE id = '6d452110-890f-41d0-9a52-f0a47de4a8bb';
   ```

   Expect exactly the intended user's row. If absent, have them sign in to Fridge
   Chef and load their kitchen, then check again. Do not insert a dummy user to
   satisfy the verifier. Do not map to the local-mode UUID.
5. Copy the Client ID from the specific Auth0 application you registered. A
   different CLI needs its own row even for the same person and kitchen.

Put these values in the deployment's private `.env` (one-line JSON). This fake
example starts read-only and will not authenticate a real account:

```dotenv
MCP_ENABLED=true
MCP_MODE=remote
MCP_RESOURCE_URL=https://fridge.example.com/mcp
MCP_ISSUER_URL=https://example-tenant.us.auth0.com/
MCP_JWKS_URL=https://example-tenant.us.auth0.com/.well-known/jwks.json
MCP_GRANTS='[{"subject":"auth0|example-user-id","client_id":"example-claude-client-id","user_id":"6d452110-890f-41d0-9a52-f0a47de4a8bb","scopes":["fridge:read"]}]'
```

Get the issuer and `jwks_uri` from the provider's discovery document, for example
`https://example-tenant.us.auth0.com/.well-known/openid-configuration`. Do not mix
a custom-domain issuer with a different tenant issuer. These are non-secret URLs
and identifiers, but account mappings remain private administrative configuration.
Never put MCP settings in `VITE_*`, commit `.env`, or add access tokens here.

For shopping access, after the person's consent, assign the provider permission,
change that row's scopes to `["fridge:read","fridge:shopping"]`, recreate every
backend replica, and log in again requesting both scopes. **Both** the token and
the grant must allow the operation. Every grant must include `fridge:read`; unknown
scope names, duplicate subject/client pairs, an empty grant list, or more than
1000 grants fail startup. No wildcard client or subject grants are supported.

## 4. Start behind the public HTTPS proxy

The included frontend nginx config proxies exact `/mcp` and
`/.well-known/oauth-protected-resource/mcp` paths to the backend. They must never
be rewritten to `index.html`. If you have an outer TLS proxy, forward those paths
unchanged to the frontend, preserving the public `Host` (including a nondefault
port), `Authorization`, `Origin`, `Accept`, `Content-Type` and MCP protocol headers.
Do not add an `Origin` to CLI traffic. Keep the normal `/api/` and SPA routes too.
Only the configured host and, when present, the same-origin `Origin` are accepted.
Cross-origin browser MCP clients are not enabled in this version.

After you have reviewed the configuration and backed up the existing database,
run from the repository root on the deployment host:

```sh
docker compose up -d --build --force-recreate backend frontend
docker compose ps
docker compose logs --tail=80 backend
```

Startup runs Alembic migrations, including the persisted shopping-approval table.
Invalid enabled MCP configuration fails startup. Do not run the destructive test
suite against this deployment. For only a later grant/environment change, use
`docker compose up -d --no-deps --force-recreate backend`; `docker compose restart`
does not reload a changed Compose `env_file`. Apply the equivalent rollout to
**all** replicas in other deployment systems.

Check these unauthenticated requests through the actual public proxy:

```sh
MCP_ORIGIN=https://fridge.example.com
curl --silent --show-error --fail-with-body \
  "$MCP_ORIGIN/.well-known/oauth-protected-resource/mcp"

curl --silent --show-error --include \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"fridge-smoke","version":"1.0"}}}' \
  "$MCP_ORIGIN/mcp"
```

The first response must be JSON with `resource` equal to the exact MCP URL,
`authorization_servers` containing the configured issuer, and `scopes_supported`
containing both scope names. The second must be **401** with a `WWW-Authenticate`
Bearer challenge whose `resource_metadata` URL identifies that metadata endpoint.
A 200 HTML response is a routing bug, not a working MCP server. A plain GET to
`/mcp` returns 405 in this stateless transport; use the POST above for the auth
challenge. Disabled MCP returns 404 at the backend. Follow the discovered issuer metadata and confirm
its authorization, token and JWKS endpoints are reachable from the relevant
client/backend networks before attempting login.

## 5. Connect a CLI

Use a current official client release supporting the shown settings. The examples
were checked against official docs on 2026-10-12 and, for Codex 0.162.1/OpenCode
1.19.0, their released source. This is **configuration verification, not live OAuth
interoperability certification**. Keep a record of the client version used for
your acceptance test. If your version rejects a key/flag, upgrade through that
client's official distribution; do not silently omit the client ID or scope.

Use your actual URL and the corresponding registered public Client ID. Do not
configure a static bearer header at the same time as OAuth. The application does
not perform dynamic client registration; a client's automatic registration at the
provider would still need a verified exact-ID grant here.

### Claude Code

Register `http://localhost:8765/callback` in that Auth0 Native application, then:

```sh
claude --version
claude mcp add-json --scope user fridge \
  '{"type":"http","url":"https://fridge.example.com/mcp","oauth":{"clientId":"example-claude-client-id","callbackPort":8765,"scopes":"fridge:read"}}'
claude mcp get fridge
claude mcp login fridge
```

Alternatively, open Claude Code and use `/mcp` to authenticate `fridge`. For
shopping, set `oauth.scopes` to `fridge:read fridge:shopping` and reauthenticate
after changing the server grant. No `--client-secret` is needed for this public
client. Claude Code 2.1.229 used `127.0.0.1` for this callback; use an updated
release or register the exact URI your installed release sends.
([Official Claude Code MCP configuration](https://code.claude.com/docs/en/mcp#use-pre-configured-oauth-credentials))

### Codex CLI

Before adding the server, put these **top-level** entries in your existing
`~/.codex/config.toml` (before any `[table]` header). They affect MCP OAuth callbacks
for other servers too, so preserve/review any existing values:

```toml
mcp_oauth_callback_port = 8766
mcp_oauth_callback_url = "http://127.0.0.1:8766/callback"
```

```sh
codex --version
codex mcp add fridge --url https://fridge.example.com/mcp \
  --oauth-client-id example-codex-client-id \
  --oauth-resource https://fridge.example.com/mcp
```

`add` prints an **OAuth callback URL** and may immediately attempt login. Register
that exact URL in Auth0; if login started before registration, cancel it and retry
below. Keep any appended `/callback/<id>` suffix: it depends on issuer discovery
and protects against mixing up authorization servers. Do not guess this suffix or
replace the saved `[mcp_servers.fridge.oauth].callback_url` with a generic callback.

```sh
codex mcp login fridge --scopes fridge:read
codex mcp get fridge
codex mcp list
```

For shopping, use `--scopes fridge:read,fridge:shopping` after updating the grant.
The explicit scope flag is verified in released 0.162.1 code. The static server
grant remains the authorization ceiling regardless of discovery/client defaults.
([Codex MCP](https://developers.openai.com/codex/mcp),
[released CLI flags](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/cli/src/mcp_cmd.rs),
[callback behavior](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/rmcp-client/src/oauth_callback.rs))

### OpenCode

Register `http://127.0.0.1:19876/mcp/oauth/callback` in the OpenCode Auth0
application. Merge this into your OpenCode configuration without replacing other
settings (project `opencode.json`, or your existing user configuration):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "fridge": {
      "type": "remote",
      "url": "https://fridge.example.com/mcp",
      "oauth": {
        "clientId": "example-opencode-client-id",
        "scope": "fridge:read",
        "callbackPort": 19876
      }
    }
  }
}
```

```sh
opencode --version
opencode mcp auth fridge
opencode mcp list
```

Use `scope: "fridge:read fridge:shopping"` for shopping and reauthenticate.
`scope` is singular here; Claude Code's `scopes` key is different. OpenCode 1.19.0's
released schema/provider confirm the callback port and URL shown. No client
secret is needed. `opencode mcp debug fridge` helps diagnose discovery failures;
review its output privately before sharing any logs.
([OpenCode MCP](https://opencode.ai/docs/mcp-servers/),
[released schema](https://github.com/anomalyco/opencode/blob/v1.19.0/packages/core/src/v1/config/mcp.ts),
[released OAuth provider](https://github.com/anomalyco/opencode/blob/v1.19.0/packages/opencode/src/mcp/oauth-provider.ts))

## 6. Use the tools and approve shopping

Start with a read-only grant and ask the connected client:

- “Use Fridge Chef to list the first 20 inventory items. Tell me which quantities
  need checking and which expiry dates are estimates.”
- “Search my saved recipes for chicken, including their current stock notes.”
- “Show my newest-created plan and its dates. Don't assume it's this week.”

Empty inventory/recipe results can be legitimate. If there is no saved plan,
`get_current_plan` returns a tool error; create one in the regular app when wanted.
These MCP tools do not generate plans or call paid AI services.

After granting both scopes, use a staging plan with known shortages for this
write-flow test:

1. Ask: “Preview shopping for plan 42 and show me the approval link. Wait while I
   review it.” Substitute your actual plan ID, or omit it for the newest plan.
2. The client calls `preview_plan_shopping`. Check the returned `approval_url`,
   `approval_id`, `expires_at`, `changes`, `check`, and assumed staples. Preview
   writes an approval record, but **does not change the shopping list**. The
   default approval lifetime is 15 minutes; an identical pending preview may
   reuse its record rather than extend the deadline.
3. Open the returned URL on your real Fridge Chef origin, sign in with the mapped
   **Supabase** account, and review the requesting client ID, plan, each item,
   before/add/after quantities and expiry. Unknown/check amounts are excluded
   from the import. Click **Approve these changes** only if the delta is right.
4. Return to the client: “I've approved it in Fridge Chef. Import approval
   `<approval_id>`.” The client calls `import_plan_shopping` with that same ID.
   Approval itself does not import; importing before approval must fail.
5. Open Shopping in the app and confirm the exact delta. Repeat the same import
   once: it must return the stored result without adding the items again.

A model saying `confirmed=true`, possessing an approval ID, clicking the link, or
using an MCP token at an approval endpoint cannot approve changes. The human can
choose **Decline request** or, while approved but unused, **Revoke approval**.
Leaving the page keeps a pending request pending. If a decision response is lost,
use **Reload approval** to inspect its saved status before trying another decision.

If stock, plan, relevant recipes, staples or shopping state changes before import,
the preview becomes stale. Request a new preview and review it again. A completed
import's same-ID retry remains safe even after later edits or expiry. The ordinary
app's original plan-import key is shared, so a second preview cannot add that
original plan twice; the app's intentional “add again” action is separate.

### Preserve approval links through Supabase login

In Supabase Authentication → URL Configuration, keep the normal Site URL and
allow `https://fridge.example.com/mcp-approvals/*` for email-link redirects on this
exact app origin. This restricted single-segment pattern covers the UUID path;
do not use a wildcard host. Password login and onboarding preserve the current
path. Test an approval link in a logged-out browser, email login, reload and
Back/Forward. The implementation does not change your project's redirect settings.
([Supabase redirect configuration](https://supabase.com/docs/guides/auth/redirect-urls))

## 7. Optional protocol smoke test with curl

Prefer the actual CLI login test above. For protocol diagnostics, an operator can
use a short-lived access token already obtained through an authorized PKCE client.
There is no shared-key shortcut or bundled token-issuing command. Do not extract
another user's credentials, use a Supabase session, or use an Auth0 client-credentials
test token. Do not enable shell tracing, print the token, or save it in history.

These Bash examples need curl with `--fail-with-body`. They pass the authorization
header on stdin instead of putting the token in curl's command-line arguments.
Run privately: successful responses contain kitchen data.

```sh
MCP_URL=https://fridge.example.com/mcp
MCP_PROTOCOL_VERSION=2025-11-25
read -r -s -p 'Short-lived MCP access token: ' MCP_ACCESS_TOKEN
printf '\n'

mcp_rpc() {
  printf 'header = "Authorization: Bearer %s"\n' "$MCP_ACCESS_TOKEN" |
    curl --silent --show-error --fail-with-body --config - \
      -H 'Content-Type: application/json' \
      -H 'Accept: application/json, text/event-stream' \
      -H "MCP-Protocol-Version: $MCP_PROTOCOL_VERSION" \
      --data-binary "$1" "$MCP_URL"
  printf '\n'
}

mcp_rpc '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"fridge-smoke","version":"1.0"}}}'
```

Expect an initialize result with tool capability. Set `MCP_PROTOCOL_VERSION` to
its returned `result.protocolVersion` if different, then continue. This server is
stateless; there is no `Mcp-Session-Id` to save. The initialized notification may
return an empty 202 response. A successful HTTP status can still contain an MCP
`error` or a tool `result.isError: true`; inspect the body.

```sh
mcp_rpc '{"jsonrpc":"2.0","method":"notifications/initialized"}'
mcp_rpc '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
mcp_rpc '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_inventory","arguments":{"limit":20,"offset":0}}}'
mcp_rpc '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"search_recipes","arguments":{"query":"chicken","favorites_only":false,"limit":10,"offset":0}}}'
mcp_rpc '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"get_current_plan","arguments":{}}}'
```

Expect exactly the five names listed above. Successful tool results provide JSON
structured content plus readable text. To exercise the two write-capable tools,
use **both** scopes and a ready staging plan. This preview defaults to the newest
plan; add `"plan_id":42` inside `arguments` to select a verified plan ID:

```sh
mcp_rpc '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"preview_plan_shopping","arguments":{}}}'
read -r -p 'approval_id from the preview: ' MCP_APPROVAL_ID
mcp_rpc "{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"tools/call\",\"params\":{\"name\":\"import_plan_shopping\",\"arguments\":{\"approval_id\":\"$MCP_APPROVAL_ID\"}}}"
```

The first import must fail while pending. Have the human open `approval_url` and
approve in the app, then repeat that import request. Expect `status: imported`,
or `already_imported` if the plan's original import already exists. Repeat once
more and confirm the identical stored result and no duplicate shopping quantities.
With only `fridge:read`, both preview and import must fail with insufficient scope.

When finished:

```sh
unset MCP_ACCESS_TOKEN MCP_APPROVAL_ID
unset -f mcp_rpc
```

Do not make the approval POST with curl as a substitute for the review screen.
Keep separate staging cases for rejection, expiry, wrong user/client, stale state,
and revoked grants; do not destructively test those against someone's real kitchen.

## Revocation, limits and operations

The grant, provider, and edge-revocation steps below apply to remote mode. For local
mode, [stop the isolated stack](#stop-or-reset-the-isolated-kitchen).

- **Revoke a client/person:** remove the corresponding `MCP_GRANTS` row and recreate
  all backend replicas. If it was the last row, set `MCP_ENABLED=false` too: enabled
  MCP with no grants fails startup. Keep remaining mappings unchanged. Recheck
  with that client's previously working token; subsequent requests must be denied.
- **Emergency stop:** block `/mcp` at the edge first, then set `MCP_ENABLED=false`
  and roll out all backends. Requests already in progress may have committed;
  inspect the shopping receipt instead of assuming they were cancelled.
- **Read-only downgrade:** remove `fridge:shopping` from that grant, roll out, and
  remove the provider permission. An old token cannot exceed the new app grant.
  Removing/reducing a grant does not undo an already-imported shopping change.
- **Also clean up provider/client sessions:** revoke the Auth0 authorization/refresh
  tokens and log out the CLI where appropriate. Provider logout alone need not
  invalidate an already-issued JWT. Access-token lifetime is at most 15 minutes;
  JWKS are cached for five minutes. This version has no online token introspection.
- **Bounds:** inventory/recipe queries are paginated. Preview/plan operations fail
  closed on oversized source sets. Domain JSON is capped at 64 KiB before commit;
  the adapter also caps raw results at 128 KiB. Wire bodies are larger because
  results include readable text and structured content. Changes are never silently
  truncated to fit.
- **Rate limits:** MCP bodies are capped at 16 KiB. Included nginx limits `/mcp` to
  10 requests/second per address, burst 20; tool calls are limited to 60/minute per
  subject/client grant **per process**. Multiple replicas need a shared per-principal
  gateway limit. Configure trusted proxy address handling at your edge.
- No long-lived MCP HTTP sessions, subscriptions or background notifications are
  enabled. There is no grant-administration UI or automatic grant provisioning.
- Approval snapshots use the existing DB and need the same access/backup protection
  as kitchen data. Automatic background retention cleanup is not included. Never
  log tokens or kitchen/recipe payloads while diagnosing an error.
- PostgreSQL table locks serialize short preview/approve/import critical sections
  against existing UI writes. This prioritizes correctness over high write
  throughput; revisit the design before a high-volume shared-kitchen deployment.

## Troubleshooting

| Symptom | Check / action |
| --- | --- |
| Local stack will not start | Ports 18080/18000 must be free; use only the standalone Compose file and its fixed URL, empty Supabase/OAuth settings, and `MCP_MODE=local`; inspect backend logs privately |
| Local client asks for OAuth | Confirm the exact loopback URL, `MCP_MODE=local`, and the new `fridge-local` entry without saved remote OAuth settings; do not create provider credentials for this quickstart |
| Remote backend refuses startup | `MCP_MODE=remote`, cloud `SUPABASE_URL`, HTTPS URLs, exact `/mcp` path, dedicated issuer, valid nonempty one-line grants JSON; there is no unauthenticated fallback |
| Metadata or `/mcp` returns HTML | Exact proxy locations are missing, an outer proxy rewrites to the SPA, or the client used `/mcp/` instead of `/mcp` |
| 404 | MCP is disabled, the backend was not recreated with new env, or the request reached the wrong route |
| Host/Origin rejection | Local clients must use exact `http://127.0.0.1:18080/mcp` and send no `Origin`; every browser MCP Origin is rejected. Remotely, public Host must match the configured resource host; do not use `*` allowlists |
| OAuth requests UserInfo / wrong audience | Resource compatibility is off, resource does not match API Identifier, or OIDC scopes introduced a second audience |
| Redirect mismatch | Register the exact URI sent by this client/version, including hostname, port and any Codex suffix |
| Login succeeds but MCP returns 401 | Check access-token type/profile, exact issuer/single audience, <=900-second lifetime, `client_id`, verified `sub`, grant and existing app-user row; check clock sync and JWKS reachability |
| Insufficient scope | Both JWT `scope` and grant need the permission; defining an Auth0 permission is not assigning it; request it in a fresh login |
| Tools appear but a write fails | Discovery includes all five names; a read-only grant still blocks shopping calls |
| No plan / plan not ready | Open the app, select or finish the intended plan; MCP does not generate one |
| Approval missing after login | Supabase redirect allowlist or wrong signed-in kitchen; reopen the exact link |
| Pending, denied, expired or stale import | Review/approve a current pending preview, or make a new preview and approve it; never reuse a denied or stale request |
| Approved but nothing changed | Approval waits for the client to import; inspect `already_imported` and the proposed delta; check items are excluded |
| Lost import response | Retry the same approval ID; do not create another request just to retry |
| 413 / oversized source error | Reduce request/result scope where possible; clean up or use the regular app; do not raise bounds blindly |
| 429 | Wait for the rate window; check pending approvals (maximum 20 active per user), proxy limits and client retry loops |
| OAuth setup/flags unsupported | Upgrade the intended CLI and verify official docs; do not fall back to a shared static app token |

## Validation and release gate

Run the Docker-only backend and frontend checks in [AGENTS.md](../AGENTS.md).
Use the isolated [PostgreSQL test stack](../README.md#tests) for migration,
smoke and MCP concurrency tests; those database tests are destructive. CI covers
unit tests, disposable PostgreSQL migrations/smoke, frontend checks and builds. The
`local-mcp-browser` CI job is configured to build the standalone local stack and
run Chromium checks in Docker against a synthetic kitchen, including desktop/mobile
and light/dark views, with screenshots uploaded for inspection. A configured job
is not a passing result; inspect the checks on the exact PR commit.
Generated test tokens/keys are synthetic, not live provider credentials. For local
MCP, verify discovery and all five tools against the isolated Docker stack, denial
of browser-origin MCP requests, and preview → human approval → import → same-ID
replay. Keep automated browser coverage distinct from manual visual QA; the latter
and the approval screen's `design.pen` update remain tracked in
[project notes](project-notes.md#deferred-ui-validation).

Before enabling production, record successful **live** tests of:

- Public-proxy discovery and 401 challenges; PKCE login and consent denial
- Actual issued JWT contract, readonly behavior, issuer key rotation and grant revocation
- Cross-user/client denial, all five tools and normal app-login isolation
- Approval deep links across login/reload, phone/light/dark layouts, rejection,
  expiry, stale data, concurrent imports and lost-response replay

Local/CI success cannot establish that your Auth0 tenant, proxy, Supabase redirects
or CLI OAuth flow is correct. This change does not claim those live checks were run.
