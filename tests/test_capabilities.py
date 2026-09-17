from backend.capabilities import ActionReceipt, CaptureEvent, Capability, CapabilityRegistry, Intent, RiskTier, TenantContext

def test_tenant_is_mandatory():
    try: TenantContext("", "user")
    except ValueError: pass
    else: raise AssertionError("empty tenant accepted")

def test_device_neutral_capture_and_registry():
    tenant=TenantContext("biz-1","user-1")
    event=CaptureEvent(tenant,"browser","text",{"text":"call Sam"})
    assert event.source == "browser"
    registry=CapabilityRegistry(); registry.record(Capability("browser",True)); registry.record(Capability("gesture",False,"no adapter"))
    assert [x.name for x in registry.available()] == ["browser"]

def test_effectful_receipt_needs_recovery():
    tenant=TenantContext("biz-1","user-1")
    intent=Intent("send_follow_up",RiskTier.EXTERNAL_SEND,{},"event-1")
    try: ActionReceipt(tenant,intent,"blocked",{},None)
    except ValueError: pass
    else: raise AssertionError("effectful receipt accepted without recovery")
