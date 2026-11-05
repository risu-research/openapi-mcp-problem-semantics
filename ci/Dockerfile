FROM python:3.13-slim-bookworm
ARG CNOE_COMMIT=8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/risu
COPY product/ /opt/risu/product-bundle/
COPY ci/ /opt/risu/ci/
RUN python /opt/risu/ci/unpack_product.py \
    && python /opt/risu/ci/apply_protocol_fix.py \
    && python -m venv /opt/cnoe \
    && git init -q /opt/cnoe-source \
    && git -C /opt/cnoe-source remote add origin https://github.com/cnoe-io/openapi-mcp-codegen.git \
    && git -C /opt/cnoe-source fetch --depth=1 origin "$CNOE_COMMIT" \
    && git -C /opt/cnoe-source checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/cnoe-source rev-parse HEAD)" = "$CNOE_COMMIT" \
    && /opt/cnoe/bin/python -m pip install --no-cache-dir -e /opt/cnoe-source \
    && /opt/cnoe/bin/python -m pip check \
    && /opt/cnoe/bin/python -m pip freeze > /opt/risu/product-bundle/CNOE_DEPENDENCIES.txt
# Separate version-pinned modern MCP server environment. Never overwrite CNOE's
# native dependency environment (which uses FastMCP 3.4.0).
RUN python -m venv /opt/modern \
    && /opt/modern/bin/python -m pip install --no-cache-dir 'mcp==2.3.0' 'fastmcp==4.1.6' 'fastmcp-slim==4.1.6' \
    && /opt/modern/bin/python -m pip check \
    && /opt/modern/bin/python -m pip freeze > /opt/risu/product-bundle/MODERN_MCP_DEPENDENCIES.txt
RUN chmod -R a+rX /opt/risu /opt/cnoe /opt/cnoe-source /opt/modern
ENV HOME=/tmp XDG_CACHE_HOME=/tmp/cache PATH="/opt/cnoe/bin:/usr/local/bin:/usr/bin:/bin"
USER 65534:65534
CMD ["/usr/local/bin/python","/opt/risu/ci/run_ci.py"]
