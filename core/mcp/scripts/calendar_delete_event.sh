#!/bin/bash
# Delete a calendar event using AppleScript
# Usage: calendar_delete_event.sh <calendar> <title> <day_offset>

CALENDAR="$1"
TITLE="$2"
DAY_OFFSET="$3"

# Escape backslashes and double quotes for safe AppleScript interpolation
# Note: Single quotes are safe inside AppleScript double-quoted strings
# Only backslashes and double quotes need escaping
CALENDAR="${CALENDAR//\\/\\\\}"
CALENDAR="${CALENDAR//\"/\\\"}"
TITLE="${TITLE//\\/\\\\}"
TITLE="${TITLE//\"/\\\"}"

osascript <<EOF
tell application "Calendar"
    set targetDate to (current date) + ($DAY_OFFSET * days)
    set startOfDay to targetDate
    set time of startOfDay to 0
    set endOfDay to startOfDay + (1 * days)
    
    tell calendar "$CALENDAR"
        set matchingEvents to (every event whose summary is "$TITLE" and start date >= startOfDay and start date < endOfDay)
        if (count of matchingEvents) > 0 then
            delete item 1 of matchingEvents
            return "Deleted: $TITLE"
        else
            error "Event not found: $TITLE on target date"
        end if
    end tell
end tell
EOF
