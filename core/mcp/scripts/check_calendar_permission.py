#!/usr/bin/env python3
"""Check macOS calendar permission status for Python/EventKit."""

import json
import threading

try:
    import EventKit

    store = EventKit.EKEventStore.alloc().init()
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(
        EventKit.EKEntityTypeEvent
    )

    status_map = {
        0: "NotDetermined",
        1: "Restricted",
        2: "Denied",
        3: "Authorized",
        4: "WriteOnly",
        5: "FullAccess",
    }

    status_name = status_map.get(status, f"Unknown({status})")

    # If not determined, requesting access will trigger the dialog
    if status == 0:
        granted = [False]
        done_event = threading.Event()

        def callback(g, e):
            granted[0] = g
            done_event.set()

        if hasattr(store, 'requestFullAccessToEventsWithCompletion_'):
            store.requestFullAccessToEventsWithCompletion_(callback)
        else:
            store.requestAccessToEntityType_completion_(
                EventKit.EKEntityTypeEvent, callback
            )

        done_event.wait(timeout=30)
        if done_event.is_set():
            status_name = "Authorized" if granted[0] else "Denied"
        else:
            status_name = "Timeout"

    print(json.dumps({
        "status": status_name,
        "authorized": status_name in ("Authorized", "FullAccess"),
        "message": {
            "Authorized": "Calendar access granted. EventKit queries are active.",
            "FullAccess": "Full calendar access granted. EventKit queries are active.",
            "NotDetermined": "Permission dialog should have appeared. Run again to check.",
            "Denied": "Calendar access denied. Open System Settings > Privacy > Calendars to enable.",
            "Restricted": "Calendar access restricted by system policy.",
            "WriteOnly": "Only write access granted. Full access needed.",
            "Timeout": "No response from the calendar permission dialog within 30 seconds. Check if the prompt is hidden or blocked and try again.",
        }.get(status_name, "Unknown status"),
    }))

except ImportError:
    print(json.dumps({
        "status": "ModuleNotFound",
        "authorized": False,
        "message": "EventKit not available. Run: pip3 install pyobjc-framework-EventKit",
    }))
