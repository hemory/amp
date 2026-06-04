# Amp System Improvement Backlog

This file is a starter backlog for product or workflow improvements. It should contain generic examples only. User-specific ideas belong in the user's local vault and should not be committed to the product repo.

## How It Works

1. Capture ideas when Amp or the user notices a concrete workflow gap.
2. Review ideas with `/amp-backlog`.
3. Workshop promising ideas with `/amp-improve`.
4. Mark implemented ideas when they ship.

Ideas are ranked by:

- **Impact:** How much the idea improves the user's daily workflow.
- **Alignment:** How well it fits the user's stated workflows.
- **Token efficiency:** Whether it reduces unnecessary reading or context loading.
- **Memory and learning:** Whether Amp gets more useful over time.
- **Proactivity:** Whether Amp can surface useful next actions earlier.

## Example Ideas

### High Priority

- **[idea-001]** Save meeting summaries so Amp does not reread entire notes every time.
  - **Problem:** Follow-up prep can require reading long historical notes.
  - **Solution:** Store short structured summaries in a meeting cache.
  - **Benefit:** Faster context gathering with less token usage.

### Medium Priority

- **[idea-002]** Maintain a lightweight people index.
  - **Problem:** Simple people lookups can require scanning many person pages.
  - **Solution:** Keep `System/People_Index.json` updated with names, roles, companies, and last interaction dates.
  - **Benefit:** Faster lookups while preserving full detail in person pages.

### Low Priority

- Add your own ideas here after setup.
