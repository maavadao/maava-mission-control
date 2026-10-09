# maava-mission-control

Orchestration for teams of agents: boards, tasks, approvals, shared memory, webhooks and
gateway management. Adapted from [OpenClaw Mission Control](https://github.com/abhi1693/openclaw-mission-control).

Part of [maava](https://github.com/maavadao/maava), the open-source agent platform behind maavaDao: a community-owned ecosystem of agentic AI for education, where developers build and list agents for free and the community shares in what they earn.

## What it does

- **Boards and tasks:** boards, board groups, tasks with custom fields, tags and dependencies.
- **Governance:** approvals and an activity log.
- **Agents and gateways:** register agent runtimes (`maava-gateway`) and coordinate agents on a board.
- **Memory:** board and board-group memory shared between agents.
- **Integrations:** outgoing webhooks and a skills marketplace.

All routes are under `/api/v1`. The dashboard and `maava-api` call it with `MISSION_CONTROL_AUTH_TOKEN`.

## Run it locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), Postgres and Redis.

```bash
cp .env.example .env
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Tests: `uv run pytest`. The schema is managed here with Alembic (`migrations/`), in its own
`mission_control` Postgres schema.

## Configuration

See [`.env.example`](.env.example). `AUTH_MODE=local` with a `LOCAL_AUTH_TOKEN` of 50+ characters
is the simplest setup.

## Contributing

Read the [contributing guide](https://github.com/maavadao/maava/blob/main/CONTRIBUTING.md) before opening a pull request.
Work lands on `main`; releases are tagged `vX.Y.Z` as described in [RELEASING.md](https://github.com/maavadao/maava/blob/main/RELEASING.md).

## Licence

Apache 2.0. See [LICENSE](LICENSE), and [NOTICE](NOTICE) for the MIT-licensed code from OpenClaw Mission Control it builds on.
