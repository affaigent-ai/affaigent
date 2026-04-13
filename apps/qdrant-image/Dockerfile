FROM qdrant/qdrant:v1.16.3

USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    openssl \
    libssl3t64 \
    openssl-provider-legacy \
 && rm -rf /var/lib/apt/lists/*

USER 1000
