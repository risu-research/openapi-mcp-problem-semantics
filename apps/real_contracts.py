"""Real pinned external SDK consumer behavior; no API calls, no mocked SDK logic.

Running this module requires pip-installing exact original application sources:
PyGithub@5aeb43916b197a0fe8016600817b868fc894af5a
stripe-python@d97a68e28ec6553c3545fdf7e5322e871559cfdb.
"""
import json

CONTRACTS={
 'pygithub-404':{
  'repo':'PyGithub/PyGithub','commit':'5aeb43916b197a0fe8016600817b868fc894af5a',
  'file':'github/Requester.py','blob':'397a58f5d44f62a49fb44cdae9273721a3f69354',
  'status':404,'operation':'get_github_issue','path':'/risu/github/issue',
  'expected':'UnknownObjectException',
  'body':{'message':'Not Found','documentation_url':'https://docs.github.com/rest',
          'unused':'synthetic-data','debug':{'trace':'local-only','timing':7}},
  'required_path':'/message',
  'source_contract':'Requester.createException: 404 + message containing not found -> UnknownObjectException',
 },
 'stripe-rate-limit-400':{
  'repo':'stripe/stripe-python','commit':'d97a68e28ec6553c3545fdf7e5322e871559cfdb',
  'file':'stripe/_api_requestor.py','blob':'6224c5e6d357043ff7a404cebefbbdef09ec9b7f',
  'status':400,'operation':'get_stripe_error','path':'/risu/stripe/error',
  'expected':'RateLimitError',
  'body':{'error':{'code':'rate_limit','type':'invalid_request_error',
                   'message':'Synthetic API rate limit','param':'synthetic',
                   'extra':{'trace':'not needed'}},
          'details':{'debug':'not needed','unused':123}},
  'required_path':'/error/code',
  'source_contract':'APIRequestor.specific_v1_api_error: 400 + error.code==rate_limit -> RateLimitError',
 },
}

def classify_real_sdk(contract:str, body:dict, status:int) ->str:
    if not isinstance(body,dict):
        return 'INVALID_BODY_TYPE'
    if contract=='pygithub-404':
        from github.Requester import Requester
        return type(Requester.createException(status,{},body)).__name__
    if contract=='stripe-rate-limit-400':
        from stripe._api_requestor import APIRequestor
        from stripe import error
        # This directly invokes the official unmodified Stripe v1 parser.
        if not isinstance(body.get('error'),dict):
            return 'APIError_MISSING_ERROR_OBJECT'
        value=APIRequestor.specific_v1_api_error(
             None,json.dumps(body,sort_keys=True),status,body,{},body['error'])
        return type(value).__name__
    raise ValueError('UNKNOWN_PINNED_SDK_CONTRACT')

def contract_source(c):
    return {'status':c['status'],'content_type':'application/json','body':c['body']}
