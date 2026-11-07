FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/risu
COPY p4d/ /opt/risu/p4d/
COPY p5b/ /opt/risu/p5b/
RUN git init -q /opt/meili-source \
 && git -C /opt/meili-source remote add origin https://github.com/meilisearch/open-api.git \
 && git -C /opt/meili-source fetch --depth=1 origin 0b0b0fdbb9d5821ec018a3db2777986a231eec37 \
 && git -C /opt/meili-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/meili-source rev-parse HEAD)" = 0b0b0fdbb9d5821ec018a3db2777986a231eec37 \
 && test "$(git -C /opt/meili-source hash-object open-api.json)" = 8e01bc5c07f4f17cc2f183ecfb427e2592ba333b
RUN git init -q /opt/cnoe-source \
 && git -C /opt/cnoe-source remote add origin https://github.com/cnoe-io/openapi-mcp-codegen.git \
 && git -C /opt/cnoe-source fetch --depth=1 origin 8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f \
 && git -C /opt/cnoe-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/cnoe-source rev-parse HEAD)" = 8c2b065497cf32ecbb7cf7e28dad3a99c6706c3f \
 && python -m venv /opt/cnoe \
 && /opt/cnoe/bin/python -m pip install --no-cache-dir -e /opt/cnoe-source \
 && /opt/cnoe/bin/python -m pip check
RUN git init -q /opt/langchain-source \
 && git -C /opt/langchain-source remote add origin https://github.com/langchain-ai/langchain.git \
 && git -C /opt/langchain-source fetch --depth=1 origin bb6a25a878527136dcb1a20507d5c20049427f96 \
 && git -C /opt/langchain-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/langchain-source rev-parse HEAD)" = bb6a25a878527136dcb1a20507d5c20049427f96 \
 && test "$(git -C /opt/langchain-source hash-object libs/langchain_v1/langchain/mcp/tools.py)" = ad0c6b0c65226f88432246bad0edcebc63496623 \
 && python -m venv /opt/langchain-venv \
 && /opt/langchain-venv/bin/python -m pip install --no-cache-dir -e '/opt/langchain-source/libs/langchain_v1[mcp]'
RUN git init -q /opt/meilisearch-python-source \
 && git -C /opt/meilisearch-python-source remote add origin https://github.com/meilisearch/meilisearch-python.git \
 && git -C /opt/meilisearch-python-source fetch --depth=1 origin 6a6cc2596779a06f121ebb6d88dfa6943ee18d91 \
 && git -C /opt/meilisearch-python-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/meilisearch-python-source rev-parse HEAD)" = 6a6cc2596779a06f121ebb6d88dfa6943ee18d91 \
 && test "$(git -C /opt/meilisearch-python-source hash-object meilisearch/errors.py)" = 9771fba0458973dc5cefe94ee3505e215caa6e66 \
 && /opt/langchain-venv/bin/python -m pip install --no-cache-dir -e /opt/meilisearch-python-source \
 && /opt/langchain-venv/bin/python -m pip check
RUN chmod -R a+rX /opt/risu /opt/meili-source /opt/cnoe-source /opt/langchain-source /opt/meilisearch-python-source /opt/cnoe /opt/langchain-venv
ENV HOME=/tmp TMPDIR=/tmp XDG_CACHE_HOME=/tmp/cache
USER 65534:65534
CMD ["/opt/langchain-venv/bin/python","-B","/opt/risu/p5b/run_full_chain.py","--out","/results"]