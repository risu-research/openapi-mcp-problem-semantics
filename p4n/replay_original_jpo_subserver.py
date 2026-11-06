"""P4-N *replay* wrapper, NOT a third-party independent capture.

Runs the exact pinned third-party JPO FastMCP subserver over actual stdio MCP
transport, inside that project's own pytest VCR configuration and original
(redacted) on-disk cassette. All outgoing TCP is blocked independently of
VCR's record_mode="none", avoiding live API requests and credentials.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parent
REPO=Path(os.environ["P4N_EXTERNAL_PROJECT"]).resolve()
CASSETTE=Path(os.environ["P4N_ORIGINAL_CASSETTE_COPY"]).resolve()
assert CASSETTE.is_file() and CASSETTE.suffix==".yaml"
assert os.environ.get("JPO_API_USERNAME")=="REDACTED_USERNAME"
assert os.environ.get("JPO_API_PASSWORD")=="REDACTED_PASSWORD"
assert os.environ.get("P4N_REPLAY_ONLY")=="1"
assert sys.prefix != sys.base_prefix, "must run installed isolated venv"

# Load the original maintainer's VCR configuration verbatim, including
# oauth-safe-body matching and httpx2 response body workaround.
source=REPO/"tests"/"conftest.py"
spec=importlib.util.spec_from_file_location("_third_party_original_vcr_config",source)
assert spec and spec.loader
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
v=mod._create_vcr()
assert mod._record_mode=="none" and v.record_mode=="none"

from patent_client_agents.mcp.tools.jpo import jpo_mcp  # noqa: E402

# A second guard beyond VCR. No real JPO HTTP calls, even when a patched
# dependency accidentally avoids cassette playback. Do not block local
# UNIX socketpair used by MCP stdio.
_connect=socket.socket.connect
_connect_ex=socket.socket.connect_ex
_dns=socket.getaddrinfo
def allowed(address):
    if not isinstance(address,tuple):return True
    if not address:return False
    host=address[0]
    return host in ("127.0.0.1","::1","localhost")
def connect_guard(self,address):
    if not allowed(address):raise PermissionError("P4N_EXTERNAL_NETWORK_BLOCKED")
    return _connect(self,address)
def connect_ex_guard(self,address):
    if not allowed(address):raise PermissionError("P4N_EXTERNAL_NETWORK_BLOCKED")
    return _connect_ex(self,address)
def dns_guard(host,*args,**kw):
    if host not in ("127.0.0.1","::1","localhost",None):
        raise PermissionError("P4N_EXTERNAL_DNS_BLOCKED")
    return _dns(host,*args,**kw)
socket.socket.connect=connect_guard
socket.socket.connect_ex=connect_ex_guard
socket.getaddrinfo=dns_guard

with v.use_cassette(str(CASSETTE)) as tape:
    assert not tape.record_mode or tape.record_mode=="none"
    print("P4N_REPLAY_MODE_ONLY",file=sys.stderr,flush=True)
    jpo_mcp.run(transport="stdio")
    # If the stdio transport ever returns normally, we still demand that
    # actual prerecorded HTTP interactions were consumed.
    n=tape.play_count
    print("P4N_ORIGINAL_HTTP_CASSETTE_PLAY_COUNT",n,file=sys.stderr,flush=True)
    if n!=2:
        sys.exit("P4N_EXPECTED_TWO_ORIGINAL_RECORDED_HTTP_INTERACTIONS")
