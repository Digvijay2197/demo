# Week 9 Task Set B -- Requirement 5
## Before/after transcript: docstring-as-prompt + recoverable error rewrite

### The failing call

User query: "What allergens does creme fraiche lite have?"

The ingredient database contains "creme fraiche" but not "creme fraiche lite".

---

### BEFORE -- old docstring (unhelpful, opaque error)

**Old docstring on `lookup_ingredient` (hypothetical pre-rewrite version):**
```
Look up one ingredient by name and return its data.
Pass the exact ingredient name. Returns error code 3 if not found.
```

**BEFORE transcript (model turn 1 -- tool call):**
```
Tool: lookup_ingredient
Args: {"name": "creme fraiche lite"}
```

**BEFORE server response:**
```json
{"error": "Error 3"}
```

**BEFORE model turn 2 -- final answer (model invents data, cannot recover):**
> I'm sorry, I wasn't able to find allergen information for creme fraiche lite.
> Creme fraiche is typically a dairy product, so it likely contains dairy allergens,
> but I cannot confirm the exact allergen profile from my database.

**Problem:** "Error 3" tells the model nothing about what went wrong or how to
fix it. The model falls back to hallucinating allergen data -- exactly what the
system is supposed to prevent.

---

### AFTER -- new docstring + recoverable error (current ingredient_server.py)

**New docstring on `lookup_ingredient` (current code):**
```
Look up one ingredient by name and return its allergen classes plus
nutrition per 100g (kcal, protein_g, fat_g, carbs_g). This is a database
lookup, not a search -- pass the ingredient exactly as it appears in a
recipe (e.g. "whole milk", not "milk products"). If the name is not on
file, the error names the closest known ingredient so you can retry with
that exact name instead of guessing its nutrition or allergens.
```

The error path in the code:
```python
close = difflib.get_close_matches(key, INGREDIENTS.keys(), n=1, cutoff=0.5)
if close:
    return {"error": f"no ingredient matched {name!r}: try {close[0]!r}"}
```

**AFTER transcript (model turn 1 -- tool call):**
```
Tool: lookup_ingredient
Args: {"name": "creme fraiche lite"}
```

**AFTER server response:**
```json
{"error": "no ingredient matched 'creme fraiche lite': try 'creme fraiche'"}
```

**AFTER model turn 2 -- tool call (model retries with corrected name):**
```
Tool: lookup_ingredient
Args: {"name": "creme fraiche"}
```

**AFTER server response (turn 2):**
```json
{
  "name": "creme fraiche",
  "allergens": ["dairy"],
  "per_100g": {"kcal": 292, "protein_g": 2.4, "fat_g": 30.0, "carbs_g": 3.0}
}
```

**AFTER model turn 3 -- final answer:**
> Creme fraiche contains **dairy** allergens.
> Per 100g: 292 kcal, 2.4g protein, 30.0g fat, 3.0g carbs.
> Note: your database uses the spelling "creme fraiche" (without "lite").

---

### What changed and why it matters

| Aspect | Before | After |
|--------|--------|-------|
| Docstring | Terse, no usage guidance | Prompt-style: when to call, how to format input, what error means |
| Error message | "Error 3" (opaque) | "no ingredient matched 'X': try 'Y'" (actionable) |
| Model behaviour | Hallucinates allergens | Retries with corrected name, gets real data |
| Tool calls | 1 (fails silently) | 2 (fail + recover) |

The docstring IS the prompt the model reads before deciding how to call the
tool -- there is no separate "prompt" the developer writes.  The recoverable
error message is the payload the model receives as the tool result, which its
system prompt instructs it to act on: "call a tool again if its result suggests
a corrected name to retry with."
