# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RESILIENCE_NFS_MOUNT=/mnt/qumulo-nfs \
    RESILIENCE_SMB_MOUNT=/mnt/qumulo-smb

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install -e ".[dev]"

COPY tests ./tests
COPY scripts ./scripts

RUN chmod +x /app/scripts/mount_protocols.sh

# --- Native protocol profile adds mount utilities ---
FROM base AS protocols

RUN apt-get update && apt-get install -y --no-install-recommends \
    nfs-common \
    cifs-utils \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/app/scripts/mount_protocols.sh"]
CMD ["pytest", "tests/unit", "tests/rest", "-v"]
