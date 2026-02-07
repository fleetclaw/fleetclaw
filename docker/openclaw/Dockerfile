FROM ghcr.io/openclaw/openclaw:2026.2.1

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends redis-tools jq && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
USER node
