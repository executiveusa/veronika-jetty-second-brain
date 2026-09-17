import os
from types import SimpleNamespace
from fastapi import HTTPException
from backend.auth import authenticate_request
class Headers(dict): pass
class Request:
    def __init__(self,path,authorization=""):
        self.url=SimpleNamespace(path=path);self.headers=Headers(authorization=authorization)
def test_health_is_public(): assert authenticate_request(Request('/api/health')) is None
def test_private_api_requires_bearer():
    os.environ['JETTY_REQUIRE_AUTH']='true'
    try: authenticate_request(Request('/api/notes'))
    except HTTPException as e: assert e.status_code==401
    else: raise AssertionError('private route allowed')
def test_missing_server_secret_fails_closed():
    os.environ['JETTY_REQUIRE_AUTH']='true';os.environ.pop('SUPABASE_JWT_SECRET',None)
    try: authenticate_request(Request('/api/notes','Bearer token'))
    except HTTPException as e: assert e.status_code==503
    else: raise AssertionError('missing auth config allowed')
