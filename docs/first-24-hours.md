# Your First 24 Hours with Amp

This is not a feature tour. This is one day with your AI [Chief of Staff](glossary.md#amp), start to finish.

By the end of these 24 hours, you will have a working system: a plan, context flowing, chaos captured, and a review loop that compounds over time.

## Before You Start: Feed the System

Your [daily plan](glossary.md#daily-plan) will be empty without context. Amp needs to know what you are working on.

**Spend 15-20 minutes on this. It pays off immediately.**

1. **Add your current tasks** to `03-Tasks/Tasks.md`. Open it in Obsidian and list what is on your plate right now. Use the priority buckets (P0 through P3) to rank them.

2. **Create project folders** in `04-Projects/` for your active work. Even a simple folder with a one-page overview is enough. Amp uses these to connect your tasks, meetings, and notes to the right context.

3. **Drop any reference material** into the relevant project folders or `06-Resources/`. Links, docs, screenshots, slides. Whatever you have been using to do your work. The more context Amp has, the better it plans.

4. **Review optional identity templates** in `System/identity/` if you want Amp to have stable voice or operating principles. Keep them generic until you are ready to add user-declared preferences.

5. **Set up calendar integration** (optional but recommended). Run `/calendar-setup` to connect your calendar. This lets your daily plan include meetings and prep suggestions. Options: Apple Calendar (direct), Apple Calendar via EventKit, Google Calendar, or skip for now.

Once you have context in the system, the [Chief of Staff Loop](glossary.md#chief-of-staff-loop) starts working.

## Morning: Pull the Plan

Run `/daily-plan`.

Amp looks at your tasks, calendar, priorities, and recent context. It generates a plan for the day, not a generic to-do list, but a grounded view of what matters today.

Your daily plan also creates a [drop zone](glossary.md#drop-zone) document in Obsidian. More on that in a moment.

## Before a Meeting: Gather the Context

Pick your next meeting and run `/meeting-prep`.

Amp pulls together everything relevant: who is attending, what you discussed last time, open action items, and related project context. Instead of scrambling to remember where things left off, you walk in prepared.

After the meeting, paste your notes into the drop zone or run `/process-meetings` if you use Granola.

## Throughout the Day: Capture the Chaos

This is where the [drop zone](glossary.md#drop-zone) earns its keep.

Your daily plan opened a drop zone document in Obsidian. Throughout the day, use it:

- Paste a Slack message you need to follow up on
- Drop a screenshot of something worth noting
- Jot down a quick thought or idea
- Save a link you will need later

Do not worry about organizing any of it. Just dump it.

When you are ready, tell Amp to "check my drop zone" or run `/capture`. Amp reads the document, routes items to the right places ([person pages](glossary.md#person-page), projects, tasks), and confirms what was processed.

The point: stay in flow. Trust that nothing is lost.

## End of Day: Close the Loop

Run `/daily-review`.

Amp checks for unprocessed drop zone items, compares what you planned vs. what actually happened, surfaces meeting follow-ups, and asks about learnings worth capturing. This is where the system starts compounding. Tomorrow's daily plan will be smarter because of what you captured today.

For meaningful sessions, Amp can write a compact summary to `System/Session_Learnings/` and important durable events to `System/Memory/episodic-index.jsonl`. Keep these entries factual and free of secrets.

## Next Morning: See It Compound

Run `/daily-plan` again.

Notice the difference. Yesterday's context flows into today's plan. Tasks that carried over are surfaced. Meeting follow-ups are queued. The system remembers what you told it.

This is the [Chief of Staff Loop](glossary.md#chief-of-staff-loop):

1. **Pull the plan** — Start grounded, not guessing
2. **Gather the context** — Walk into meetings prepared
3. **Prep the repeatable work** — Let Amp handle the drafts and summaries
4. **Capture the chaos** — Drop zone catches everything without breaking flow
5. **Come back as the decision-maker** — Spend your energy on judgment, not logistics

## What to Explore Next

Once the loop is running, try these:

- `/process-meetings` — Auto-process meeting notes into [person pages](glossary.md#person-page) and tasks
- `/week-plan` — Set weekly priorities that feed into daily plans
- `/quarter-plan` — Define strategic goals for the quarter
- `/amp-level-up` — Discover [skills](glossary.md#skill) you have not tried yet

See [Glossary](glossary.md) for key terms and [Troubleshooting](troubleshooting.md) if something is not working.
