#!/usr/bin/env python3
"""Jetty guide-mode overlay — draws a pulsing emerald ring + label on the REAL desktop.

Usage: python3 overlay.py <x_pct 0-100> <y_pct 0-100> [label]
The window is transparent, always-on-top, click-THROUGH (ignores mouse), and exits by
itself after ~8 seconds. Needs pyobjc (pip3 install --user pyobjc-framework-Cocoa).
"""
import math
import sys
import time

import objc
from AppKit import (NSApplication, NSApplicationActivationPolicyAccessory, NSBackingStoreBuffered,
                    NSBezierPath, NSColor, NSFont, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSMakeRect, NSScreen, NSView, NSWindow,
                    NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowStyleMaskBorderless)
from Foundation import NSObject, NSString, NSTimer

LIFETIME = 8.0          # seconds on screen
EMERALD = (0.20, 0.83, 0.60)


class RingView(NSView):
    # plain Python attributes, set after init (a custom ObjC init taking an NSRect would
    # need an explicit type signature — this avoids the problem entirely)
    center = (0.0, 0.0)
    label = ""
    t0 = 0.0

    def drawRect_(self, rect):
        elapsed = time.time() - self.t0
        pulse = 0.5 + 0.5 * math.sin(elapsed * 4.0)
        cx, cy = self.center
        r, g, b = EMERALD
        for radius, width, alpha in ((26 + 10 * pulse, 3.0, 0.9),
                                     (44 + 16 * pulse, 2.0, 0.5),
                                     (64 + 22 * pulse, 1.0, 0.25)):
            NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, alpha).setStroke()
            path = NSBezierPath.bezierPathWithOvalInRect_(
                NSMakeRect(cx - radius, cy - radius, radius * 2, radius * 2))
            path.setLineWidth_(width)
            path.stroke()
        NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 0.95).setFill()
        NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(cx - 5, cy - 5, 10, 10)).fill()
        if self.label:
            attrs = {
                NSFontAttributeName: NSFont.boldSystemFontOfSize_(15),
                NSForegroundColorAttributeName:
                    NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 0.95),
            }
            NSString.stringWithString_(self.label).drawAtPoint_withAttributes_(
                (cx + 78, cy - 8), attrs)


class Driver(NSObject):
    view = None
    app = None

    def tick_(self, timer):
        if time.time() - self.view.t0 > LIFETIME:
            self.app.terminate_(None)
        self.view.setNeedsDisplay_(True)


def main():
    x_pct = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0
    y_pct = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    label = sys.argv[3] if len(sys.argv) > 3 else ""

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    screen = NSScreen.mainScreen().frame()
    w, h = screen.size.width, screen.size.height
    # incoming y is % from the TOP of the screen; AppKit's origin is bottom-left
    cx, cy = w * x_pct / 100.0, h * (1.0 - y_pct / 100.0)

    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, w, h), NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setOpaque_(False)
    win.setLevel_(1000)                      # NSScreenSaverWindowLevel — above everything
    win.setIgnoresMouseEvents_(True)         # clicks pass straight through to the target
    win.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)

    view = RingView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    view.center = (cx, cy)
    view.label = label
    view.t0 = time.time()
    win.setContentView_(view)
    win.makeKeyAndOrderFront_(None)

    driver = Driver.alloc().init()
    driver.view, driver.app = view, app
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        1.0 / 30.0, driver, "tick:", None, True)
    app.run()


if __name__ == "__main__":
    main()
