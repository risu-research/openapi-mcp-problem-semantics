"""External Meilisearch SDK decoder with a clearly separate RISU contract check.

MeilisearchApiError is UNMODIFIED third-party source. The decision policy and
failure exception below are an explicit test-app requirement, not SDK behavior.
"""
from __future__ import annotations
import hashlib
import inspect
import json
from pathlib import Path
from requests import Response
from meilisearch.errors import MeilisearchApiError

EXPECTED_GIT_BLOB='9771fba0458973dc5cefe94ee3505e215caa6e66'

class SourceErrorContractFailure(Exception):
    pass

def hash_git_blob(path:Path):
    b=path.read_bytes()
    return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()

def verify_vendor_sdk_source():
    src=Path(inspect.getsourcefile(MeilisearchApiError) or '')
    if not src.is_file() or hash_git_blob(src)!=EXPECTED_GIT_BLOB:
        raise RuntimeError('Original official Meilisearch SDK source SHA mismatch')
    return {'path':str(src),'git_blob':EXPECTED_GIT_BLOB}

def external_sdk_then_contract(raw_body:str, origin:str):
    """Feed EXACT supplied body into unmodified original SDK parsing function."""
    response=Response()
    response.status_code=404
    response._content=raw_body.encode('utf-8')
    response.url='http://127.0.0.1/fixtures/index/does-not-exist'
    parsed=MeilisearchApiError('local replay error',response)
    decoded={'sdk_type':type(parsed).__name__,'status':parsed.status_code,
        'message':parsed.message,'code':parsed.code,'error_type':parsed.type,'link':parsed.link}
    if parsed.code!='index_not_found':
        raise SourceErrorContractFailure(f'{origin}: SOURCE_ERROR_CODE_UNAVAILABLE code={parsed.code!r}')
    if parsed.type!='invalid_request' or not isinstance(parsed.link,str) or not parsed.link:
        raise SourceErrorContractFailure(f'{origin}: SOURCE_ERROR_METADATA_UNAVAILABLE')
    return decoded

def extract_consumer_text(content):
    if isinstance(content,str):return content
    if isinstance(content,list) and len(content)==1 and isinstance(content[0],str):return content[0]
    if isinstance(content,list) and len(content)==1 and isinstance(content[0],dict) and content[0].get('type')=='text':
        return content[0]['text']
    raise SourceErrorContractFailure(f'Unexpected LangChain model content shape: {str(content)[:250]}')