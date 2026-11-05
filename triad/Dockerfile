FROM python:3.13-slim-bookworm
ARG CNOE_COMMIT=8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f
ARG MCPGEN_COMMIT=30ee7cb9c2e923ce901e788b0d911f6547772866
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/risu
COPY dist/risu_v09_source/ /opt/risu/product/
COPY triad/ /opt/risu/triad/
# Different dependencies never collide. Verify both externally maintained source SHAs.
RUN python -m venv /opt/cnoe \
 && git init -q /opt/cnoe-source \
 && git -C /opt/cnoe-source remote add origin https://github.com/cnoe-io/openapi-mcp-codegen.git \
 && git -C /opt/cnoe-source fetch --depth=1 origin "$CNOE_COMMIT" \
 && git -C /opt/cnoe-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/cnoe-source rev-parse HEAD)" = "$CNOE_COMMIT" \
 && /opt/cnoe/bin/python -m pip install --no-cache-dir -e /opt/cnoe-source \
 && /opt/cnoe/bin/python -m pip check \
 && /opt/cnoe/bin/python -m pip freeze > /opt/risu/CNOE_DEPENDENCIES.txt
RUN python -m venv /opt/mcpgen \
 && git init -q /opt/mcpgen-source \
 && git -C /opt/mcpgen-source remote add origin https://github.com/breezykalama/mcpgen.git \
 && git -C /opt/mcpgen-source fetch --depth=1 origin "$MCPGEN_COMMIT" \
 && git -C /opt/mcpgen-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/mcpgen-source rev-parse HEAD)" = "$MCPGEN_COMMIT" \
 && /opt/mcpgen/bin/python -m pip install --no-cache-dir -e /opt/mcpgen-source \
 && /opt/mcpgen/bin/python -m pip check \
 && /opt/mcpgen/bin/python -m pip freeze > /opt/risu/MCPGEN_DEPENDENCIES.txt
RUN python -m venv /opt/fastmcp \
 && /opt/fastmcp/bin/python -m pip install --no-cache-dir 'fastmcp==4.1.6' 'fastmcp-slim==4.1.6' 'mcp==2.3.0' \
 && /opt/fastmcp/bin/python -m pip check \
 && /opt/fastmcp/bin/python -m pip freeze > /opt/risu/FASTMCP_DEPENDENCIES.txt
RUN chmod -R a+rX /opt/risu /opt/cnoe /opt/cnoe-source /opt/mcpgen /opt/mcpgen-source /opt/fastmcp
ENV HOME=/tmp TMPDIR=/tmp XDG_CACHE_HOME=/tmp/cache PATH="/opt/cnoe/bin:/usr/local/bin:/usr/bin:/bin"
USER 65534:65534
ENTRYPOINT ["/usr/local/bin/python","-B","/opt/risu/triad/run_three.py"]
