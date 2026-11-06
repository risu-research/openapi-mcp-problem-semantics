"""Unpack the exact locally tested P4-Q identity module and verify its SHA."""
from pathlib import Path
import base64
import hashlib
import zlib
ROOT=Path(__file__).resolve().parent
sources={
 "risu_arraymatch.py":("overrides/risu_arraymatch.py",
    "759e12f869c6add6ba947f60650845431fcbbc003885438c484da0bfeb2937b1",19493)
}
for src,(dest,sha,size) in sources.items():
    encoded=(ROOT/"packed"/(src+".zlib.b64")).read_text().strip()
    body=zlib.decompress(base64.b64decode(encoded,validate=True))
    assert len(body)==size and hashlib.sha256(body).hexdigest()==sha,("P4Q_SOURCE_SHA_MISMATCH",src)
    path=ROOT/dest
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(body)
    print("P4Q_EXACT_SOURCE_READY",src,sha,flush=True)
