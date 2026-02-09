FROM ghcr.io/openclaw/openclaw:v2026.2.6

USER root
RUN apt-get update && apt-get install -y --no-install-recommends redis-tools jq && rm -rf /var/lib/apt/lists/*
USER node
