FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG MCPGEN_SHA=30ee7cb9c2e923ce901e788b0d911f6547772866
ARG PYGITHUB_SHA=5aeb43916b197a0fe8016600817b868fc894af5a
ARG STRIPE_SHA=d97a68e28ec6553c3545fdf7e5322e871559cfdb
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/risu
COPY dist/risu_v09_source/ /opt/risu/product/
COPY apps/ /opt/risu/apps/

# MCP generator, pinned upstream source, independently installed.
RUN python -m venv /opt/mcpgen \
 && git init -q /opt/mcpgen-source \
 && git -C /opt/mcpgen-source remote add origin https://github.com/breezykalama/mcpgen.git \
 && git -C /opt/mcpgen-source fetch --depth=1 origin "$MCPGEN_SHA" \
 && git -C /opt/mcpgen-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/mcpgen-source rev-parse HEAD)" = "$MCPGEN_SHA" \
 && /opt/mcpgen/bin/python -m pip install --no-cache-dir -e /opt/mcpgen-source \
 && /opt/mcpgen/bin/python -m pip check

# Actual external application SDKs, not copied/reimplemented consumer logic.
RUN python -m venv /opt/sdk \
 && git init -q /opt/pygithub-source \
 && git -C /opt/pygithub-source remote add origin https://github.com/PyGithub/PyGithub.git \
 && git -C /opt/pygithub-source fetch --depth=1 origin "$PYGITHUB_SHA" \
 && git -C /opt/pygithub-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/pygithub-source rev-parse HEAD)" = "$PYGITHUB_SHA" \
 && test "$(git -C /opt/pygithub-source hash-object github/Requester.py)" = 397a58f5d44f62a49fb44cdae9273721a3f69354 \
 && /opt/sdk/bin/python -m pip install --no-cache-dir -e /opt/pygithub-source
RUN git init -q /opt/stripe-source \
 && git -C /opt/stripe-source remote add origin https://github.com/stripe/stripe-python.git \
 && git -C /opt/stripe-source fetch --depth=1 origin "$STRIPE_SHA" \
 && git -C /opt/stripe-source checkout --detach FETCH_HEAD \
 && test "$(git -C /opt/stripe-source rev-parse HEAD)" = "$STRIPE_SHA" \
 && test "$(git -C /opt/stripe-source hash-object stripe/_api_requestor.py)" = 6224c5e6d357043ff7a404cebefbbdef09ec9b7f \
 && /opt/sdk/bin/python -m pip install --no-cache-dir -e /opt/stripe-source \
 && /opt/sdk/bin/python -m pip check
RUN chmod -R a+rX /opt/risu /opt/mcpgen /opt/sdk /opt/pygithub-source /opt/stripe-source
ENV HOME=/tmp TMPDIR=/tmp XDG_CACHE_HOME=/tmp/cache PATH="/opt/sdk/bin:/usr/local/bin:/usr/bin:/bin"
USER 65534:65534
ENTRYPOINT ["/opt/sdk/bin/python","-B","/opt/risu/apps/run_live.py"]
