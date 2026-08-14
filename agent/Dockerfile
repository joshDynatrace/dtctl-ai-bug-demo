FROM python:3.11-slim

# Install system dependencies including gh CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    nodejs \
    npm \
    && mkdir -p /usr/share/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Install dtctl (GITHUB_TOKEN passed as build secret to avoid API rate limits)
RUN --mount=type=secret,id=GITHUB_TOKEN \
    GITHUB_TOKEN=$(cat /run/secrets/GITHUB_TOKEN 2>/dev/null || true) \
    curl -fsSL https://raw.githubusercontent.com/dynatrace-oss/dtctl/main/install.sh | sh \
    && install -m 0755 /root/.local/bin/dtctl /usr/local/bin/dtctl

# Install Python dependencies
RUN pip install --no-cache-dir requests pyyaml claude-agent-sdk

# Install Claude Code CLI used by claude-agent-sdk runtime.
RUN npm install -g @anthropic-ai/claude-code

# Run as non-root so Claude SDK bypass-permissions mode is allowed.
RUN groupadd --gid 1001 agent \
    && useradd --uid 1001 --gid 1001 --create-home --shell /bin/sh agent
USER agent
ENV HOME="/home/agent"
ENV PATH="/home/agent/.local/bin:/usr/local/bin:$PATH"

WORKDIR /github/workspace
