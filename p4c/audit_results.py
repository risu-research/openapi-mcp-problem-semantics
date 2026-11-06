"""Independent classification of actual original-source MCP consumer results.

Never equate a documented error-content precedence policy with a novel bug.
The LangChain failure is pre-existing, publicly reported issue #40471.
"""
from pathlib import Path
import hashlib,json,sys

ROOT=Path(__file__).resolve().parent
PROTOCOL=json.loads((ROOT/'FROZEN_EXTERNAL_CONSUMER_PROTOCOL.json').read_text(encoding='utf-8'))

def audit(directory):
    paths={
        'langchain':'langchain.json',
        'openai':'openai.json',
        'pydanticai':'pydanticai.json',
    }
    reports={name:json.loads((directory/path).read_text(encoding='utf-8'))
             for name,path in paths.items()}
    for name,report in reports.items():
        assert report['status']=='PASS'
        expected={
            'langchain':'LangChain current MCP',
            'openai':'OpenAI Agents Python MCP',
            'pydanticai':'PydanticAI MCP',
        }[name]
        assert report['framework']==expected
        pin=next(p for p in PROTOCOL['products_under_test'] if p['name']==expected)
        assert report['pinned']==pin
        rows={x['id']:x for x in report['results']}
        assert set(rows)=={'E1','E2','S1','T1'}
    a={x['id']:x for x in reports['langchain']['results']}
    b={x['id']:x for x in reports['openai']['results']}
    c={x['id']:x for x in reports['pydanticai']['results']}
    # The same exact source payload is accessible on success but
    # omitted from LangChain's machine-readable artifact on errors.
    assert a['S1']['tool_message_artifact']['structured_content']['retry_after']==30
    assert a['E1']['tool_message_status']=='error'
    assert a['E1']['tool_message_artifact'] is None
    assert a['E2']['tool_message_artifact'] is None
    assert b['E1']['model_visible_tool_output']==[]
    assert b['E2']['model_visible_tool_output']=={'type':'text','text':'rate limited'}
    assert b['S1']['machine_error_field_visible'] is True
    assert c['E1']['machine_error_field_visible'] is True
    assert c['E2']['machine_error_field_visible'] is True
    assert c['T1']['machine_error_field_visible'] is False
    count=sum(
        not a[label]['machine_error_field_visible'] and
        c[label]['machine_error_field_visible']
        for label in ('E1','E2')
    )
    assert count==2
    report={
        'schema':'risu-p4c-audited-external-consumers-v1',
        'status':'PASS',
        'exact_pinned_source_projects':3,
        'authentic_original_consumer_paths_executed':3,
        'frozen_scenarios_per_consumer':4,
        'cross_framework_observed_error_structured_content_inequivalence':2,
        'langchain_known_issue':'https://github.com/langchain-ai/langchain/issues/40471',
        'langchain_issue_was_preexisting':True,
        'openai_agents_error_precedence_documented':True,
        'pydanticai_preserves_structured_error':True,
        'new_undocumented_upstream_bugs_claimed':0,
        'new_external_user_production_incidents_measured':0,
        'external_api_or_llm_calls':0,
        'vendor_code_modified':False,
        'method':'Real pinned source code and dependency isolation; injected synthetic result via local fake transport; no actual vendor service or MCP server',
        'claim_boundary':'A real consumer-code compatibility behavior is reproduced, but the LangChain branch was already publicly reported, OpenAI policy is documented, and PydanticAI is a negative control. Novel upstream defect not yet established.',
        'evidence_sha256':{
            key:hashlib.sha256((directory/path).read_bytes()).hexdigest()
            for key,path in paths.items()},
        'protocol_sha256':hashlib.sha256(
            (ROOT/'FROZEN_EXTERNAL_CONSUMER_PROTOCOL.json').read_bytes()).hexdigest(),
    }
    (directory/'INDEPENDENT_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    print('RISU_P4C_INDEPENDENT_AUDIT_PASS',json.dumps({
        k:report[k] for k in ('exact_pinned_source_projects',
                             'cross_framework_observed_error_structured_content_inequivalence',
                             'new_undocumented_upstream_bugs_claimed')}),
          flush=True)

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: audit_results.py DIRECTORY')
    audit(Path(sys.argv[1]))
