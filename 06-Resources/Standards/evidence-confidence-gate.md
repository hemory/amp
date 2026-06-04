# Evidence and Confidence Gate

Use this gate when Amp produces factual research, recommendations, audits, system changes, external-facing drafts, leadership content, or reusable artifacts. The goal is simple: no confident-looking output without a verified source chain.

## Source hierarchy

Prefer sources in this order:

1. Primary source or repository content: linked documents, issues, PRs, commits, files, calendar events, messages, docs, or direct user input.
2. Vault context: project docs, person pages, meeting notes, task files, standards, system docs, and session learnings.
3. Durable memory: `System/Memory/episodic-index.jsonl`, `System/Agent_Learnings/`, and local memories, only when relevant and not contradicted by files.
4. General model knowledge: use only for framing, background, or clearly labeled inference.

If a higher-quality source should exist but is unavailable, say what is missing before filling the gap.

## Verification checklist

Before presenting high-stakes or reusable work, check:

- Quotes are exact or explicitly labeled as paraphrases.
- Metrics include source and context.
- Issue, PR, discussion, and commit references resolve or are labeled unverified.
- File paths and named artifacts exist when they are in the vault or repo.
- External links are correctly formed and checked when they are load-bearing and access is available.
- Claims about people, org processes, ladders, decisions, or commitments trace to an accessible source.
- Assumptions are labeled, not presented as facts.

## Evidence notes

Use a short evidence note when the work is research-heavy, factual, high-stakes, or likely to be reused:

```markdown
**Verified:** ...
**Not verified:** ...
**Assumptions:** ...
```

Skip this note for routine proofreading, simple rewrites, and low-stakes confirmations.

## Confidence language

Use direct language when the source chain is strong. Use explicit uncertainty when it is not:

- "Verified in ..." when the source is accessible and checked.
- "I could not verify ..." when the source is missing, inaccessible, or ambiguous.
- "Inferring from ..." when connecting evidence into a judgment.
- "I do not know" when the answer would require invention.

Confidence without sourcing is not confidence. It is invention.
