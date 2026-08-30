# Security Policy

## Scope and threat model

The app runs in one of two modes, and the threat model differs:

**Local mode (default)** is **single-user with no authentication, intended to run
on localhost only**. That is a design decision, not an oversight:

- Reports along the lines of "anyone who can reach the port can read/change
  data" are **out of scope** in local mode — the README tells users never to
  expose it to the internet or an untrusted network.

**Cloud mode** (Supabase Auth + Postgres + Storage) is meant to be reachable over
the network, so in that mode access control *is* in scope:

- Every API request must carry a valid Supabase access token (ES256, verified
  against the project JWKS); every row is scoped to the authenticated user, and
  cross-user access must fail with 404. Bypasses of either are in scope.
- Row-level security is enabled (with no policies) so Supabase's auto-generated
  REST API denies direct table access with the publishable key. A way to read or
  write another user's rows through Supabase directly would be in scope.
- Uploaded photos live in a private bucket keyed by user id and are served through
  short-lived signed URLs; access to another user's photo is in scope.

In **either** mode, real vulnerabilities are very much wanted. Examples: path
traversal or unsafe file handling in the photo upload flow, SSRF via the Brave
Search / weather integrations, SQL injection, JWT verification weaknesses, or
anything exploitable by a *remote* party even when the app is correctly deployed
(e.g. via a malicious web page in the user's browser).

## Reporting a vulnerability

Please use **GitHub private vulnerability reporting** (Security tab →
"Report a vulnerability") rather than a public issue. You should get a
response within a week. Please include reproduction steps.

## Secrets

All keys live in `.env`, which is gitignored — **no key of any kind is committed
to this repository**: `OPENROUTER_API_KEY`, `BRAVE_API_KEY`, and in cloud mode
`SUPABASE_SECRET_KEY` plus the database password inside `DATABASE_URL`.

One nuance for cloud mode: the Supabase **publishable** key (`sb_publishable_…`)
is compiled into *your own* frontend build at `docker compose build` time and
delivered to browsers, because that is how Supabase browser clients authenticate
with the project. That is by design — Supabase classifies it as publishable, it
grants no data access on its own (row-level security denies direct table access),
and it is still never committed. Treat only the secret key and the database
password as secrets. If you find a real key committed anywhere in the
repo or its history, report it privately as above.
