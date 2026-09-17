"""Normalize optional holo-gestures input without retaining camera frames."""
from __future__ import annotations
from typing import Any, Mapping
from .core import CaptureEvent, TenantContext
SUPPORTED_GESTURES={"pinch","grab","release","swipe_left","swipe_right","open_palm"}
def normalize_holo_event(tenant:TenantContext,event:Mapping[str,Any])->CaptureEvent:
    name=str(event.get("gesture","")).strip().lower()
    if name not in SUPPORTED_GESTURES: raise ValueError("unsupported gesture")
    confidence=float(event.get("confidence",0))
    if not 0<=confidence<=1: raise ValueError("confidence must be between 0 and 1")
    return CaptureEvent(tenant=tenant,source="holo-gestures",media_type="gesture",payload={"gesture":name,"confidence":confidence,"target":str(event.get("target",""))[:120]})
