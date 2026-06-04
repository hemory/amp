#!/usr/bin/env python3
"""
EventKit-based calendar access for Amp.
Uses native macOS EventKit framework for fast calendar queries.

Usage:
    calendar_eventkit.py list
    calendar_eventkit.py events <calendar> <start_offset> <end_offset>
    calendar_eventkit.py next <calendar>
    calendar_eventkit.py search <calendar> <query> <days_back> <days_forward>
    calendar_eventkit.py attendees <calendar> <start_offset> <end_offset>

Offsets are integer days relative to today (0 = today, -1 = yesterday, 1 = tomorrow).
Output is JSON to stdout.
"""

import sys
import json
import threading
from datetime import datetime, timedelta

import EventKit
import objc
from Foundation import NSDate


def to_nsdate(dt):
    """Convert a Python datetime to an NSDate."""
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def get_event_store():
    """Create and authorize an EKEventStore."""
    store = EventKit.EKEventStore.alloc().init()

    # Check current authorization status synchronously first
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(
        EventKit.EKEntityTypeEvent
    )

    # status 3 = Authorized, 5 = FullAccess
    if status in (3, 5):
        return store

    # status 0 = NotDetermined — request access (triggers dialog on first run)
    if status == 0:
        granted = [False]
        error_ref = [None]
        done_event = threading.Event()

        def callback(g, e):
            granted[0] = g
            error_ref[0] = e
            done_event.set()

        if hasattr(store, 'requestFullAccessToEventsWithCompletion_'):
            store.requestFullAccessToEventsWithCompletion_(callback)
        else:
            store.requestAccessToEntityType_completion_(
                EventKit.EKEntityTypeEvent, callback
            )

        done_event.wait(timeout=30)

        # Distinguish a timeout from an explicit denial.
        if not done_event.is_set():
            print(
                json.dumps(
                    {
                        "error": "Timed out waiting for calendar access authorization.",
                    }
                ),
                file=sys.stderr,
            )
            sys.exit(1)

        if granted[0]:
            return store

        # Authorization callback completed but access was not granted.
        error_payload = {
            "error": "Calendar access not granted. Run /calendar-setup.",
        }
        if error_ref[0] is not None:
            error_payload["underlying_error"] = str(error_ref[0])

        print(json.dumps(error_payload), file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"error": "Calendar access not granted. Run /calendar-setup."}), file=sys.stderr)
    sys.exit(1)


def event_to_dict(event, include_attendees=False):
    """Convert an EKEvent to a JSON-serializable dict."""
    d = {
        "title": str(event.title() or ""),
        "start": str(event.startDate()),
        "end": str(event.endDate()),
        "all_day": bool(event.isAllDay()),
        "location": str(event.location() or ""),
        "notes": str(event.notes() or ""),
        "calendar": str(event.calendar().title()),
    }

    if event.URL():
        d["url"] = str(event.URL())

    if include_attendees and event.attendees():
        attendees = []
        for att in event.attendees():
            att_dict = {
                "name": str(att.name() or ""),
                "status": _participation_status(att.participantStatus()),
            }
            if att.URL():
                url_str = str(att.URL())
                if url_str.startswith("mailto:"):
                    att_dict["email"] = url_str[7:]
            attendees.append(att_dict)
        d["attendees"] = attendees

    return d


def _participation_status(status):
    mapping = {
        0: "unknown",
        1: "pending",
        2: "accepted",
        3: "declined",
        4: "tentative",
    }
    return mapping.get(status, "unknown")


def find_calendar(store, name):
    """Find a calendar by title (case-insensitive partial match)."""
    for cal in store.calendarsForEntityType_(EventKit.EKEntityTypeEvent):
        if cal.title().lower() == name.lower():
            return cal
    # Partial match fallback
    for cal in store.calendarsForEntityType_(EventKit.EKEntityTypeEvent):
        if name.lower() in cal.title().lower():
            return cal
    return None


def cmd_list(store):
    """List all calendars."""
    calendars = []
    for cal in store.calendarsForEntityType_(EventKit.EKEntityTypeEvent):
        calendars.append({
            "title": str(cal.title()),
            "type": str(cal.type()),
            "color": str(cal.color()) if cal.color() else None,
        })
    print(json.dumps(calendars))


def cmd_events(store, calendar_name, start_offset, end_offset, include_attendees=False):
    """Get events in a date range."""
    cal = find_calendar(store, calendar_name)
    if not cal:
        print(json.dumps([]))
        return

    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = now + timedelta(days=int(start_offset))
    end = now + timedelta(days=int(end_offset))

    ns_start = to_nsdate(start)
    ns_end = to_nsdate(end)

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        ns_start, ns_end, [cal]
    )
    events = store.eventsMatchingPredicate_(predicate)

    results = []
    if events:
        for ev in events:
            results.append(event_to_dict(ev, include_attendees))

    # Sort by start time
    results.sort(key=lambda e: e["start"])
    print(json.dumps(results))


def cmd_next(store, calendar_name):
    """Get the next upcoming event."""
    cal = find_calendar(store, calendar_name)
    if not cal:
        print(json.dumps({"message": "Calendar not found"}))
        return

    now = datetime.now()
    end = now + timedelta(days=7)

    ns_start = to_nsdate(now)
    ns_end = to_nsdate(end)

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        ns_start, ns_end, [cal]
    )
    events = store.eventsMatchingPredicate_(predicate)

    if not events:
        print(json.dumps({"message": "No upcoming events in the next 7 days"}))
        return

    # Sort and get the first future event
    sorted_events = sorted(events, key=lambda e: e.startDate().timeIntervalSince1970())
    for ev in sorted_events:
        ev_start = datetime.fromtimestamp(ev.startDate().timeIntervalSince1970())
        if ev_start >= now and not ev.isAllDay():
            print(json.dumps(event_to_dict(ev, include_attendees=True)))
            return

    print(json.dumps({"message": "No upcoming events found"}))


def cmd_search(store, calendar_name, query, days_back, days_forward):
    """Search events by title."""
    cal = find_calendar(store, calendar_name)
    calendars = [cal] if cal else None

    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = now - timedelta(days=int(days_back))
    end = now + timedelta(days=int(days_forward))

    ns_start = to_nsdate(start)
    ns_end = to_nsdate(end)

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        ns_start, ns_end, calendars
    )
    events = store.eventsMatchingPredicate_(predicate)

    results = []
    query_lower = query.lower()
    if events:
        for ev in events:
            title = str(ev.title() or "")
            if query_lower in title.lower():
                results.append(event_to_dict(ev))

    results.sort(key=lambda e: e["start"])
    print(json.dumps(results))


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <command> [args...]", file=sys.stderr)
        print("Commands: list, events, next, search, attendees", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    # Per-command argument validation
    arg_requirements = {
        "list": (2, "list"),
        "events": (5, "events <calendar> <start_offset> <end_offset>"),
        "next": (3, "next <calendar>"),
        "search": (6, "search <calendar> <query> <days_back> <days_forward>"),
        "attendees": (5, "attendees <calendar> <start_offset> <end_offset>"),
    }

    if command in arg_requirements:
        required, usage = arg_requirements[command]
        if len(sys.argv) < required:
            print(f"Usage: {sys.argv[0]} {usage}", file=sys.stderr)
            sys.exit(1)

    store = get_event_store()

    if command == "list":
        cmd_list(store)
    elif command == "events":
        cmd_events(store, sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == "next":
        cmd_next(store, sys.argv[2])
    elif command == "search":
        cmd_search(store, sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif command == "attendees":
        cmd_events(store, sys.argv[2], sys.argv[3], sys.argv[4], include_attendees=True)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
