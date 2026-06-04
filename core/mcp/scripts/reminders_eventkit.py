#!/usr/bin/env python3
"""
EventKit-based Reminders access for Amp.
Uses native macOS EventKit framework for fast Reminders queries.

Usage:
    reminders_eventkit.py list_items <list_name>
    reminders_eventkit.py complete <reminder_id>
    reminders_eventkit.py create <list_name> <title> [notes] [due_date]
    reminders_eventkit.py ensure_lists
    reminders_eventkit.py list_completed <list_name>
    reminders_eventkit.py find_and_complete <list_name> <title_query>
    reminders_eventkit.py clear_completed <list_name>

Output is JSON to stdout.
"""

import sys
import json
import logging
import threading
from datetime import datetime, timedelta

import EventKit

try:
    from Foundation import NSDate as FoundationNSDate
except ImportError:
    FoundationNSDate = None

try:
    from core.utils import mcp_error
except ImportError:
    def mcp_error(message, code="error"):
        return {"error": message, "code": code}


def _datetime_to_nsdate(dt):
    """Convert a Python datetime to an NSDate using the public Foundation API."""
    if FoundationNSDate is not None:
        return FoundationNSDate.dateWithTimeIntervalSince1970_(dt.timestamp())
    # Fallback: NSDate is re-exported through EventKit's ObjC bridge
    return EventKit.NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def get_reminder_store():
    """Create and authorize an EKEventStore for reminders."""
    store = EventKit.EKEventStore.alloc().init()

    # Check current authorization status synchronously first
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(
        EventKit.EKEntityTypeReminder
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

        if hasattr(store, 'requestFullAccessToRemindersWithCompletion_'):
            store.requestFullAccessToRemindersWithCompletion_(callback)
        else:
            store.requestAccessToEntityType_completion_(
                EventKit.EKEntityTypeReminder, callback
            )

        # Wait for the authorization callback, but distinguish timeout vs explicit denial.
        if not done_event.wait(timeout=30):
            print(json.dumps(
                {"error": "Timed out waiting for Reminders access authorization"}
            ), file=sys.stderr)
            sys.exit(1)

        if granted[0]:
            return store

        # Access was not granted; include any underlying EventKit error if available.
        error_msg = "Reminders access not granted"
        if error_ref[0] is not None:
            error_msg = f"{error_msg}: {error_ref[0]}"
        print(json.dumps({"error": error_msg}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"error": "Reminders access not granted"}), file=sys.stderr)
    sys.exit(1)


def find_reminder_list(store, name):
    """Find a reminder list by title."""
    for cal in store.calendarsForEntityType_(EventKit.EKEntityTypeReminder):
        if cal.title().lower() == name.lower():
            return cal
    return None


def reminder_to_dict(reminder):
    """Convert an EKReminder to a JSON-serializable dict."""
    d = {
        "id": str(reminder.calendarItemIdentifier()),
        "title": str(reminder.title() or ""),
        "completed": bool(reminder.isCompleted()),
        "notes": str(reminder.notes() or ""),
    }
    if reminder.dueDateComponents():
        dc = reminder.dueDateComponents()
        d["due_date"] = f"{dc.year():04d}-{dc.month():02d}-{dc.day():02d}"
    if reminder.completionDate():
        d["completed_date"] = str(reminder.completionDate())
    return d


def cmd_list_items(store, list_name):
    """Get incomplete items from a list."""
    cal = find_reminder_list(store, list_name)
    if not cal:
        print(json.dumps({"items": [], "message": f"List '{list_name}' not found"}))
        return

    predicate = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        None, None, [cal]
    )

    # Fetch synchronously
    result_holder = [None]
    event = threading.Event()

    def fetch_callback(reminders):
        result_holder[0] = reminders
        event.set()

    store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_callback)
    if not event.wait(timeout=10):
        logging.warning("list_items: fetch timed out after 10 seconds")
        print(json.dumps({"items": [], "count": 0, "error": "Operation timed out"}))
        return

    items = []
    if result_holder[0]:
        for r in result_holder[0]:
            items.append(reminder_to_dict(r))

    print(json.dumps({"items": items, "count": len(items)}))


def cmd_complete(store, reminder_id):
    """Mark a reminder as complete by its calendarItemIdentifier."""
    item = store.calendarItemWithIdentifier_(reminder_id)
    if not item:
        print(json.dumps(mcp_error("Reminder not found")))
        return

    item.setCompleted_(True)
    item.setCompletionDate_(EventKit.NSDate.date())
    success, error = store.saveReminder_commit_error_(item, True, None)

    if success:
        print(json.dumps({"success": True, "message": f"Completed: {item.title()}"}))
    else:
        print(json.dumps(mcp_error(str(error))))


def cmd_create(store, list_name, title, notes="", due_date=""):
    """Create a new reminder."""
    cal = find_reminder_list(store, list_name)
    if not cal:
        print(json.dumps(mcp_error(f"List '{list_name}' not found")))
        return

    reminder = EventKit.EKReminder.reminderWithEventStore_(store)
    reminder.setTitle_(title)
    reminder.setCalendar_(cal)

    if notes:
        reminder.setNotes_(notes)

    if due_date:
        try:
            dt = datetime.strptime(due_date, "%Y-%m-%d")
            components = EventKit.NSDateComponents.alloc().init()
            components.setYear_(dt.year)
            components.setMonth_(dt.month)
            components.setDay_(dt.day)
            reminder.setDueDateComponents_(components)
        except ValueError:
            pass

    success, error = store.saveReminder_commit_error_(reminder, True, None)

    if success:
        print(json.dumps({
            "success": True,
            "reminder": reminder_to_dict(reminder)
        }))
    else:
        print(json.dumps(mcp_error(str(error))))


def cmd_ensure_lists(store):
    """Create Amp Inbox and Amp Today lists if they don't exist."""
    created = []
    for name in ["Amp Inbox", "Amp Today"]:
        if not find_reminder_list(store, name):
            source = store.defaultCalendarForNewReminders().source()
            cal = EventKit.EKCalendar.calendarForEntityType_eventStore_(
                EventKit.EKEntityTypeReminder, store
            )
            cal.setTitle_(name)
            cal.setSource_(source)
            success, error = store.saveCalendar_commit_error_(cal, True, None)
            if success:
                created.append(name)

    print(json.dumps({
        "success": True,
        "created": created,
        "message": f"Created {len(created)} lists" if created else "All lists exist"
    }))


def cmd_list_completed(store, list_name):
    """Get recently completed items (last 2 days)."""
    cal = find_reminder_list(store, list_name)
    if not cal:
        print(json.dumps({"items": [], "message": f"List '{list_name}' not found"}))
        return

    two_days_ago = datetime.now() - timedelta(days=2)
    ns_start = _datetime_to_nsdate(two_days_ago)

    predicate = store.predicateForCompletedRemindersWithCompletionDateStarting_ending_calendars_(
        ns_start, None, [cal]
    )

    result_holder = [None]
    event = threading.Event()

    def fetch_callback(reminders):
        result_holder[0] = reminders
        event.set()

    store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_callback)
    if not event.wait(timeout=10):
        logging.warning("list_completed: fetch timed out after 10 seconds")
        print(json.dumps({"items": [], "count": 0, "error": "Operation timed out"}))
        return

    items = []
    if result_holder[0]:
        for r in result_holder[0]:
            items.append(reminder_to_dict(r))

    print(json.dumps({"items": items, "count": len(items)}))


def cmd_find_and_complete(store, list_name, title_query):
    """Find a reminder by fuzzy title match and complete it."""
    cal = find_reminder_list(store, list_name)
    if not cal:
        print(json.dumps(mcp_error(f"List '{list_name}' not found")))
        return

    predicate = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        None, None, [cal]
    )

    result_holder = [None]
    event = threading.Event()

    def fetch_callback(reminders):
        result_holder[0] = reminders
        event.set()

    store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_callback)
    if not event.wait(timeout=10):
        logging.warning("find_and_complete: fetch timed out after 10 seconds")
        print(json.dumps(mcp_error("Operation timed out")))
        return

    query_lower = title_query.lower()
    matched = None
    if result_holder[0]:
        for r in result_holder[0]:
            if query_lower in str(r.title() or "").lower():
                matched = r
                break

    if matched:
        matched.setCompleted_(True)
        matched.setCompletionDate_(EventKit.NSDate.date())
        success, error = store.saveReminder_commit_error_(matched, True, None)
        if success:
            print(json.dumps({"success": True, "title": str(matched.title()), "message": "Completed"}))
        else:
            print(json.dumps(mcp_error(str(error))))
    else:
        print(json.dumps(mcp_error(f"No reminder matching '{title_query}'")))


def cmd_clear_completed(store, list_name):
    """Remove all completed reminders from a list."""
    cal = find_reminder_list(store, list_name)
    if not cal:
        print(json.dumps(mcp_error(f"List '{list_name}' not found")))
        return

    two_weeks_ago = datetime.now() - timedelta(days=14)
    ns_start = _datetime_to_nsdate(two_weeks_ago)

    predicate = store.predicateForCompletedRemindersWithCompletionDateStarting_ending_calendars_(
        ns_start, None, [cal]
    )

    result_holder = [None]
    event = threading.Event()

    def fetch_callback(reminders):
        result_holder[0] = reminders
        event.set()

    store.fetchRemindersMatchingPredicate_completion_(predicate, fetch_callback)
    if not event.wait(timeout=10):
        logging.warning("clear_completed: fetch timed out after 10 seconds")
        print(json.dumps(mcp_error("Operation timed out")))
        return

    removed = 0
    if result_holder[0]:
        for r in result_holder[0]:
            success, error = store.removeReminder_commit_error_(r, True, None)
            if success:
                removed += 1

    print(json.dumps({"success": True, "removed": removed}))


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <command> [args...]", file=sys.stderr)
        print("Commands: list_items, complete, create, ensure_lists, list_completed, find_and_complete, clear_completed", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    # Per-command argument validation
    arg_requirements = {
        "list_items": (3, "list_items <list_name>"),
        "complete": (3, "complete <reminder_id>"),
        "create": (4, "create <list_name> <title> [notes] [due_date]"),
        "ensure_lists": (2, "ensure_lists"),
        "list_completed": (3, "list_completed <list_name>"),
        "find_and_complete": (4, "find_and_complete <list_name> <title_query>"),
        "clear_completed": (3, "clear_completed <list_name>"),
    }

    if command in arg_requirements:
        required, usage = arg_requirements[command]
        if len(sys.argv) < required:
            print(f"Usage: {sys.argv[0]} {usage}", file=sys.stderr)
            sys.exit(1)

    store = get_reminder_store()

    if command == "list_items":
        cmd_list_items(store, sys.argv[2])
    elif command == "complete":
        cmd_complete(store, sys.argv[2])
    elif command == "create":
        cmd_create(store, sys.argv[2], sys.argv[3],
                   sys.argv[4] if len(sys.argv) > 4 else "",
                   sys.argv[5] if len(sys.argv) > 5 else "")
    elif command == "ensure_lists":
        cmd_ensure_lists(store)
    elif command == "list_completed":
        cmd_list_completed(store, sys.argv[2])
    elif command == "find_and_complete":
        cmd_find_and_complete(store, sys.argv[2], sys.argv[3])
    elif command == "clear_completed":
        cmd_clear_completed(store, sys.argv[2])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
