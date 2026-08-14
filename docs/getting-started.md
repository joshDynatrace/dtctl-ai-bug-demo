# Getting Started

--8<-- "snippets/bizevent-getting-started.js"

This guide walks you through everything needed to run the Arc Store agentic debugging demo from scratch.

## Prerequisites

The following will be used:

- A **Dynatrace environment** with Live Debugger enabled
- A **Dynatrace Platfom Token** with scopes as defined below
- A **Dynatrace API Token** for event ingest
- An **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com/){target=_blank}

---

## 1. Configure Dynatrace

### Enable Live Debugger

In your Dynatrace tenant, make sure the [Live Debugger](https://docs.dynatrace.com/docs/observe/application-observability/live-debugger) is enabled.

### Configure OpenPipeline

Create a new Pipeline using a DQL Processor. Create a matching condition that matches error events from the `arc-store` namespace or the arc-backend container.

For example:
```bash
matchesPhrase(k8s.container.name, "arc-backend")
and
matchesPhrase(content, "NullPointerException")
```

Use a DQL processor defition like `fieldsAdd alertme = "true"`.

Create a Davis event matching the `alertme == "true"` with event.type = `ERROR_EVENT`.

Finally create a `Dynamic Route` with the same matching condition from above that triggers the pipeline you just created.

### Create a Workflow

Create a Dynatrace Workflow that:

1. Triggers on **Problem opened** events from Arc Store services
2. Creates a GitHub issue in your forked repository via the GitHub action or an HTTP request to the GitHub Issues API

The issue must meet these requirements for the agent to pick it up:

- **Title** must contain `Defect Found`
- **Body** must include the Problem ID in the format `Problem: P-XXXXXX`

You can import the workflow in the project under `Dynatrace/trigger-arc-store-problem-triage.workflow.json`

---

## 5. Configure GitHub Secrets

Go to **Repo Settings → Secrets and variables → Actions** and add the following secrets:

| Secret | Description |
|--------|-------------|
| `DT_ENV_LIVE` | Dynatrace live environment URL, e.g. `https://abc12345.live.dynatrace.com` |
| `DT_PLATFORM_TOKEN` | Dynatrace Platform token for dtctl — see scopes below |
| `DT_API_TOKEN` | Dynatrace API token for the Events ingest API (`/api/v2/events/ingest`) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude Agent SDK |

You can generate your API token from the Access Tokens app within your Dynatrace environment. Your DT_API_TOKEN should have the `Read events` and `Ingest events` scopes.

### DT_PLATFORM_TOKEN Scopes

Your platform token requires at least these scopes to allow dtctl to query logs, traces, and the Live Debugger:

- `storage:logs:read`
- `storage:metrics:read`
- `storage:spans:read`
- `dev-obs:breakpoints:set`
- `storage:application.snapshots:read`
- `storage:buckets:read`

See the full list at [dtctl token-scope docs](https://dynatrace-oss.github.io/dtctl/docs/token-scopes){target=_blank}.

!!! note "DT_ENV_APPS is derived automatically"
    The GitHub Actions workflow converts `DT_ENV_LIVE` (e.g. `https://abc12345.live.dynatrace.com`) to `DT_ENV_APPS` (e.g. `https://abc12345.apps.dynatrace.com`) — no separate secret is required.

---

## 6. Set GitHub Actions Permissions

Go to **Settings → Actions → General → Workflow permissions** and make the following changes:

1. Select **Read and write permissions**
2. Check **Allow GitHub Actions to create and approve pull requests**

This allows the agent workflow to:

- Post comments on issues
- Create fix branches
- Open pull requests

---

Next you're ready to start the codespaces.

<div class="grid cards" markdown>
- [Codespaces :octicons-arrow-right-24:](codespaces.md)
</div>
