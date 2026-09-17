"""Fail-closed authentication boundary for private Jetty API routes."""
from __future__ import annotations
import os
from typing import Any
import jwt
from fastapi import HTTPException, Request

PUBLIC_API_PATHS = {"/api/health", "/api/directory/categories", "/api/directory/locations", "/api/directory/businesses"}

def auth_required() -> bool:
    return os.getenv("JETTY_REQUIRE_AUTH", "true").strip().lower() not in {"0", "false", "no"}

def decode_access_token(token: str) -> dict[str, Any]:
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Access token has no subject")
    return payload

def authenticate_request(request: Request) -> dict[str, Any] | None:
    if not auth_required() or request.url.path in PUBLIC_API_PATHS or not request.url.path.startswith("/api/"):
        return None
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Bearer access token required")
    return decode_access_token(token.strip())
