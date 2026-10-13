# Top-3 known weaknesses — written 2026-10-12, before the first full eval run finished

> Written from reading my own code, *before* looking at any suite result, so these are predictions the eval can
> embarrass. The brief wants them dated Wednesday and unprompted; I am dating them when they were actually written.
> Re-check each against [`eval_report.md`](eval_report.md) — "what the eval later showed" is added at the bottom.

1. **No grounding gate: "not in the library" depends on the model, not on a score.**
   Retrieval always returns the nearest four recipes. For "how do I make beef wellington" the top hit is the beef
   meatballs at similarity 0.36 — barely lower than a real match (0.40–0.60 for genuine dish queries). I did *not* add a
   threshold because on this corpus the genuine and non-genuine ranges overlap, and I can't tune one honestly with 30
   cases. So refusal is only as good as the model's reading of the hit list, and I expect it to occasionally "helpfully"
   answer with the nearest recipe. Cases c27/c30 are the probe.

2. **Every question is stateless — an allergy stated earlier is forgotten.**
   "My daughter is allergic to tree nuts" in message 1, "can she have the shortbread?" in message 3: the allergen
   parser only sees the current question, so `avoid` is empty, the guard has nothing to enforce, and the model has no
   memory either. This is the most realistic way a real family hits the exact failure the client fears. Not built;
   not covered by any eval case (see "does not cover" in the report).

3. **The deterministic allergen parser and the PII redactor are regexes, and I know both leak.**
   `extract_avoid` needs a cue word ("allergic to", "…-free", "avoid"); it misses "she can't tolerate walnuts",
   "carries an EpiPen", "reacts to peanuts". When it misses, the guards enforce nothing for that question.
   `redact` strips `my <relation> <Name>`, ages, emails, phones, `named X` — but a bare first name ("is this ok for
   Priya?") or a free-text diagnosis passes through into the trace log. Health data in logs is the failure; regex
   redaction reduces it, it does not close it.

Also known, lower priority: single stdio MCP session serialises tool calls (see `tenx.md`); cold start ~1 min; the
"original" version is only offered when the user's words contain a cue ("original", "before", "old"); the
substitution table is tiny (11 ingredients) so "no safe swap exists" is common and untested for helpfulness.
