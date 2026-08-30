# Security Policy

## Scope and threat model

This app is **single-user with no authentication, intended to run on
localhost only**. That is a design decision, not an oversight:

- Reports along the lines of "anyone who can reach the port can read/change
  data" are **out of scope** — the README tells users never to expose the app
  to the internet or an untrusted network.
- Real vulnerabilities are very much in scope. Examples of things we'd want to
  hear about: path traversal or unsafe file handling in the photo upload flow,
  SSRF via the Brave Search / weather integrations, SQL injection, or anything
  exploitable by a *remote* party even when the app is correctly deployed on
  localhost (e.g. via a malicious web page in the user's browser).

## Reporting a vulnerability

Please use **GitHub private vulnerability reporting** (Security tab →
"Report a vulnerability") rather than a public issue. You should get a
response within a week. Please include reproduction steps.

## Secrets

The app uses two API keys (`OPENROUTER_API_KEY`, `BRAVE_API_KEY`) supplied via
`.env`, which is gitignored. If you find a real key committed anywhere in the
repo or its history, report it privately as above.
