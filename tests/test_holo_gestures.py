from backend.capabilities import TenantContext
from backend.capabilities.holo_gestures import normalize_holo_event
def test_normalizes_supported_event_without_frame_data():
 e=normalize_holo_event(TenantContext('biz','user'),{'gesture':'Pinch','confidence':.9,'target':'note-1','frame':'discard'})
 assert e.payload=={'gesture':'pinch','confidence':.9,'target':'note-1'}
def test_rejects_unknown_event():
 try: normalize_holo_event(TenantContext('biz','user'),{'gesture':'launch_missile','confidence':1})
 except ValueError:pass
 else:raise AssertionError('unknown gesture accepted')
def test_rejects_invalid_confidence():
 try: normalize_holo_event(TenantContext('biz','user'),{'gesture':'pinch','confidence':2})
 except ValueError:pass
 else:raise AssertionError('invalid confidence accepted')
