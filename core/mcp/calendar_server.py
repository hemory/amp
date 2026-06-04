#!/usr/bin/env python3
"""
Apple Calendar MCP Server for Amp

Provides read/write access to Apple Calendar via AppleScript.
Works with any calendar synced to Calendar.app, including Google accounts.

Tools:
- calendar_list_calendars: List all available calendars
- calendar_get_events: Get events for a date range
- calendar_get_today: Quick access to today's meetings
- calendar_create_event: Create a new event
- calendar_search_events: Search events by title
- calendar_delete_event: Delete an event
- calendar_get_next_event: Get the next upcoming event
- calendar_get_events_with_attendees: Get events with full attendee details
- reminders_list_items: Get incomplete items from a Reminders list
- reminders_complete_item: Mark a Reminder as complete
- reminders_create_item: Create a new Reminder
- reminders_ensure_lists: Create Amp Inbox/Today lists if missing
- reminders_list_completed: Get recently completed Reminders for sync
- reminders_find_and_complete: Find and complete a Reminder by title match
- reminders_clear_completed: Remove completed Reminders from a list
"""

import os
import sys
import subprocess
import json
import logging
import tempfile
import re
import yaml
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from core.utils import mcp_error

# Vault paths
VAULT_PATH = Path(os.environ.get('VAULT_PATH', Path.cwd()))
PEOPLE_DIR = VAULT_PATH / "05-Areas" / "People"

# Health system — error queue and health reporting
try:
    from core.utils.amp_logger import log_error as _log_health_error, mark_healthy as _mark_healthy
    _HAS_HEALTH = True
except ImportError:
    _HAS_HEALTH = False

# Timezone-aware date/time (respects user-profile.yaml timezone)
try:
    import sys as _sys2
    _sys2.path.insert(0, str(Path(__file__).parent.parent.parent))
    from core.utils.timezone import now as _tz_now, today as _tz_today, convert_utc_to_user as _convert_utc
except ImportError:
    def _tz_now():
        return datetime.now()
    def _tz_today():
        return datetime.now().date()
    def _convert_utc(dt_str):
        return dt_str.replace(' +0000', '')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Scripts directory
SCRIPTS_DIR = Path(__file__).parent / "scripts"

# User profile path
USER_PROFILE_PATH = VAULT_PATH / "System" / "user-profile.yaml"


def get_default_work_calendar() -> str:
    """Get the configured work calendar from user-profile.yaml.
    
    Returns the work_calendar if configured, otherwise tries work_email,
    otherwise falls back to 'Work'.
    
    This dramatically improves performance (45s → 0.3s) by querying
    only the relevant calendar instead of all calendars.
    """
    try:
        import yaml
        if USER_PROFILE_PATH.exists():
            with open(USER_PROFILE_PATH, 'r') as f:
                profile = yaml.safe_load(f)
            
            # Try calendar.work_calendar first
            if profile.get('calendar', {}).get('work_calendar'):
                return profile['calendar']['work_calendar']
            
            # Fall back to work_email
            if profile.get('work_email'):
                return profile['work_email']
            
            # Try constructing from email_domain
            if profile.get('name') and profile.get('email_domain'):
                name = profile['name'].lower().replace(' ', '.')
                domain = profile['email_domain']
                return f"{name}@{domain}"
    except Exception as e:
        logger.warning(f"Could not read work calendar from profile: {e}")
    
    return "Work"  # Fallback default


# Cache the default calendar (read once at startup)
DEFAULT_WORK_CALENDAR = get_default_work_calendar()
logger.info(f"Default work calendar: {DEFAULT_WORK_CALENDAR}")


# Custom JSON encoder for handling date/datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def run_applescript(script: str) -> tuple[bool, str]:
    """Run an AppleScript and return (success, output).
    
    Uses subprocess.run with temp file output to avoid pipe issues
    with Calendar.app AppleScript queries.
    """
    try:
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.scpt', delete=False) as script_file:
            script_file.write(script)
            script_path = script_file.name
        
        # Output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as out_file:
            out_path = out_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as err_file:
            err_path = err_file.name
        
        try:
            # Run osascript via subprocess.run (shell=False for safety)
            with open(out_path, 'w') as out_f, open(err_path, 'w') as err_f:
                result = subprocess.run(
                    ["osascript", script_path],
                    stdout=out_f,
                    stderr=err_f,
                    timeout=30
                )
                exit_code = result.returncode
            
            with open(out_path, 'r') as f:
                stdout = f.read().strip()
            with open(err_path, 'r') as f:
                stderr = f.read().strip()
            
            if exit_code == 0:
                return True, stdout
            else:
                return False, stderr or f"Exit code: {exit_code}"
        except subprocess.TimeoutExpired:
            return False, "Calendar took too long to respond (30s timeout). Is Calendar.app open? Try again in a moment."
        finally:
            # Cleanup temp files
            for path in [script_path, out_path, err_path]:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                    
    except Exception as e:
        return False, str(e)


def run_shell_script(script_name: str, *args) -> tuple[bool, str]:
    """Run a helper script from the scripts directory.

    Python helpers are invoked through sys.executable so EventKit scripts run
    in the same environment as this MCP server. This avoids falling back to a
    system Python that may not have PyObjC/EventKit installed.
    """
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return False, f"Script not found at {script_path}. Reinstall Amp or check that core/scripts/ is intact."

    if script_name.endswith('.py'):
        cmd = [sys.executable, str(script_path)] + [str(a) for a in args]
    else:
        cmd = [str(script_path)] + [str(a) for a in args]
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as out_file:
            out_path = out_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as err_file:
            err_path = err_file.name
        
        try:
            # Run script with args via subprocess.run (shell=False for safety)
            with open(out_path, 'w') as out_f, open(err_path, 'w') as err_f:
                result = subprocess.run(
                    cmd,
                    stdout=out_f,
                    stderr=err_f,
                    timeout=30
                )
                exit_code = result.returncode
            
            with open(out_path, 'r') as f:
                stdout = f.read().strip()
            with open(err_path, 'r') as f:
                stderr = f.read().strip()
            
            if exit_code == 0:
                return True, stdout
            else:
                return False, stderr or f"Exit code: {exit_code}"
        except subprocess.TimeoutExpired:
            return False, "Calendar took too long to respond (30s timeout). Is Calendar.app open? Try again in a moment."
        finally:
            for path in [out_path, err_path]:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                    
    except Exception as e:
        return False, str(e)


def parse_applescript_list(output: str) -> list[str]:
    """Parse comma-separated AppleScript output into a list"""
    if not output:
        return []
    # AppleScript returns lists like: item1, item2, item3
    return [item.strip() for item in output.split(', ') if item.strip()]


def parse_attendee_string(attendee_str: str) -> dict:
    """Parse an attendee string like 'Name<email>[status]' into a dict."""
    match = re.match(r'^(.+?)<(.+?)>\[(.+?)\]$', attendee_str.strip())
    if match:
        name, email, status = match.groups()
        name = name.strip()
        email = email.strip().lower()
        
        # If name equals email, try to extract a proper name from email
        if name.lower() == email.lower() or '@' in name:
            # Extract from email: firstname.lastname@domain -> Firstname Lastname
            local_part = email.split('@')[0]
            name = local_part.replace('.', ' ').replace('_', ' ').replace('-', ' ').title()
        
        return {
            'name': name,
            'email': email,
            'status': status.strip()
        }
    return None


def get_domain_from_email(email: str) -> str:
    """Extract domain from email address."""
    if '@' in email:
        return email.split('@')[1].lower()
    return None


def normalize_name_for_filename(name: str) -> str:
    """Convert a name to a filename-safe format."""
    # Replace spaces with underscores, remove special chars
    safe_name = re.sub(r'[^\w\s-]', '', name)
    safe_name = re.sub(r'\s+', '_', safe_name.strip())
    return safe_name


def find_person_page(name: str, email: str) -> Optional[Path]:
    """Find an existing person page by name or email."""
    # Try multiple name variations
    name_variations = [
        normalize_name_for_filename(name),
        # Also try extracting name from email (firstname.lastname@domain)
        normalize_name_for_filename(email.split('@')[0].replace('.', ' ').replace('_', ' ').title()) if '@' in email else None
    ]
    name_variations = [n for n in name_variations if n]
    
    # Check Internal and External folders
    for folder in ['Internal', 'External']:
        folder_path = PEOPLE_DIR / folder
        if folder_path.exists():
            for file in folder_path.glob('*.md'):
                file_stem_lower = file.stem.lower().replace('_', ' ').replace('-', ' ')
                
                # Check by filename variations
                for name_var in name_variations:
                    name_var_lower = name_var.lower().replace('_', ' ')
                    # Check if names match (allowing for partial matches)
                    if name_var_lower in file_stem_lower or file_stem_lower in name_var_lower:
                        return file
                    # Check individual name parts
                    name_parts = name_var_lower.split()
                    if len(name_parts) >= 2:
                        # Check if first and last name are in filename
                        if name_parts[0] in file_stem_lower and name_parts[-1] in file_stem_lower:
                            return file
                
                # Check by email in file content
                try:
                    content = file.read_text()
                    if email.lower() in content.lower():
                        return file
                except OSError:
                    pass
    return None


# Initialize the MCP server
app = Server("amp-calendar-mcp")


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available calendar tools"""
    return [
        types.Tool(
            name="calendar_list_calendars",
            description="List all calendars available in Apple Calendar",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="calendar_get_events",
            description="Get events from a specific calendar for a date range",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_name": {
                        "type": "string",
                        "description": "Name of the calendar (e.g., 'Work' or 'user@example.com')"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (defaults to today)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (defaults to start_date + 1 day)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events to return (default: 50)",
                        "default": 50
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="calendar_get_today",
            description="Quick access to today's events from a calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_name": {
                        "type": "string",
                        "description": "Calendar name (optional, defaults to your work calendar)"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="calendar_create_event",
            description="Create a new calendar event",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_name": {
                        "type": "string",
                        "description": "Name of the calendar to add the event to"
                    },
                    "title": {
                        "type": "string",
                        "description": "Event title/summary"
                    },
                    "start_datetime": {
                        "type": "string",
                        "description": "Start datetime in 'YYYY-MM-DD HH:MM' format"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration in minutes (default: 30)",
                        "default": 30
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional event description/notes"
                    },
                    "location": {
                        "type": "string",
                        "description": "Optional event location"
                    }
                },
                "required": ["title", "start_datetime"]
            }
        ),
        types.Tool(
            name="calendar_search_events",
            description="Search for events by title across a calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_name": {
                        "type": "string",
                        "description": "Name of the calendar to search"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search term to match against event titles"
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "How many days back to search (default: 30)",
                        "default": 30
                    },
                    "days_forward": {
                        "type": "integer",
                        "description": "How many days forward to search (default: 30)",
                        "default": 30
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="calendar_delete_event",
            description="Delete a calendar event by its title and date",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_name": {
                        "type": "string",
                        "description": "Name of the calendar containing the event"
                    },
                    "title": {
                        "type": "string",
                        "description": "Exact title of the event to delete"
                    },
                    "event_date": {
                        "type": "string",
                        "description": "Date of the event in YYYY-MM-DD format"
                    }
                },
                "required": ["title", "event_date"]
            }
        ),
        types.Tool(
            name="calendar_get_next_event",
            description="Get the next upcoming event from a calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_name": {
                        "type": "string",
                        "description": "Calendar name (optional, defaults to your work calendar)"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="calendar_get_events_with_attendees",
            description="Get events with full attendee details (name, email, status)",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_name": {
                        "type": "string",
                        "description": "Name of the calendar"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (defaults to today)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (defaults to start_date + 1 day)"
                    }
                },
                "required": []
            }
        ),
        # --- Apple Reminders tools ---
        types.Tool(
            name="reminders_list_items",
            description="Get incomplete items from an Apple Reminders list. Use with 'Amp Inbox' to check for mobile-captured tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_name": {
                        "type": "string",
                        "description": "Name of the Reminders list (default: 'Amp Inbox')"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="reminders_complete_item",
            description="Mark a Reminder as complete (e.g., after triaging into Amp tasks)",
            inputSchema={
                "type": "object",
                "properties": {
                    "reminder_id": {
                        "type": "string",
                        "description": "The calendarItemIdentifier of the reminder to complete"
                    }
                },
                "required": ["reminder_id"]
            }
        ),
        types.Tool(
            name="reminders_create_item",
            description="Create a new Reminder in a specific list (e.g., push P0 tasks to 'Amp Today' for iOS notifications)",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_name": {
                        "type": "string",
                        "description": "Name of the Reminders list (default: 'Amp Today')"
                    },
                    "title": {
                        "type": "string",
                        "description": "Reminder title"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes/description"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Optional due date in YYYY-MM-DD format"
                    }
                },
                "required": ["title"]
            }
        ),
        types.Tool(
            name="reminders_ensure_lists",
            description="Create 'Amp Inbox' and 'Amp Today' Reminders lists if they don't exist. Idempotent — safe to call every time.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="reminders_list_completed",
            description="Get recently completed items from a Reminders list (last 2 days). Use with 'Amp Today' to detect tasks completed on phone for sync back to Amp.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_name": {
                        "type": "string",
                        "description": "Name of the Reminders list (default: 'Amp Today')"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="reminders_find_and_complete",
            description="Find a Reminder by title match and mark it complete. Use for Amp → Reminders sync when a task is done in Amp.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_name": {
                        "type": "string",
                        "description": "Name of the Reminders list (default: 'Amp Today')"
                    },
                    "title_query": {
                        "type": "string",
                        "description": "Title text to match against (fuzzy substring match)"
                    }
                },
                "required": ["title_query"]
            }
        ),
        types.Tool(
            name="reminders_clear_completed",
            description="Remove all completed Reminders from a list. Use to clean up 'Amp Today' at start of day.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_name": {
                        "type": "string",
                        "description": "Name of the Reminders list (default: 'Amp Today')"
                    }
                },
                "required": []
            }
        ),
    ]


@app.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""
    try:
        return await _handle_call_tool_inner(name, arguments)
    except Exception as e:
        if _HAS_HEALTH:
            _tool_human_messages = {
                "calendar_list_calendars": "Could not list calendars. Is Calendar.app open and accessible?",
                "calendar_get_events": "Could not fetch calendar events. Check that Calendar.app is running.",
                "calendar_get_today": "Could not fetch today's events. Is Calendar.app open?",
                "calendar_create_event": "Could not create the calendar event. Check Calendar.app permissions.",
                "calendar_search_events": "Calendar search failed. Is Calendar.app open and accessible?",
                "calendar_delete_event": "Could not delete the calendar event. Check Calendar.app permissions.",
                "calendar_get_next_event": "Could not find the next event. Is Calendar.app running?",
                "calendar_get_events_with_attendees": "Could not fetch attendee details. Check Calendar.app permissions.",
            }
            _log_health_error(
                source="calendar-mcp",
                message=str(e),
                human_message=_tool_human_messages.get(name, f"Calendar tool '{name}' hit an error. Try again, or check that Calendar.app is open."),
                context={"tool": name},
            )
        raise


async def _fetch_events(start_date: str, end_date: str = None, calendar_name: str = None, limit: int = None) -> dict:
    """Core event fetching logic shared by calendar_get_events and calendar_get_today."""
    calendar_name = calendar_name or DEFAULT_WORK_CALENDAR

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = start_dt + timedelta(days=1)

    today_dt = datetime.combine(_tz_today(), datetime.min.time())
    start_offset = (start_dt - today_dt).days
    end_offset = (end_dt - today_dt).days

    success, output = run_shell_script(
        "calendar_eventkit.py",
        "events",
        calendar_name,
        str(start_offset),
        str(end_offset)
    )

    if not success:
        return mcp_error(output)

    try:
        events = json.loads(output)
    except json.JSONDecodeError as e:
        return mcp_error(f"Could not parse calendar data (JSON error: {e}). The calendar script may have returned unexpected output.")

    local_tz = datetime.now().astimezone().tzinfo
    for event in events:
        if event.get('start'):
            try:
                raw = event['start'].strip()
                if ' +0000' in raw:
                    utc_dt = datetime.fromisoformat(raw.replace(' +0000', '+00:00'))
                elif raw.endswith('Z'):
                    utc_dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                else:
                    utc_dt = datetime.fromisoformat(raw)
                    if utc_dt.tzinfo is None:
                        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                event['start'] = utc_dt.astimezone(local_tz).isoformat()
            except (ValueError, TypeError) as e:
                logging.warning(f"Skipping event with malformed start date: {e}")
        if event.get('end'):
            try:
                raw = event['end'].strip()
                if ' +0000' in raw:
                    utc_dt = datetime.fromisoformat(raw.replace(' +0000', '+00:00'))
                elif raw.endswith('Z'):
                    utc_dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                else:
                    utc_dt = datetime.fromisoformat(raw)
                    if utc_dt.tzinfo is None:
                        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                event['end'] = utc_dt.astimezone(local_tz).isoformat()
            except (ValueError, TypeError) as e:
                logging.warning(f"Skipping event with malformed end date: {e}")

    filtered_events = []
    for event in events:
        if event.get('all_day'):
            try:
                event_start_date = datetime.fromisoformat(event['start']).date()
            except (ValueError, TypeError) as e:
                logging.warning(f"Skipping event with malformed date: {e}")
                continue
            if start_dt.date() <= event_start_date < end_dt.date():
                filtered_events.append(event)
        else:
            filtered_events.append(event)

    if limit:
        filtered_events = filtered_events[:limit]

    return {
        "success": True,
        "calendar": calendar_name,
        "date_range": f"{start_date} to {end_dt.strftime('%Y-%m-%d')}",
        "events": filtered_events,
        "count": len(filtered_events)
    }


async def _handle_call_tool_inner(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Inner tool handler — wrapped by handle_call_tool for health reporting."""

    arguments = arguments or {}

    if name == "calendar_list_calendars":
        # Use fast EventKit
        success, output = run_shell_script("calendar_eventkit.py", "list")
        
        if success:
            try:
                calendars = json.loads(output)
                # Extract just the titles for backward compatibility
                calendar_names = [cal["title"] for cal in calendars]
                result = {
                    "success": True,
                    "calendars": calendar_names,
                    "count": len(calendar_names),
                    "details": calendars  # Full details for advanced use
                }
            except json.JSONDecodeError as e:
                result = mcp_error(f"Could not parse calendar data (JSON error: {e}). The calendar script may have returned unexpected output.")
        else:
            result = mcp_error(output)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "calendar_get_events":
        result = await _fetch_events(
            start_date=arguments.get("start_date", _tz_now().strftime("%Y-%m-%d")),
            end_date=arguments.get("end_date"),
            calendar_name=arguments.get("calendar_name"),
            limit=arguments.get("limit"),
        )
        return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]
    
    elif name == "calendar_get_today":
        result = await _fetch_events(
            start_date=_tz_now().strftime("%Y-%m-%d"),
            calendar_name=arguments.get("calendar_name"),
        )
        return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]
    
    elif name == "calendar_create_event":
        calendar_name = arguments.get("calendar_name", DEFAULT_WORK_CALENDAR)
        title = arguments["title"]
        start_str = arguments["start_datetime"]
        duration = arguments.get("duration_minutes", 30)
        description = arguments.get("description", "")
        location = arguments.get("location", "")
        
        # Validate datetime format
        try:
            datetime.strptime(start_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return [types.TextContent(type="text", text=json.dumps(mcp_error(f"Invalid datetime format. Use 'YYYY-MM-DD HH:MM' (e.g., '2026-03-15 14:00'). Got: {start_str}"), indent=2))]
        
        # Use shell script
        success, output = run_shell_script(
            "calendar_create_event.sh",
            calendar_name,
            title,
            start_str,
            str(duration),
            description,
            location
        )
        
        if success:
            result = {
                "success": True,
                "message": output,
                "event": {
                    "title": title,
                    "calendar": calendar_name,
                    "start": start_str,
                    "duration_minutes": duration
                }
            }
        else:
            result = mcp_error(output)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]
    
    elif name == "calendar_search_events":
        calendar_name = arguments.get("calendar_name", DEFAULT_WORK_CALENDAR)
        query = arguments["query"]
        days_back = arguments.get("days_back", 30)
        days_forward = arguments.get("days_forward", 30)
        
        # Use fast EventKit search
        success, output = run_shell_script(
            "calendar_eventkit.py",
            "search",
            calendar_name,
            query,
            str(days_back),
            str(days_forward)
        )
        
        if success:
            try:
                events = json.loads(output)
                result = {
                    "success": True,
                    "query": query,
                    "calendar": calendar_name,
                    "events": events,
                    "count": len(events)
                }
            except json.JSONDecodeError as e:
                result = mcp_error(f"Could not parse calendar data (JSON error: {e}). The calendar script may have returned unexpected output.")
        else:
            result = mcp_error(output)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "calendar_delete_event":
        calendar_name = arguments.get("calendar_name", DEFAULT_WORK_CALENDAR)
        title = arguments["title"]
        event_date = arguments["event_date"]
        
        # Parse the date and calculate offset from today
        try:
            target_dt = datetime.strptime(event_date, "%Y-%m-%d")
        except ValueError:
            return [types.TextContent(type="text", text=json.dumps(mcp_error(f"Invalid date format. Use 'YYYY-MM-DD', got: {event_date}"), indent=2))]
        
        today_dt = datetime.combine(_tz_today(), datetime.min.time())
        day_offset = (target_dt - today_dt).days
        
        success, output = run_shell_script(
            "calendar_delete_event.sh",
            calendar_name,
            title,
            str(day_offset)
        )
        
        if success:
            result = {
                "success": True,
                "message": output
            }
        else:
            result = mcp_error(output)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "calendar_get_next_event":
        calendar_name = arguments.get("calendar_name", DEFAULT_WORK_CALENDAR)
        
        # Use fast EventKit
        success, output = run_shell_script("calendar_eventkit.py", "next", calendar_name)
        
        if success:
            try:
                event_data = json.loads(output)
                if "message" in event_data:
                    # No events found
                    result = {
                        "success": True,
                        "message": event_data["message"],
                        "next_event": None
                    }
                else:
                    # Event found
                    result = {
                        "success": True,
                        "next_event": event_data
                    }
            except json.JSONDecodeError as e:
                result = mcp_error(f"Could not parse calendar data (JSON error: {e}). The calendar script may have returned unexpected output.")
        else:
            result = mcp_error(output)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "calendar_get_events_with_attendees":
        calendar_name = arguments.get("calendar_name", DEFAULT_WORK_CALENDAR)
        start_date = arguments.get("start_date", _tz_now().strftime("%Y-%m-%d"))
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        if "end_date" in arguments:
            end_dt = datetime.strptime(arguments["end_date"], "%Y-%m-%d")
        else:
            end_dt = start_dt + timedelta(days=1)
        
        today_dt = datetime.combine(_tz_today(), datetime.min.time())
        start_offset = (start_dt - today_dt).days
        end_offset = (end_dt - today_dt).days
        
        # Use fast EventKit with attendee details
        success, output = run_shell_script(
            "calendar_eventkit.py",
            "attendees",
            calendar_name,
            str(start_offset),
            str(end_offset)
        )
        
        if success:
            try:
                events = json.loads(output)
                
                # Enhance attendees with person page links
                for event in events:
                    if "attendees" in event:
                        for att in event["attendees"]:
                            # Check if person page exists
                            person_page = find_person_page(att.get('name', ''), att.get('email', ''))
                            att['has_person_page'] = person_page is not None
                            if person_page:
                                att['person_page'] = str(person_page.relative_to(VAULT_PATH))
                
                result = {
                    "success": True,
                    "calendar": calendar_name,
                    "date_range": f"{start_date} to {end_dt.strftime('%Y-%m-%d')}",
                    "events": events,
                    "count": len(events)
                }
            except json.JSONDecodeError as e:
                result = mcp_error(f"Could not parse calendar data (JSON error: {e}). The calendar script may have returned unexpected output.")
        else:
            result = mcp_error(output)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]
    
    # --- Apple Reminders handlers ---
    elif name == "reminders_list_items":
        list_name = arguments.get("list_name", "Amp Inbox")
        success, output = run_shell_script("reminders_eventkit.py", "list_items", list_name)
        if success:
            try:
                items = json.loads(output)
                result = {"success": True, "list": list_name, "items": items, "count": len(items)}
            except json.JSONDecodeError as e:
                result = mcp_error(f"Could not parse calendar data (JSON error: {e}). The calendar script may have returned unexpected output.")
        else:
            result = mcp_error(output)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "reminders_complete_item":
        reminder_id = arguments["reminder_id"]
        success, output = run_shell_script("reminders_eventkit.py", "complete", reminder_id)
        if success:
            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                result = {"success": True, "message": output}
        else:
            result = mcp_error(output)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "reminders_create_item":
        list_name = arguments.get("list_name", "Amp Today")
        title = arguments["title"]
        notes = arguments.get("notes", "")
        due_date = arguments.get("due_date", "")
        success, output = run_shell_script("reminders_eventkit.py", "create", list_name, title, notes, due_date)
        if success:
            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                result = {"success": True, "message": output}
        else:
            result = mcp_error(output)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "reminders_ensure_lists":
        success, output = run_shell_script("reminders_eventkit.py", "ensure_lists")
        if success:
            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                result = {"success": True, "message": output}
        else:
            result = mcp_error(output)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "reminders_list_completed":
        list_name = arguments.get("list_name", "Amp Today")
        success, output = run_shell_script("reminders_eventkit.py", "list_completed", list_name)
        if success:
            try:
                items = json.loads(output)
                result = {"success": True, "list": list_name, "items": items, "count": len(items)}
            except json.JSONDecodeError as e:
                result = mcp_error(f"Could not parse calendar data (JSON error: {e}). The calendar script may have returned unexpected output.")
        else:
            result = mcp_error(output)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "reminders_find_and_complete":
        list_name = arguments.get("list_name", "Amp Today")
        title_query = arguments["title_query"]
        success, output = run_shell_script("reminders_eventkit.py", "find_and_complete", list_name, title_query)
        if success:
            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                result = {"success": True, "message": output}
        else:
            result = mcp_error(output)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "reminders_clear_completed":
        list_name = arguments.get("list_name", "Amp Today")
        success, output = run_shell_script("reminders_eventkit.py", "clear_completed", list_name)
        if success:
            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                result = {"success": True, "message": output}
        else:
            result = mcp_error(output)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [types.TextContent(type="text", text=json.dumps({
            "error": f"Unknown tool: {name}"
        }, indent=2))]


async def _main():
    """Async main entry point for the MCP server"""
    if _HAS_HEALTH:
        _mark_healthy("calendar-mcp")
    logger.info("Starting Amp Calendar MCP Server")
    logger.info("Using Apple Calendar via AppleScript")
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="amp-calendar-mcp",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main():
    """Sync entry point for console script"""
    import asyncio
    asyncio.run(_main())


if __name__ == "__main__":
    main()
