"""Device-neutral capability contracts.

This module has no device or provider dependency. Browser, phone, glasses, and
future gesture adapters can emit CaptureEvent objects without changing Jetty's
memory or action layers.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

class RiskTier(str, Enum):
    READ = "read"
    DRAFT = "draft"
    REVERSIBLE_WRITE = "reversible_write"
    EXTERNAL_SEND = "external_send"
    MONEY = "money"

@dataclass(frozen=True)
class TenantContext:
    business_id: str
    user_id: str
    roles: tuple[str, ...] = ()
    def __post_init__(self) -> None:
        if not self.business_id.strip() or not self.user_id.strip():
            raise ValueError("business_id and user_id are required")

@dataclass(frozen=True)
class CaptureEvent:
    tenant: TenantContext
    source: str
    media_type: str
    payload: Mapping[str, Any]
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid4()))

@dataclass(frozen=True)
class Intent:
    name: str
    risk: RiskTier
    arguments: Mapping[str, Any]
    source_event_id: str

@dataclass(frozen=True)
class ActionReceipt:
    tenant: TenantContext
    intent: Intent
    status: str
    result: Mapping[str, Any]
    undo: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    receipt_id: str = field(default_factory=lambda: str(uuid4()))
    def __post_init__(self) -> None:
        if self.intent.risk in {RiskTier.REVERSIBLE_WRITE, RiskTier.EXTERNAL_SEND, RiskTier.MONEY} and not self.undo:
            raise ValueError("effectful actions require an undo or recovery statement")

@dataclass(frozen=True)
class Capability:
    name: str
    healthy: bool
    detail: str = ""

class CapabilityRegistry:
    """Expose only capabilities that passed their current health check."""
    def __init__(self) -> None:
        self._items: dict[str, Capability] = {}
    def record(self, capability: Capability) -> None:
        self._items[capability.name] = capability
    def available(self) -> tuple[Capability, ...]:
        return tuple(sorted((c for c in self._items.values() if c.healthy), key=lambda c: c.name))
    def status(self) -> tuple[Capability, ...]:
        return tuple(sorted(self._items.values(), key=lambda c: c.name))
