# Playwright image ships Chromium (/ms-playwright) plus its system deps; the pip playwright
# version below must match the tag.
FROM mcr.microsoft.com/playwright:v1.49.1-jammy

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xz-utils python3-pip \
 && rm -rf /var/lib/apt/lists/*

# shadowsocks-rust client for the ss service
ARG SS_VERSION=1.21.2
ARG TARGETARCH
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in amd64) arch=x86_64 ;; arm64) arch=aarch64 ;; *) exit 1 ;; esac; \
    curl -fsSL --retry 5 --retry-all-errors --retry-delay 3 -o /tmp/ss.tar.xz \
      "https://github.com/shadowsocks/shadowsocks-rust/releases/download/v${SS_VERSION}/shadowsocks-v${SS_VERSION}.${arch}-unknown-linux-gnu.tar.xz"; \
    tar -xJf /tmp/ss.tar.xz -C /usr/local/bin sslocal; \
    rm /tmp/ss.tar.xz; \
    sslocal --version

WORKDIR /app
COPY pyproject.toml CLAUDE.md ./
COPY src ./src
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip3 install --no-cache-dir -e . "playwright==1.49.1" pytest ruff

# Runs as the host user (see compose.yaml); HOME must be writable for Chromium.
ENV HOME=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["edu"]
