#!/usr/bin/env python3
"""
MCP Server for Amp Onboarding System

Provides stateful onboarding with validation, dependency checking, and vault creation.
Ensures all required fields (especially email_domain) are collected before completion.

Features:
- Session state management with resume capability
- Step-by-step validation enforcement
- Dependency verification (Python packages, Calendar.app)
- Automatic MCP configuration
- PARA folder structure creation
"""

import os
import sys
import json
import logging
import re
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, date

try:
    import yaml
except ImportError:
    yaml = None

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Analytics helper (optional - gracefully degrade if not available)
try:
    from analytics_helper import fire_event as _fire_analytics_event
    HAS_ANALYTICS = True
except ImportError:
    HAS_ANALYTICS = False
    def _fire_analytics_event(event_name, properties=None):
        return {'fired': False, 'reason': 'analytics_not_available'}

# Health system — error queue and health reporting
try:
    from core.constants import (
        SYSTEM_DIR as SYSTEM_DIR_NAME,
        PROJECTS_DIR as PROJECTS_DIR_NAME,
        AREAS_DIR as AREAS_DIR_NAME,
        INBOX_DIR as INBOX_DIR_NAME,
        RESOURCES_DIR as RESOURCES_DIR_NAME,
        ARCHIVES_DIR as ARCHIVES_DIR_NAME,
        QUARTER_GOALS_DIR as QUARTER_GOALS_DIR_NAME,
        TASKS_DIR as TASKS_DIR_NAME,
        WEEK_PRIORITIES_DIR as WEEK_PRIORITIES_DIR_NAME,
        PEOPLE_INTERNAL_DIR as PEOPLE_INTERNAL_DIR_NAME,
        PEOPLE_EXTERNAL_DIR as PEOPLE_EXTERNAL_DIR_NAME,
        COMPANIES_DIR as COMPANIES_DIR_NAME,
    )
    from core.utils.amp_logger import log_error as _log_health_error, mark_healthy as _mark_healthy
    _HAS_HEALTH = True
except ImportError:
    _HAS_HEALTH = False

# Timezone detection
try:
    from core.utils.timezone import detect_system_timezone
    _HAS_TIMEZONE = True
except ImportError:
    _HAS_TIMEZONE = False
    def detect_system_timezone():
        return ""

from core.utils import mcp_error, validate_vault_path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom JSON encoder for handling date/datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

# Configuration - Vault paths
BASE_DIR = Path(os.environ.get('VAULT_PATH', Path.cwd()))
SESSION_FILE = BASE_DIR / SYSTEM_DIR_NAME / '.onboarding-session.json'
MARKER_FILE = BASE_DIR / SYSTEM_DIR_NAME / '.onboarding-complete'
USER_PROFILE_FILE = BASE_DIR / SYSTEM_DIR_NAME / 'user-profile.yaml'
USER_PROFILE_TEMPLATE = BASE_DIR / SYSTEM_DIR_NAME / 'user-profile.example.yaml'
PILLARS_FILE = BASE_DIR / SYSTEM_DIR_NAME / 'pillars.yaml'
CLAUDE_MD = BASE_DIR / 'CLAUDE.md'
MCP_CONFIG_EXAMPLE = BASE_DIR / '.mcp.json.template'
MCP_CONFIG_TARGET = BASE_DIR / '.mcp.json'

# Role definitions for validation
ROLES = {
    1: ("Product Manager", "product"),
    2: ("Sales / Account Executive", "sales"),
    3: ("Marketing", "marketing"),
    4: ("Engineering", "engineering"),
    5: ("Design", "design"),
    6: ("Customer Success", "customer_success"),
    7: ("Solutions Engineering", "engineering"),
    8: ("Product Operations", "operations"),
    9: ("RevOps / BizOps", "operations"),
    10: ("Data / Analytics", "operations"),
    11: ("Finance", "finance"),
    12: ("People (HR)", "support"),
    13: ("Legal", "support"),
    14: ("IT Support", "support"),
    15: ("Founder", "leadership"),
    16: ("CEO", "leadership"),
    17: ("CFO", "leadership"),
    18: ("COO", "leadership"),
    19: ("CMO", "leadership"),
    20: ("CRO", "leadership"),
    21: ("CTO", "leadership"),
    22: ("CPO", "leadership"),
    23: ("CIO", "leadership"),
    24: ("CISO", "leadership"),
    25: ("CHRO / Chief People Officer", "leadership"),
    26: ("CLO / General Counsel", "leadership"),
    27: ("CCO (Chief Customer Officer)", "leadership"),
    28: ("Fractional CPO", "advisory"),
    29: ("Consultant", "advisory"),
    30: ("Coach", "advisory"),
    31: ("Venture Capital / Private Equity", "advisory"),
}

FORMALITY_LEVELS = ["formal", "professional_casual", "casual"]
DIRECTNESS_LEVELS = ["very_direct", "balanced", "supportive"]
CAREER_LEVELS = ["junior", "mid", "senior", "leadership", "c_suite"]
COACHING_STYLES = ["encouraging", "collaborative", "challenging"]
ONBOARDING_VERSION = "2.0"
REQUIRED_STEPS = {
    1: "Name",
    2: "Role",
    3: "Email Domain",
    4: "Communication Preferences",
}
DEFAULT_PRIORITY_LIMITS = {
    "P0": 3,
    "P1": 5,
    "P2": 10,
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_success_response(data: Any, message: str = None) -> Dict:
    """Create a standardized success response"""
    response = {"success": True, "data": data}
    if message:
        response["message"] = message
    return response

def create_error_response(error: str, step: int = None, field: str = None, suggestion: str = None) -> Dict:
    """Create a standardized error response"""
    response = mcp_error(error)
    if step is not None:
        response["step"] = step
    if field:
        response["field"] = field
    if suggestion:
        response["suggestion"] = suggestion
    return response

def sanitize_markdown_input(text: str) -> str:
    """Strip characters that could inject markdown structure."""
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = text.replace('#', '').replace('---', '-')
    return text.strip()

def atomic_write_text(filepath: Path, content: str) -> None:
    """Write text to file atomically via temp file + rename."""
    dirpath = filepath.parent
    dirpath.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(dirpath), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.rename(tmp_path, str(filepath))
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

def load_session() -> Optional[Dict]:
    """Load existing onboarding session"""
    if not SESSION_FILE.exists():
        return None
    
    try:
        with open(SESSION_FILE, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error loading session: {e}")
        return None

def save_session(session_data: Dict) -> bool:
    """Save onboarding session"""
    try:
        # Ensure System directory exists
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        session_data['last_updated'] = datetime.now().isoformat()
        
        atomic_write_text(SESSION_FILE, json.dumps(session_data, indent=2, cls=DateTimeEncoder))
        return True
    except (OSError, TypeError, ValueError) as e:
        logger.error(f"Error saving session: {e}")
        return False

def create_new_session() -> Dict:
    """Create a new onboarding session"""
    return {
        "version": ONBOARDING_VERSION,
        "started_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "completed_steps": [],
        "current_step": 1,
        "data": {}
    }

def validate_email_domain(domain: str) -> tuple[bool, Optional[str]]:
    """Validate email domain format (supports multiple domains separated by commas)"""
    if not domain or not domain.strip():
        return False, "Email domain can't be empty. Enter your company domain (e.g., 'acme.com')."
    
    domain = domain.strip()
    
    # Check for @ symbol
    if '@' in domain:
        return False, "Don't include the @ symbol. Just the domain part (e.g., 'pendo.io' not '@pendo.io')."
    
    # Split by comma if multiple domains
    domains = [d.strip() for d in domain.split(',')]
    
    for d in domains:
        if not d:
            continue
        
        # Check for at least one dot (basic domain validation)
        if '.' not in d:
            return False, f"'{d}' doesn't look like a domain. It needs at least one dot (e.g., 'acme.com')."
        
        # Check for valid characters (alphanumeric, dots, hyphens)
        if not re.match(r'^[a-zA-Z0-9\-\.]+$', d):
            return False, f"'{d}' has characters that aren't allowed in a domain. Stick to letters, numbers, dots, and hyphens."
    
    return True, None

def validate_pillars(pillars: List[str]) -> tuple[bool, Optional[str]]:
    """Validate strategic pillars"""
    if not pillars or not isinstance(pillars, list):
        return False, "Pillars should be a list with at least one item."
    
    # Filter out empty strings
    pillars = [p.strip() for p in pillars if p and p.strip()]
    
    if len(pillars) < 2:
        return False, "You need at least 2 pillars so Amp can help you balance priorities."
    
    if len(pillars) > 3:
        return True, f"Warning: {len(pillars)} pillars provided. 2-3 is recommended for focus."
    
    return True, None

def normalize_step_data(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Accept either the step_data wrapper or top-level step fields."""
    normalized: Dict[str, Any] = {}
    top_level_fields = ("name", "role", "role_group", "role_number", "email_domain", "obsidian_mode")

    for field in top_level_fields:
        if field in arguments:
            normalized[field] = arguments[field]

    communication_fields = ("formality", "directness", "career_level", "coaching_style")
    communication = {}

    if isinstance(arguments.get("communication"), dict):
        communication.update(arguments["communication"])

    for field in communication_fields:
        if field in arguments:
            communication[field] = arguments[field]

    step_data = arguments.get("step_data")
    if isinstance(step_data, dict):
        nested_communication = step_data.get("communication")
        if isinstance(nested_communication, dict):
            communication.update(nested_communication)

        for key, value in step_data.items():
            if key == "communication":
                continue
            normalized[key] = value

    if communication:
        normalized["communication"] = communication

    return normalized

def build_completion_marker(session: Dict[str, Any]) -> Dict[str, Any]:
    """Build the persisted onboarding completion marker from session data."""
    return {
        "completed_at": datetime.now().isoformat(),
        "user_name": session["data"]["name"],
        "role": session["data"]["role"],
        "email_domain": session["data"].get("email_domain", ""),
        "has_pillars": bool(session["data"].get("pillars", [])),
        "phase2_completed": False,
        "pre_analysis_deferred": True,
    }

def contains_role_phrase(role_text: str, phrase: str) -> bool:
    """Match role phrases on token boundaries to avoid substring false positives."""
    normalized_phrase = phrase.lower().strip()
    if not normalized_phrase:
        return False
    return re.search(rf'(?<!\w){re.escape(normalized_phrase)}(?!\w)', role_text) is not None

def infer_role_group(role: str) -> str:
    """Infer a reasonable role group from freeform role text."""
    role_lower = role.lower().strip()
    if not role_lower:
        return "operations"

    for _, (label, group) in ROLES.items():
        label_lower = label.lower().strip()
        if role_lower == label_lower or contains_role_phrase(role_lower, label_lower):
            return group

    keyword_groups = {
        "product": ["product", "pm", "product manager"],
        "sales": ["sales", "account executive", "account manager", "revenue", "business development"],
        "marketing": ["marketing", "brand", "content", "demand gen", "growth"],
        "engineering": ["engineer", "engineering", "developer", "software", "sre", "platform"],
        "design": ["design", "designer", "ux", "ui", "researcher"],
        "customer_success": ["customer success", "csm", "implementation", "account management"],
        "finance": ["finance", "accounting", "fp&a", "controller"],
        "support": ["people", "human resources", "hr", "legal", "recruiting", "talent", "it support"],
        "leadership": ["ceo", "cfo", "coo", "cto", "cmo", "cpo", "chief", "vp", "vice president", "head of"],
        "advisory": ["consultant", "coach", "advisor", "investor", "venture capital", "private equity"],
        "operations": ["operations", "program manager", "program management", "project manager", "bizops", "revops", "chief of staff"],
    }

    for group, keywords in keyword_groups.items():
        if any(contains_role_phrase(role_lower, keyword) for keyword in keywords):
            return group

    return "operations"

def build_pillar_entries(pillars: Optional[List[str]]) -> tuple[List[Dict[str, Any]], bool]:
    """Build pillar entries, falling back to a single general bucket for first-run setup."""
    cleaned = [p.strip() for p in (pillars or []) if p and p.strip()]
    if cleaned:
        return ([
            {
                "id": re.sub(r'[^a-z0-9]+', '-', pillar.lower()).strip('-') or f"pillar-{idx}",
                "name": pillar,
                "description": "",
                "keywords": [],
            }
            for idx, pillar in enumerate(cleaned, start=1)
        ], True)

    return ([{
        "id": "general",
        "name": "General",
        "description": "Temporary bucket until you define your strategic pillars.",
        "keywords": [],
    }], False)

def check_python_packages() -> Dict[str, Any]:
    """Check if required Python packages are installed"""
    packages = {'mcp': '>=1.0.0', 'yaml': '>=6.0', 'aiohttp': '>=3.9.0'}
    results = {}
    
    for package, version in packages.items():
        try:
            if package == 'yaml':
                import yaml as _yaml
                results['yaml'] = {"installed": True, "version": "available"}
            elif package == 'mcp':
                import mcp
                results['mcp'] = {"installed": True, "version": "available"}
            elif package == 'aiohttp':
                import aiohttp
                results['aiohttp'] = {"installed": True, "version": aiohttp.__version__}
        except ImportError:
            results[package] = {"installed": False, "required": version}
    
    return results

def check_calendar_app() -> Dict[str, Any]:
    """Check if Calendar.app is accessible (macOS only)"""
    if platform.system() != 'Darwin':
        return {
            "available": False,
            "reason": "Not macOS",
            "required": False
        }
    
    try:
        # Try to run a simple AppleScript to check Calendar access
        result = subprocess.run(
            ['osascript', '-e', 'tell application "Calendar" to get name of calendars'],
            capture_output=True,
            timeout=5,
            text=True
        )
        
        if result.returncode == 0:
            return {"available": True, "calendars_found": True}
        else:
            return {
                "available": False,
                "reason": "Calendar.app not accessible or permission denied",
                "required": False
            }
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning("Calendar app check failed: %s", e)
        return {
            "available": False,
            "reason": str(e),
            "required": False
        }


def create_para_structure(base_path: Path) -> List[str]:
    """Create PARA folder structure"""
    folders = [
        PROJECTS_DIR_NAME,
        PEOPLE_INTERNAL_DIR_NAME,
        PEOPLE_EXTERNAL_DIR_NAME,
        COMPANIES_DIR_NAME,
        f"{INBOX_DIR_NAME}/Meetings",
        f"{INBOX_DIR_NAME}/Ideas",
        f"{INBOX_DIR_NAME}/Plans",
        f"{INBOX_DIR_NAME}/Drop_Zone",
        f"{RESOURCES_DIR_NAME}/Learnings",
        f"{RESOURCES_DIR_NAME}/Quarterly_Reviews",
        f"{ARCHIVES_DIR_NAME}/{PROJECTS_DIR_NAME}",
        f"{ARCHIVES_DIR_NAME}/Plans",
        f"{ARCHIVES_DIR_NAME}/Reviews",
        f"{SYSTEM_DIR_NAME}/Templates",
        QUARTER_GOALS_DIR_NAME,
        TASKS_DIR_NAME,
        WEEK_PRIORITIES_DIR_NAME,
    ]
    
    created = []
    for folder in folders:
        folder_path = base_path / folder
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            created.append(folder)
    
    return created

def create_initial_files(base_path: Path, session_data: Dict) -> List[str]:
    """Create initial state files"""
    created = []
    
    # Create Tasks.md
    tasks_file = base_path / TASKS_DIR_NAME / 'Tasks.md'
    if not tasks_file.exists():
        tasks_content = """# Tasks

## Instructions
- Tasks are organized by pillar and priority
- Use task IDs (^task-YYYYMMDD-XXX) for cross-file sync
- Priorities: P0 (urgent), P1 (important), P2 (normal), P3 (low)

---

"""
        pillar_entries, _ = build_pillar_entries(session_data['data'].get('pillars', []))
        for pillar in pillar_entries:
            tasks_content += f"## {sanitize_markdown_input(pillar['name'])} #{sanitize_markdown_input(pillar['id'])}\n\n"
        
        tasks_file.write_text(tasks_content)
        created.append(f'{TASKS_DIR_NAME}/Tasks.md')
    
    # Create Week_Priorities.md
    priorities_file = base_path / WEEK_PRIORITIES_DIR_NAME / 'Week_Priorities.md'
    if not priorities_file.exists():
        priorities_content = """# Week Priorities

*Updated: Week of [date]*

## This Week's Focus

### Top 3 Priorities

1. 
2. 
3. 

---

"""
        priorities_file.write_text(priorities_content)
        created.append(f'{WEEK_PRIORITIES_DIR_NAME}/Week_Priorities.md')
    
    return created

def create_user_profile(session_data: Dict) -> bool:
    """Create user-profile.yaml from session data"""
    try:
        # Load template
        if not USER_PROFILE_TEMPLATE.exists():
            logger.error("user-profile.example.yaml not found")
            return False
        
        with open(USER_PROFILE_TEMPLATE, 'r') as f:
            profile = yaml.safe_load(f) if yaml else {}
        
        # Update with session data
        data = session_data['data']
        profile['name'] = data.get('name', '')
        profile['role'] = data.get('role', '')
        profile['role_group'] = data.get('role_group', '')
        profile['company'] = data.get('company', '')
        profile['company_size'] = data.get('company_size', '')
        profile['email_domain'] = data.get('email_domain', '')
        
        # Update Obsidian mode (defaults to false)
        profile['obsidian_mode'] = data.get('obsidian_mode', False)
        
        # Auto-detect timezone if not already set
        if not profile.get('timezone'):
            detected_tz = detect_system_timezone()
            if detected_tz:
                profile['timezone'] = detected_tz
                logger.info(f"Auto-detected timezone: {detected_tz}")
        
        # Update communication preferences
        comm = data.get('communication', {})
        if 'communication' not in profile:
            profile['communication'] = {}
        profile['communication']['formality'] = comm.get('formality', 'professional_casual')
        profile['communication']['directness'] = comm.get('directness', 'balanced')
        profile['communication']['career_level'] = comm.get('career_level', 'mid')
        profile['communication']['coaching_style'] = comm.get('coaching_style', 'collaborative')
        
        # Save
        import io
        buf = io.StringIO()
        yaml.dump(profile, buf, default_flow_style=False, sort_keys=False)
        atomic_write_text(USER_PROFILE_FILE, buf.getvalue())
        
        return True
    except Exception as e:
        logger.error(f"Error creating user profile: {e}")
        return False

def create_pillars_file(pillars: Optional[List[str]]) -> bool:
    """Create pillars.yaml from pillar list or a temporary general bucket."""
    try:
        pillar_entries, configured = build_pillar_entries(pillars)
        pillars_data = {
            "configured": configured,
            "pillars": pillar_entries,
            "priority_limits": DEFAULT_PRIORITY_LIMITS,
        }

        import io
        buf = io.StringIO()
        yaml.dump(pillars_data, buf, default_flow_style=False, sort_keys=False)
        atomic_write_text(PILLARS_FILE, buf.getvalue())
        
        return True
    except Exception as e:
        logger.error(f"Error creating pillars file: {e}")
        return False

def update_claude_md(session_data: Dict) -> bool:
    """Update CLAUDE.md User Profile section"""
    try:
        if not CLAUDE_MD.exists():
            logger.error("CLAUDE.md not found")
            return False
        
        content = CLAUDE_MD.read_text()
        data = session_data['data']
        _, pillars_configured = build_pillar_entries(data.get('pillars', []))
        
        # Find and replace User Profile section
        safe_name = sanitize_markdown_input(data.get('name', 'Not configured'))
        safe_role = sanitize_markdown_input(data.get('role', 'Not configured'))
        safe_domain = sanitize_markdown_input(data.get('email_domain', 'Not configured'))
        safe_style = sanitize_markdown_input(data.get('communication', {}).get('formality', 'Not configured'))
        profile_section = f"""## User Profile
        
<!-- Updated during onboarding -->
**Name:** {safe_name}
**Role:** {safe_role}
**Email Domain:** {safe_domain}
**Working Style:** {safe_style}
**Pillars:**
"""
        if pillars_configured:
            for pillar in data.get('pillars', []):
                profile_section += f"- {sanitize_markdown_input(pillar)}\n"
        else:
            profile_section += "- Not configured yet, using the General temporary bucket\n"
        
        # Replace between "## User Profile" and next "---"
        pattern = r'## User Profile.*?---'
        replacement = profile_section + "\n---"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        atomic_write_text(CLAUDE_MD, content)
        return True
    except (OSError, KeyError, ValueError) as e:
        logger.error(f"Error updating CLAUDE.md: {e}")
        return False

def setup_mcp_config(vault_path: Path) -> tuple[bool, Optional[str]]:
    """Setup .mcp.json by replacing {{VAULT_PATH}} in the template."""
    try:
        if not MCP_CONFIG_EXAMPLE.exists():
            return False, ".mcp.json.template not found. Reinstall Amp or check that the template exists at the vault root."
        
        # Read example
        with open(MCP_CONFIG_EXAMPLE, 'r') as f:
            config_content = f.read()
        
        # Replace {{VAULT_PATH}} with actual path
        config_content = config_content.replace('{{VAULT_PATH}}', str(vault_path))
        
        # Validate JSON
        try:
            json.loads(config_content)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON after template substitution: {e}. Check .mcp.json.template for syntax errors."
        
        # Write to target
        atomic_write_text(MCP_CONFIG_TARGET, config_content)
        
        return True, None
    except (OSError, ValueError) as e:
        logger.warning("MCP config setup failed: %s", e)
        return False, str(e)

# ============================================================================
# PRE-ANALYSIS HELPER FUNCTIONS
# ============================================================================

def get_calendar_events_for_week() -> List[Dict]:
    """
    Get calendar events for the current week by importing and calling calendar MCP.
    Returns empty list if calendar not available.
    """
    try:
        # Import calendar server functions
        calendar_server_path = BASE_DIR / 'core' / 'mcp' / 'calendar_server.py'
        if not calendar_server_path.exists():
            logger.warning("calendar_server.py not found")
            return []
        
        # Dynamic import to avoid circular dependencies
        import importlib.util
        spec = importlib.util.spec_from_file_location("calendar_server", calendar_server_path)
        calendar_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(calendar_module)
        
        # Get this week's events
        from datetime import timedelta
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=7)
        
        events = calendar_module.get_events_for_range(start, end)
        return events if events else []
    except Exception as e:
        logger.warning(f"Failed to get calendar events: {e}")
        return []

def analyze_calendar_events(events: List[Dict]) -> Dict:
    """Analyze calendar events to extract insights"""
    if not events:
        return {}
    
    # Count meetings
    total = len(events)
    
    # Count 1:1s (events with 2 attendees)
    one_on_ones = sum(1 for e in events if len(e.get('attendees', [])) == 2)
    
    # Find busiest day
    day_counts = {}
    for event in events:
        day = event['start'].strftime('%A')
        day_counts[day] = day_counts.get(day, 0) + 1
    busiest_day = max(day_counts.items(), key=lambda x: x[1]) if day_counts else ('Unknown', 0)
    
    # Get frequent attendees (excluding self)
    attendee_counts = {}
    for event in events:
        for attendee in event.get('attendees', []):
            email = attendee.get('email', '')
            name = attendee.get('name', email)
            if email and name:
                attendee_counts[email] = attendee_counts.get(email, 0) + 1
    
    # Top 3 people
    top_people = sorted(attendee_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        'total_meetings': total,
        'one_on_ones': one_on_ones,
        'busiest_day': busiest_day[0],
        'busiest_day_count': busiest_day[1],
        'top_people': [{'email': email, 'count': count} for email, count in top_people]
    }

def generate_weekly_plan(events: List[Dict], pillars: List[str], role: str) -> str:
    """Generate weekly plan markdown content from calendar events"""
    from datetime import timedelta
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    content = f"""# Week Priorities - {week_start.strftime('%b %d')} to {week_end.strftime('%b %d, %Y')}

## This Week's Focus

Based on your calendar and pillars, here are suggested priorities:

"""
    
    # Add pillar-based priorities
    for i, pillar in enumerate(pillars[:3], 1):
        content += f"{i}. **{sanitize_markdown_input(pillar)}**: [Define specific outcome for this week]\n"
    
    content += f"\n## Meeting Overview\n\n"
    content += f"You have **{len(events)} meetings** scheduled this week.\n\n"
    
    # Group by day
    days = {}
    for event in events:
        day = event['start'].strftime('%A')
        if day not in days:
            days[day] = []
        days[day].append(event)
    
    content += "### Key Meetings\n\n"
    for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
        if day in days:
            content += f"**{day}** ({len(days[day])} meetings)\n"
            for event in days[day][:3]:  # Show first 3
                time = event['start'].strftime('%I:%M %p')
                content += f"- {time}: {sanitize_markdown_input(event['title'])}\n"
            if len(days[day]) > 3:
                content += f"- ... and {len(days[day]) - 3} more\n"
            content += "\n"
    
    content += """## Action Items

- [ ] Review and prep for key meetings
- [ ] Block focus time for deep work
- [ ] Check in on project progress

## Notes

*This plan was automatically generated during onboarding based on your calendar.*
"""
    
    return content

def write_weekly_plan(content: str) -> bool:
    """Write weekly plan to file"""
    try:
        week_priorities_dir = BASE_DIR / '02-Week_Priorities'
        week_priorities_dir.mkdir(parents=True, exist_ok=True)
        
        week_file = week_priorities_dir / 'Week_Priorities.md'
        week_file.write_text(content)
        return True
    except OSError as e:
        logger.error(f"Failed to write weekly plan: {e}")
        return False

def get_frequent_attendees(events: List[Dict], limit: int = 3) -> List[Dict]:
    """Get most frequent meeting attendees"""
    attendee_data = {}
    
    for event in events:
        for attendee in event.get('attendees', []):
            email = attendee.get('email', '')
            name = attendee.get('name', email)
            if email and name:
                if email not in attendee_data:
                    attendee_data[email] = {
                        'email': email,
                        'name': name,
                        'count': 0
                    }
                attendee_data[email]['count'] += 1
    
    # Sort by count and return top N
    sorted_attendees = sorted(attendee_data.values(), key=lambda x: x['count'], reverse=True)
    return sorted_attendees[:limit]

def create_person_page(contact: Dict, email_domain: str) -> bool:
    """Create a person page, routing to Internal or External based on email domain"""
    try:
        email = contact['email']
        name = contact['name']
        
        # Determine if internal or external
        contact_domain = email.split('@')[1] if '@' in email else ''
        is_internal = contact_domain in email_domain.split(',')
        
        # Create appropriate folder
        folder = 'Internal' if is_internal else 'External'
        people_dir = BASE_DIR / '05-Areas' / 'People' / folder
        people_dir.mkdir(parents=True, exist_ok=True)
        
        # Create person page
        safe_name = re.sub(r'[/\\<>:"|?*\x00-\x1f]', '', name).strip()
        safe_name = safe_name.replace(' ', '_')
        if not safe_name:
            return False
        person_file_name = safe_name + '.md'
        person_file = people_dir / person_file_name
        
        # Validate path stays within vault
        try:
            validate_vault_path(person_file, BASE_DIR)
        except ValueError:
            logger.warning(f"Path traversal blocked for person page: {name}")
            return False
        
        # Don't overwrite existing
        if person_file.exists():
            return False
        
        content = f"""# {sanitize_markdown_input(name)}

**Email:** {sanitize_markdown_input(email)}
**Type:** {'Internal' if is_internal else 'External'}

## Context

*Automatically created during onboarding as a frequent meeting contact*

## Meeting History

## Action Items

## Notes
"""
        
        person_file.write_text(content)
        return True
    except OSError as e:
        logger.error(f"Failed to create person page for {contact.get('name', 'unknown')}: {e}")
        return False

def get_recent_granola_meetings(days: int = 7) -> List[Dict]:
    """Deprecated: Granola removed from onboarding. Returns empty list for compatibility."""
    return []

def count_unique_people(meetings: List[Dict]) -> int:
    """Count unique people across meetings"""
    people = set()
    for meeting in meetings:
        for attendee in meeting.get('attendees', []):
            email = attendee.get('email', '')
            if email:
                people.add(email)
    return len(people)

def count_external_companies(meetings: List[Dict], email_domain: str) -> int:
    """Count unique external companies based on email domains"""
    internal_domains = set(d.strip() for d in email_domain.split(','))
    external_domains = set()
    
    for meeting in meetings:
        for attendee in meeting.get('attendees', []):
            email = attendee.get('email', '')
            if '@' in email:
                domain = email.split('@')[1]
                if domain not in internal_domains:
                    external_domains.add(domain)
    
    return len(external_domains)

# ============================================================================
# MCP SERVER SETUP
# ============================================================================

app = Server("amp-onboarding-mcp")

logger.info("Starting Amp Onboarding MCP Server")
logger.info(f"Vault path: {BASE_DIR}")

# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available onboarding tools"""
    return [
        types.Tool(
            name="start_onboarding_session",
            description="Initialize or resume an onboarding session. Returns session state with completed steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "force_new": {
                        "type": "boolean",
                        "description": "Force create a new session even if one exists",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="validate_and_save_step",
            description="Validate and save data for a specific onboarding step. Enforces validation rules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "step_number": {
                        "type": "integer",
                        "description": "Step number (1-4)",
                        "minimum": 1,
                        "maximum": 4
                    },
                    "step_data": {
                        "type": "object",
                        "description": "Data for the step (structure varies by step)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Fallback Step 1 field when the caller does not wrap values in step_data"
                    },
                    "role": {
                        "type": "string",
                        "description": "Fallback Step 2 role value"
                    },
                    "role_group": {
                        "type": "string",
                        "description": "Optional explicit role_group for Step 2"
                    },
                    "role_number": {
                        "type": "integer",
                        "description": "Optional preset role number for Step 2"
                    },
                    "email_domain": {
                        "type": "string",
                        "description": "Fallback Step 3 email domain value"
                    },
                    "communication": {
                        "type": "object",
                        "description": "Fallback Step 4 communication object"
                    },
                    "formality": {
                        "type": "string",
                        "description": "Optional Step 4 formality fallback"
                    },
                    "directness": {
                        "type": "string",
                        "description": "Optional Step 4 directness fallback"
                    },
                    "career_level": {
                        "type": "string",
                        "description": "Optional Step 4 career level fallback"
                    },
                    "coaching_style": {
                        "type": "string",
                        "description": "Optional Step 4 coaching style fallback"
                    },
                    "obsidian_mode": {
                        "type": "boolean",
                        "description": "Optional Obsidian mode flag"
                    }
                },
                "required": ["step_number"]
            }
        ),
        types.Tool(
            name="get_onboarding_status",
            description="Get current onboarding progress and completion status",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="verify_dependencies",
            description="Check system requirements: Python packages. Calendar.app is checked on macOS only (informational, not required).",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="finalize_onboarding",
            description="Complete onboarding: create vault structure, write configs, setup MCP. Requires all steps completed. Use dry_run=true to preview what would be created without making changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, show what would be created without actually creating anything. Used for QA testing.",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="complete_obsidian_walkthrough",
            description="Finish onboarding after the user confirms the vault is open in Obsidian. Creates the completion marker and clears the active onboarding session.",
            inputSchema={
                "type": "object",
                "properties": {
                    "vault_opened": {
                        "type": "boolean",
                        "description": "Whether the user confirmed the Amp root is open as an Obsidian vault.",
                        "default": True
                    }
                }
            }
        ),
        types.Tool(
            name="check_onboarding_complete",
            description="Check if onboarding is complete and get vault age. Returns completion status and days since setup.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="cleanup_qa_session",
            description="Delete the QA/test onboarding session file without affecting the real onboarding marker. Use after /qa-onboarding to clean up.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]

# ============================================================================
# TOOL HANDLERS
# ============================================================================

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls"""
    arguments = arguments or {}
    
    try:
        if name == "start_onboarding_session":
            force_new = arguments.get('force_new', False)
            
            session = load_session()
            
            if session and session.get('version') != ONBOARDING_VERSION:
                logger.info("Existing onboarding session uses an older flow, starting fresh")
                session = create_new_session()
                save_session(session)
                result = create_success_response(
                    session,
                    "Started a fresh onboarding session because the previous session used an older flow"
                )
            elif session and not force_new:
                result = create_success_response(
                    session,
                    f"Resuming onboarding session. Completed steps: {len(session['completed_steps'])}/{len(REQUIRED_STEPS)}"
                )
            else:
                if session and force_new:
                    logger.info("Creating new session (force_new=True)")
                
                session = create_new_session()
                save_session(session)
                result = create_success_response(
                    session,
                    "New onboarding session created"
                )
            
            return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]
        
        elif name == "validate_and_save_step":
            step_number = arguments.get('step_number')
            step_data = normalize_step_data(arguments)
            
            if not step_number or not isinstance(step_number, int):
                result = create_error_response("step_number should be an integer from 1 to 4.", suggestion="Provide step_number as an integer (1, 2, 3, or 4).")
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            session = load_session()
            if not session:
                result = create_error_response("No onboarding session in progress.", suggestion="Run start_onboarding_session first to begin setup.")
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            # Step 1: Name
            if step_number == 1:
                name_val = step_data.get('name', '').strip()
                if not name_val:
                    result = create_error_response(
                        "A name is needed to personalize your experience.",
                        step=1,
                        field="name",
                        suggestion="Provide your first name or preferred name."
                    )
                else:
                    session['data']['name'] = name_val
                    if step_number not in session['completed_steps']:
                        session['completed_steps'].append(step_number)
                    session['current_step'] = 2
                    save_session(session)
                    result = create_success_response({"step": 1, "completed": True}, "Step 1 complete")
            
            # Step 2: Role
            elif step_number == 2:
                role = step_data.get('role', '').strip()
                role_number = step_data.get('role_number')
                
                if role_number and isinstance(role_number, int) and role_number in ROLES:
                    role, role_group = ROLES[role_number]
                    session['data']['role'] = role
                    session['data']['role_group'] = role_group
                elif role:
                    session['data']['role'] = role
                    session['data']['role_group'] = step_data.get('role_group') or infer_role_group(role)
                else:
                    result = create_error_response(
                        "A role is needed so Amp can tailor suggestions to your work.",
                        step=2,
                        field="role",
                        suggestion="Describe your role in a few words (e.g., 'Product Manager', 'Engineering Lead')."
                    )
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                if step_number not in session['completed_steps']:
                    session['completed_steps'].append(step_number)
                session['current_step'] = 3
                save_session(session)
                result = create_success_response({"step": 2, "completed": True}, "Step 2 complete")
            
            # Step 3: Email Domain (CRITICAL)
            elif step_number == 3:
                email_domain = step_data.get('email_domain', '').strip()
                
                valid, error_msg = validate_email_domain(email_domain)
                if not valid:
                    result = create_error_response(
                        error_msg,
                        step=3,
                        field="email_domain",
                        suggestion="Provide domain without @ (e.g., 'pendo.io' or 'acme.com')"
                    )
                else:
                    session['data']['email_domain'] = email_domain
                    if step_number not in session['completed_steps']:
                        session['completed_steps'].append(step_number)
                    session['current_step'] = 4
                    save_session(session)
                    result = create_success_response(
                        {"step": 3, "completed": True, "email_domain": email_domain},
                        "Step 3 complete, email domain validated"
                    )
            
            # Step 4: Communication Preferences + optional Obsidian Mode
            elif step_number == 4:
                comm = step_data.get('communication', {})
                if not isinstance(comm, dict):
                    comm = {}
                
                formality = comm.get('formality', 'professional_casual')
                directness = comm.get('directness', 'balanced')
                career_level = comm.get('career_level')
                coaching_style = comm.get('coaching_style')
                
                # Obsidian mode is optional, default to false
                obsidian_mode = step_data.get('obsidian_mode', False)
                
                # Validate enums
                if formality not in FORMALITY_LEVELS:
                    result = create_error_response(
                        f"'{formality}' isn't a recognized formality level.",
                        step=4,
                        field="formality",
                        suggestion=f"Choose one of: {', '.join(FORMALITY_LEVELS)}"
                    )
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                if directness not in DIRECTNESS_LEVELS:
                    result = create_error_response(
                        f"'{directness}' isn't a recognized directness level.",
                        step=4,
                        field="directness",
                        suggestion=f"Choose one of: {', '.join(DIRECTNESS_LEVELS)}"
                    )
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                if career_level and career_level not in CAREER_LEVELS:
                    result = create_error_response(
                        f"'{career_level}' isn't a recognized career level.",
                        step=4,
                        field="career_level",
                        suggestion=f"Choose one of: {', '.join(CAREER_LEVELS)}"
                    )
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                coaching_style_map = {
                    'junior': 'encouraging',
                    'mid': 'collaborative',
                    'senior': 'challenging',
                    'leadership': 'challenging',
                    'c_suite': 'challenging'
                }
                if career_level:
                    coaching_style = coaching_style or coaching_style_map.get(career_level, 'collaborative')
                else:
                    career_level = 'mid'
                    coaching_style = coaching_style or 'collaborative'

                if coaching_style not in COACHING_STYLES:
                    result = create_error_response(
                        f"'{coaching_style}' isn't a recognized coaching style.",
                        step=4,
                        field="coaching_style",
                        suggestion=f"Choose one of: {', '.join(COACHING_STYLES)}"
                    )
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                session['data']['communication'] = {
                    'formality': formality,
                    'directness': directness,
                    'career_level': career_level,
                    'coaching_style': coaching_style
                }
                
                # Save obsidian_mode preference
                session['data']['obsidian_mode'] = obsidian_mode
                
                if step_number not in session['completed_steps']:
                    session['completed_steps'].append(step_number)
                session['current_step'] = 5
                save_session(session)
                result = create_success_response({"step": 4, "completed": True}, "Step 4 complete")
            
            else:
                result = create_error_response(f"Step {step_number} is out of range.", suggestion="Step must be 1 through 4.")
            
            return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]
        
        elif name == "get_onboarding_status":
            session = load_session()
            
            if not session:
                result = create_error_response("No onboarding session in progress.", suggestion="Run start_onboarding_session to begin setup.")
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            required_steps = list(REQUIRED_STEPS.keys())
            completed = session['completed_steps']
            missing = [s for s in required_steps if s not in completed]

            progress = len(completed) / len(required_steps) * 100
            
            status = {
                "completed_steps": completed,
                "missing_steps": missing,
                "missing_step_names": [REQUIRED_STEPS[s] for s in missing],
                "current_step": session['current_step'],
                "progress_percent": round(progress, 1),
                "ready_to_finalize": len(missing) == 0,
                "awaiting_obsidian_walkthrough": session.get('workspace_created', False) and session.get('current_step') == 6,
                "session_data": session['data']
            }
            
            result = create_success_response(status)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]
        
        elif name == "verify_dependencies":
            deps = {
                "python_packages": check_python_packages(),
                "calendar_app": check_calendar_app(),
            }
            
            # Check if all required packages installed
            packages = deps['python_packages']
            all_installed = all(p.get('installed', False) for p in packages.values())
            
            missing = [pkg for pkg, info in packages.items() if not info.get('installed')]
            
            instructions = ""
            if missing:
                instructions = f"Install missing packages:\n  pip install -r {BASE_DIR}/requirements.txt"
            
            result = create_success_response({
                "dependencies": deps,
                "all_required_installed": all_installed,
                "missing_packages": missing,
                "installation_instructions": instructions
            })
            
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "finalize_onboarding":
            dry_run = arguments.get('dry_run', False)
            session = load_session()

            if not session:
                result = create_error_response("No onboarding session in progress.", suggestion="Run start_onboarding_session first to begin setup.")
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            # Verify all required steps completed
            required_steps = list(REQUIRED_STEPS.keys())
            completed = session['completed_steps']
            missing = [s for s in required_steps if s not in completed]

            if missing:
                result = create_error_response(
                    f"Can't finalize yet. Steps {missing} still need to be completed.",
                    suggestion=f"Complete these first: {', '.join(REQUIRED_STEPS[s] for s in missing)}"
                )
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            # Critical check for Step 3
            if 3 not in completed or not session['data'].get('email_domain'):
                result = create_error_response(
                    "Email domain is required before finalizing. This is how Amp sorts internal vs. external contacts.",
                    step=3,
                    field="email_domain",
                    suggestion="Go back to Step 3 and provide your company email domain (e.g., 'acme.com')."
                )
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            # ---- DRY RUN MODE ----
            if dry_run:
                logger.info("Finalize (DRY RUN) - previewing what would be created")

                # Compute folders that would be created
                para_folders = [
                    "04-Projects", "05-Areas/People/Internal", "05-Areas/People/External",
                    "05-Areas/Companies", "00-Inbox/Meetings", "00-Inbox/Ideas",
                    "00-Inbox/Plans", "00-Inbox/Drop_Zone",
                    "06-Resources/Learnings", "06-Resources/Quarterly_Reviews",
                    "07-Archives/04-Projects", "07-Archives/Plans", "07-Archives/Reviews",
                    "System/Templates", "01-Quarter_Goals", "03-Tasks", "02-Week_Priorities"
                ]
                would_create_folders = [f for f in para_folders if not (BASE_DIR / f).exists()]
                already_exist_folders = [f for f in para_folders if (BASE_DIR / f).exists()]

                # Compute files that would be created
                would_create_files = []
                already_exist_files = []

                tasks_file = BASE_DIR / '03-Tasks' / 'Tasks.md'
                if not tasks_file.exists():
                    would_create_files.append('03-Tasks/Tasks.md')
                else:
                    already_exist_files.append('03-Tasks/Tasks.md')

                priorities_file = BASE_DIR / '02-Week_Priorities' / 'Week_Priorities.md'
                if not priorities_file.exists():
                    would_create_files.append('02-Week_Priorities/Week_Priorities.md')
                else:
                    already_exist_files.append('02-Week_Priorities/Week_Priorities.md')

                would_create_files.append('System/user-profile.yaml')
                would_create_files.append('System/pillars.yaml')

                # Configs that would be updated
                would_update_configs = ['CLAUDE.md (User Profile section)']
                if MCP_CONFIG_EXAMPLE.exists():
                    would_update_configs.append('.mcp.json')

                # Build preview of user-profile.yaml content
                data = session['data']
                profile_preview = {
                    'name': data.get('name', ''),
                    'role': data.get('role', ''),
                    'role_group': data.get('role_group', ''),
                    'company': data.get('company', ''),
                    'company_size': data.get('company_size', ''),
                    'email_domain': data.get('email_domain', ''),
                    'obsidian_mode': data.get('obsidian_mode', False),
                    'communication': data.get('communication', {})
                }

                # Build preview of pillars.yaml content
                pillars_preview, pillars_configured = build_pillar_entries(data.get('pillars', []))

                # Completion marker preview
                marker_preview = {
                    'completed_at': '(timestamp)',
                    'user_name': data.get('name', ''),
                    'role': data.get('role', ''),
                    'email_domain': data.get('email_domain', ''),
                    'has_pillars': pillars_configured,
                    'phase2_completed': False,
                    'pre_analysis_deferred': True
                }

                dry_run_summary = {
                    'dry_run': True,
                    'validation_passed': True,
                    'would_create_folders': would_create_folders,
                    'already_exist_folders': already_exist_folders,
                    'would_create_files': would_create_files,
                    'already_exist_files': already_exist_files,
                    'would_update_configs': would_update_configs,
                    'would_create_completion_marker_after_obsidian_walkthrough': marker_preview,
                    'would_delete_session_after_obsidian_walkthrough': True,
                    'preview_user_profile': profile_preview,
                    'preview_pillars': pillars_preview,
                    'session_data_snapshot': data
                }

                result = create_success_response(
                    dry_run_summary,
                    f"DRY RUN: Would create {len(would_create_folders)} folders, {len(would_create_files)} files, update {len(would_update_configs)} configs. No changes made."
                )
                return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]

            # ---- REAL FINALIZATION ----
            # Execute finalization steps
            summary = {
                "folders_created": [],
                "files_created": [],
                "configs_updated": [],
                "errors": []
            }

            try:
                created_artifacts = []

                # 1. Create PARA structure
                logger.info("Creating PARA folder structure")
                folders = create_para_structure(BASE_DIR)
                for folder in folders:
                    created_artifacts.append(BASE_DIR / folder)
                summary['folders_created'] = folders

                # 2. Create initial files
                logger.info("Creating initial files")
                files = create_initial_files(BASE_DIR, session)
                for f_rel in files:
                    created_artifacts.append(BASE_DIR / f_rel)
                summary['files_created'].extend(files)

                # 3. Create user-profile.yaml
                logger.info("Creating user-profile.yaml")
                if yaml and create_user_profile(session):
                    created_artifacts.append(USER_PROFILE_FILE)
                    summary['files_created'].append('System/user-profile.yaml')
                else:
                    summary['errors'].append("Could not create user-profile.yaml")

                # 4. Create pillars.yaml
                logger.info("Creating pillars.yaml")
                if yaml and create_pillars_file(session['data'].get('pillars', [])):
                    created_artifacts.append(PILLARS_FILE)
                    summary['files_created'].append('System/pillars.yaml')
                else:
                    summary['errors'].append("Could not create pillars.yaml")

                # 5. Update CLAUDE.md
                logger.info("Updating CLAUDE.md")
                if update_claude_md(session):
                    summary['configs_updated'].append('CLAUDE.md')
                else:
                    summary['errors'].append("Could not update CLAUDE.md")

                # 6. Setup MCP config
                logger.info("Setting up .mcp.json")
                success, error = setup_mcp_config(BASE_DIR)
                if success:
                    created_artifacts.append(MCP_CONFIG_TARGET)
                    summary['configs_updated'].append('.mcp.json')
                else:
                    summary['errors'].append(f"MCP config error: {error}")
                    result = create_error_response(
                        f"Could not create .mcp.json: {error}. Finalization stopped.",
                        suggestion="Make sure .mcp.json.template exists at the vault root, then rerun finalize_onboarding."
                    )
                    result["data"] = summary
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]

                # 7. Persist onboarding state so Step 6 can resume cleanly
                session['current_step'] = 6
                session['workspace_created'] = True
                session['workspace_created_at'] = datetime.now().isoformat()
                session['finalization_summary'] = summary
                if not save_session(session):
                    summary['errors'].append("Could not save onboarding session after workspace creation")
                    result = create_error_response(
                        "Workspace was created, but the session state could not be saved. The Obsidian walkthrough can't proceed.",
                        suggestion="Rerun /setup to resume the required Obsidian walkthrough before completing onboarding."
                    )
                    result["data"] = summary
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]

                result = create_success_response(
                    {
                        **summary,
                        "next_step": "Open the Amp root in Obsidian, then call complete_obsidian_walkthrough to finish onboarding."
                    },
                    f"Workspace created. Open the Amp root in Obsidian, then finish onboarding with the required walkthrough confirmation."
                )
                
            except Exception as e:
                logger.error(f"Error during finalization: {e}")
                # Rollback: remove created artifacts in reverse order
                for artifact in reversed(created_artifacts):
                    try:
                        artifact = Path(artifact)
                        if artifact.is_file():
                            artifact.unlink()
                        elif artifact.is_dir():
                            shutil.rmtree(artifact, ignore_errors=True)
                    except OSError:
                        pass
                result = create_error_response(
                    f"Finalization failed and changes were rolled back: {e}",
                    suggestion="Check the error above, fix the issue, and try finalize_onboarding again."
                )
            
            return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]

        elif name == "complete_obsidian_walkthrough":
            vault_opened = arguments.get('vault_opened', True)

            if not vault_opened:
                result = create_error_response(
                    "The Obsidian walkthrough hasn't been confirmed yet.",
                    suggestion="Open the Amp repo root as an Obsidian vault, then call complete_obsidian_walkthrough again."
                )
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            session = load_session()
            if not session:
                if MARKER_FILE.exists():
                    result = create_success_response(
                        {"already_complete": True},
                        "Onboarding is already complete"
                    )
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

                result = create_error_response(
                    "No onboarding session found.",
                    suggestion="Run start_onboarding_session first, or rerun /setup to start over."
                )
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            if session.get('current_step') != 6 or not session.get('workspace_created'):
                result = create_error_response(
                    "The workspace hasn't been finalized yet. That needs to happen before the Obsidian walkthrough.",
                    suggestion="Run finalize_onboarding first, then come back to complete the walkthrough."
                )
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            logger.info("Creating completion marker after Obsidian walkthrough")
            marker_data = build_completion_marker(session)
            atomic_write_text(MARKER_FILE, json.dumps(marker_data, indent=2, cls=DateTimeEncoder))

            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
                logger.info("Deleted session file")

            result = create_success_response(
                {
                    "completed": True,
                    "marker_file": str(MARKER_FILE),
                    "summary": session.get('finalization_summary', {})
                },
                "Onboarding complete"
            )
            try:
                _fire_analytics_event('onboarding_completed')
            except Exception as e:
                logger.debug("Analytics event failed: %s", e)
            if not MARKER_FILE.exists():
                session = load_session()
                if session and session.get('workspace_created') and session.get('current_step') == 6:
                    result = create_success_response({
                        "complete": False,
                        "is_new_vault": False,
                        "awaiting_obsidian_walkthrough": True,
                        "user_name": session.get('data', {}).get('name', ''),
                        "role": session.get('data', {}).get('role', '')
                    })
                else:
                    result = create_success_response({
                        "complete": False,
                        "is_new_vault": False
                    })
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            try:
                marker_data = json.loads(MARKER_FILE.read_text())
                completed_at = datetime.fromisoformat(marker_data['completed_at'])
                age_days = (datetime.now() - completed_at).days
                
                result = create_success_response({
                    "complete": True,
                    "age_days": age_days,
                    "is_new_vault": age_days <= 7,
                    "phase2_completed": marker_data.get('phase2_completed', False),
                    "user_name": marker_data.get('user_name', ''),
                    "role": marker_data.get('role', '')
                })
            except (OSError, json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(f"Error reading marker file: {e}")
                result = create_error_response(f"Could not read the onboarding completion marker: {e}. Try rerunning /setup.")
            
            return [types.TextContent(type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder))]
        
        elif name == "cleanup_qa_session":
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
                result = create_success_response(
                    {"session_deleted": True},
                    "QA session cleaned up. Session file deleted."
                )
            else:
                result = create_success_response(
                    {"session_deleted": False},
                    "No session file to clean up."
                )
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            result = create_error_response(f"'{name}' is not a recognized onboarding tool. Available tools: start_onboarding_session, validate_and_save_step, get_onboarding_status, finalize_onboarding, complete_obsidian_walkthrough.")
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    
    except Exception as e:
        if _HAS_HEALTH:
            _log_health_error(
                source="onboarding-mcp",
                message=str(e),
                human_message=f"Onboarding step '{name}' hit an error. Try again or rerun /setup.",
                context={"tool": name}
            )
        logger.error(f"Error handling {name}: {e}")
        result = create_error_response(f"Something went wrong: {e}. Try the operation again. If it keeps failing, check the logs.")
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def _main():
    """Main entry point for the MCP server"""
    if _HAS_HEALTH:
        _mark_healthy("onboarding-mcp")
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="amp-onboarding-mcp",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

def main():
    """Entry point wrapper"""
    import asyncio
    asyncio.run(_main())

if __name__ == "__main__":
    main()
