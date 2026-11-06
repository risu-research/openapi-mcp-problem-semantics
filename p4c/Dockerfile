FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/risu
COPY p4c/ /opt/risu/p4c/
ARG LANGCHAIN_SHA=bb6a25a878527136dcb1a20507d5c20049427f96
ARG AGENTS_SHA=d4f07df2915ddb029d7076595bb7d4ce89322308
ARG PYDANTIC_SHA=61db3e988851c8905bc16c8f518a1052deccec5d

# Public source checkout only. SHA and Git blob identities must match before
# any installation. All execution happens later with --network none.
RUN git init -q /opt/langchain-source \
 && git -C /opt/langchain-source remote add origin https://github.com/langchain-ai/langchain.git \
 && git -C /opt/langchain-source fetch --depth=1 origin "$LANGCHAIN_SHA" \
 && git -C /opt/langchain-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/langchain-source rev-parse HEAD)" = "$LANGCHAIN_SHA" \
 && test "$(git -C /opt/langchain-source hash-object libs/langchain_v1/langchain/mcp/tools.py)" = ad0c6b0c65226f88432246bad0edcebc63496623
RUN python -m venv /opt/langchain-venv \
 && /opt/langchain-venv/bin/python -m pip install --no-cache-dir -e '/opt/langchain-source/libs/langchain_v1[mcp]' \
 && /opt/langchain-venv/bin/python -m pip check

RUN git init -q /opt/agents-source \
 && git -C /opt/agents-source remote add origin https://github.com/openai/openai-agents-python.git \
 && git -C /opt/agents-source fetch --depth=1 origin "$AGENTS_SHA" \
 && git -C /opt/agents-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/agents-source rev-parse HEAD)" = "$AGENTS_SHA" \
 && test "$(git -C /opt/agents-source hash-object src/agents/mcp/util.py)" = d51a773342c93239a1b79f1056ca889f37599d57
RUN python -m venv /opt/agents-venv \
 && /opt/agents-venv/bin/python -m pip install --no-cache-dir -e /opt/agents-source \
 && /opt/agents-venv/bin/python -m pip check

RUN git init -q /opt/pydantic-source \
 && git -C /opt/pydantic-source remote add origin https://github.com/pydantic/pydantic-ai.git \
 && git -C /opt/pydantic-source fetch --depth=1 origin "$PYDANTIC_SHA" \
 && git -C /opt/pydantic-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/pydantic-source rev-parse HEAD)" = "$PYDANTIC_SHA" \
 && test "$(git -C /opt/pydantic-source hash-object pydantic_ai_slim/pydantic_ai/mcp.py)" = e00e00cd395da3b23a7ffff07dc47317aba0f4f0
RUN python -m venv /opt/pydantic-venv \
 && /opt/pydantic-venv/bin/python -m pip install --no-cache-dir -e '/opt/pydantic-source/pydantic_ai_slim[mcp]' \
 && /opt/pydantic-venv/bin/python -m pip check

RUN chmod -R a+rX /opt/risu /opt/langchain-source /opt/agents-source /opt/pydantic-source \
   /opt/langchain-venv /opt/agents-venv /opt/pydantic-venv
ENV HOME=/tmp TMPDIR=/tmp XDG_CACHE_HOME=/tmp/cache
USER 65534:65534
ENTRYPOINT ["/bin/sh","-c"]
