# Testing decisions

This document records the per-module testing decisions for the agent engine —
what is tested at which level, and why. The general testing philosophy lives
in [testing-strategy.md](./testing-strategy.md); the module dependency graph
these decisions are based on lives in
[module-interactions.md](./module-interactions.md).

## Unit tests

Some modules are fully covered by unit tests, with no need for component or
integration tests on top:

- **skills**: the only external dep is the file system, provided by pytest's
  `tmp_path` fixture. Strictly speaking, depending on the file system goes
  against the "no external deps" rationale behind unit tests — but it's
  lightweight enough that introducing it at the unit level is legitimate and
  going further (a component test with a real file backend) wouldn't prove
  anything more.
- **config**: same external dependency (file system), same reasoning.

## Component tests

Three components are covered:

- The **a2a interface**.
- The **MCP module** (including its use of `auth.outbound` and
  `auth.context`).
- The **auth.inbound wiring**.

Notable exclusions:

- **subagents**: the only public surface beyond initialization is private
  agent-card retrieval on `RemoteA2aAgent`, which isn't compelling test
  material. Exercised through integration hot paths instead (see below).
- **skills**, **config**: fully covered by unit tests (see above).
- **auth.outbound**: doesn't stand alone — it's always exercised through
  `mcp` or `subagents`, so it's tested as part of their tests rather than as
  its own component.
- **observability**: deliberately deferred. The module is currently very
  basic; tests will be added once it's robust and rich enough to be worth
  covering.

## Integration tests

Work in progress.

Each integration test spins up a fresh agent server app and exercises a hot
path against it.

Tests are grouped by topic:

- **mcp hot paths** — the agent runtime making calls through the MCP
  module against an MCP server.
- **subagent hot paths** — the agent runtime delegating to a subagent.
- **inbound auth hot paths** — tests where the assertion is specifically
  about inbound auth behavior (bad token, expired token, missing scope,
  etc.) rather than the downstream call. The other categories exercise
  `auth.inbound` transitively; this one targets it directly.
- **skills hot paths** — the agent runtime loading and using skills
  end-to-end (distinct from the skills module's own unit tests, which test
  skills in isolation rather than the agent's use of them).

The LLM is stubbed even at integration level — it's non-deterministic and
hitting a real model on every run is expensive (see
[testing-strategy.md](./testing-strategy.md) for the full rationale).

### Test infrastructure

External dependencies are spun up with testcontainers from inside the test
suite, per session.

### Readiness and flakiness

Containers are gated at session-start by polling Keycloak's OIDC discovery
endpoint (`/realms/<realm>/.well-known/openid-configuration`) until it
returns 200. Port-open is not enough — Keycloak accepts connections well
before it's actually serving OIDC.

Inside tests: no retries, no soft timeouts, no flake tolerance. If an
integration test fails intermittently, that's a real bug (in the test, in
the production code, or in our readiness gating) and gets fixed at the
source. We can reconsider if this proves untenable in practice, but starting
permissive makes flakes invisible and they accumulate.

### Isolation between tests

Default to shared fixtures: tests use the same clients / users / scopes
declared in the static realm. Each test gets a fresh outbound-auth token
cache (cleared in a fixture) — cheap, and removes a class of cross-test
interference.

The exception is tests that genuinely need to assert on auth-specific
behavior — token expiry, scope mismatch, unknown client, etc. Those get
their own dedicated clients / users provisioned via the admin API, so they
can mutate auth state without breaking everyone else.

External servers under test (MCP server, subagent) must be stateless. Any
per-test state belongs in the test, not the server. This is a design
constraint on what we accept as a test dependency, not a tolerance to be
worked around.

### Failure observability

When a test fails, two things happen:

1. **Container logs are dumped** into the failure output via a pytest hook
   that calls `get_logs()` on every container the suite started. Most
   integration failures are "the HTTP call returned 4xx" and the _why_ lives
   in the server logs — capturing them by default removes a re-run cycle.

2. **Failed-session containers are kept alive** instead of being torn down
   at session end, so the developer can connect to them and poke around.
   Their dynamic-port connection details (Keycloak URL, MCP URL, etc.) are
   printed in the failure output so they're actually reachable. These leaked
   containers don't accumulate forever — they're reaped by the label-based
   cleanup at the start of the next session.

### Teardown and leak recovery

testcontainers stops what it started at clean session end. There's no safety
net if the test process is killed abnormally (Ctrl-C, SIGKILL, OOM, CI
cancellation) — containers will be left running.

To make this self-healing rather than relying on the developer noticing:
every container the suite spins up is tagged with a known label, and at
session start the suite kills anything still alive matching that label from
a previous run. A leaked session from yesterday gets reaped at the start of
today's session, with no manual cleanup needed.

### Seed data

Keycloak is configured by importing a static realm JSON checked in alongside
the tests. One realm, shared by every test. Tests refer to fixture client
IDs / users / scopes defined in that file.

If a test later needs a fundamentally different realm shape and we find
ourselves wanting to swap configs often, we'll revisit — likely by falling
back to admin-API provisioning for that test rather than restarting
Keycloak.
