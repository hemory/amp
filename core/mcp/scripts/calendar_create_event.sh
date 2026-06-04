#!/bin/bash
# Create a calendar event using AppleScript
# Usage: calendar_create_event.sh <calendar> <title> <start_datetime> <duration_min> [description] [location]

CALENDAR="$1"
TITLE="$2"
START="$3"
DURATION="$4"
DESCRIPTION="${5:-}"
LOCATION="${6:-}"

# Escape backslashes and double quotes for safe AppleScript interpolation
# Note: Single quotes are safe inside AppleScript double-quoted strings
# Only backslashes and double quotes need escaping
CALENDAR="${CALENDAR//\\/\\\\}"
CALENDAR="${CALENDAR//\"/\\\"}"
TITLE="${TITLE//\\/\\\\}"
TITLE="${TITLE//\"/\\\"}"
DESCRIPTION="${DESCRIPTION//\\/\\\\}"
DESCRIPTION="${DESCRIPTION//\"/\\\"}"
LOCATION="${LOCATION//\\/\\\\}"
LOCATION="${LOCATION//\"/\\\"}"

osascript <<EOF
tell application "Calendar"
    tell calendar "$CALENDAR"
        set startDate to date "$START"
        set endDate to startDate + ($DURATION * 60)
        set newEvent to make new event with properties {summary:"$TITLE", start date:startDate, end date:endDate}
        if "$DESCRIPTION" is not "" then
            set description of newEvent to "$DESCRIPTION"
        end if
        if "$LOCATION" is not "" then
            set location of newEvent to "$LOCATION"
        end if
    end tell
end tell
return "Event created: $TITLE"
EOF
