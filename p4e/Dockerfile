FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/risu
COPY p4e/ /opt/risu/p4e/
# Freeze source bytes before dependency installation; build may reach public repositories.
RUN git init -q /opt/deepl-source \
 && git -C /opt/deepl-source remote add origin https://github.com/DeepL/openapi.git \
 && git -C /opt/deepl-source fetch --depth=1 origin 2b5e50f83888960923bf7c842e75ef2dbf309e96 \
 && git -C /opt/deepl-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/deepl-source rev-parse HEAD)" = 2b5e50f83888960923bf7c842e75ef2dbf309e96 \
 && test "$(git -C /opt/deepl-source hash-object openapi.json)" = f1029f7003e08ce82c3322bd3f6d9ad97f594ee2
RUN git init -q /opt/pydantic-source \
 && git -C /opt/pydantic-source remote add origin https://github.com/pydantic/pydantic-ai.git \
 && git -C /opt/pydantic-source fetch --depth=1 origin 61db3e988851c8905bc16c8f518a1052deccec5d \
 && git -C /opt/pydantic-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/pydantic-source rev-parse HEAD)" = 61db3e988851c8905bc16c8f518a1052deccec5d \
 && test "$(git -C /opt/pydantic-source hash-object pydantic_ai_slim/pydantic_ai/mcp.py)" = e00e00cd395da3b23a7ffff07dc47317aba0f4f0
# Isolate conversion and consumer dependencies to prevent version collisions.
RUN python -m venv /opt/fastmcp-venv \
 && /opt/fastmcp-venv/bin/python -m pip install --no-cache-dir 'fastmcp==4.1.6' 'fastmcp-slim==4.1.6' 'mcp==2.3.0' \
 && /opt/fastmcp-venv/bin/python -m pip check \
 && /opt/fastmcp-venv/bin/python -m pip freeze > /opt/risu/FASTMCP_DEPENDENCIES.txt
RUN python -m venv /opt/pydantic-venv \
 && /opt/pydantic-venv/bin/python -m pip install --no-cache-dir -e /opt/pydantic-source/pydantic_graph \
 && /opt/pydantic-venv/bin/python -m pip install --no-cache-dir -e '/opt/pydantic-source/pydantic_ai_slim[mcp]' \
 && /opt/pydantic-venv/bin/python -m pip check \
 && /opt/pydantic-venv/bin/python -m pip freeze > /opt/risu/PYDANTIC_DEPENDENCIES.txt
RUN chmod -R a+rX /opt/risu /opt/deepl-source /opt/pydantic-source /opt/fastmcp-venv /opt/pydantic-venv
ENV HOME=/tmp TMPDIR=/tmp XDG_CACHE_HOME=/tmp/cache
USER 65534:65534
ENTRYPOINT ["/opt/pydantic-venv/bin/python","-B","/opt/risu/p4e/run_integration.py"]
