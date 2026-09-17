# Jetty capability integration boundary

Jetty keeps its current screens and routes. New input devices connect through a small boundary rather than bringing another product's UI into Jetty.

1. A browser, phone, camera, glasses, or future gesture adapter emits a `CaptureEvent`.
2. Every event carries `TenantContext`; missing business or user identity is rejected.
3. An intent router maps the event to read, draft, reversible write, external send, or money.
4. External sends and money are never automatic. They require a separate approved execution path.
5. Every effect returns an `ActionReceipt` with an undo or recovery statement.
6. The UI displays only capabilities whose current health check passes.

No code was copied from VisionClaw or holo-gestures. Holo-gestures remains architecture-only until a usable license is confirmed.
