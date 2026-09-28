<!-- Soft Suave · The AI Engineering League -->
# Week 10 bonus — AgentCard and the A2A task lifecycle

## The AgentCard the orchestrator would advertise

An A2A AgentCard is what `agent/orchestrator.py` would publish at
`/.well-known/agent.json` if it were exposed as a standalone A2A server
instead of an in-process function call — the same three hand-offs
(nutrition/allergen worker, substitution worker, synthesis), just described
for a caller who has never read this codebase:

```json
{
  "name": "recipe-adaptation-orchestrator",
  "description": "Adapts a recipe to a target serving count and removes every banned allergen class, delegating nutrition lookup/scaling and ingredient substitution to two internal workers and synthesising one adapted method.",
  "url": "https://recipes.example.internal/a2a/orchestrator",
  "version": "1.0.0",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["application/json"],
  "authentication": {
    "schemes": ["bearer"]
  },
  "skills": [
    {
      "id": "adapt-recipe",
      "name": "Adapt recipe for allergies and serving count",
      "description": "Given a recipe query, a target serving count, and a list of allergen classes to avoid, returns a scaled, fully substituted ingredient list, the substitutions made, and an adapted method.",
      "tags": ["recipes", "allergens", "nutrition", "multi-agent"],
      "examples": [
        "adapt classic pancakes to 8 servings avoiding dairy and gluten"
      ],
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    }
  ]
}
```

The `skills` array is deliberately ONE skill, not three — a caller integrates
against "adapt a recipe," never against "call the nutrition worker" or "call
the substitution worker." The internal hand-offs this whole race is about are
an implementation detail the AgentCard does not expose, same as a REST
client never sees that a monolith's handler internally calls two other
functions.

## The injected failure, mapped onto the A2A task lifecycle

A2A tasks move through a fixed state machine: `submitted -> working ->
{completed | failed | canceled | input-required | auth-required}`.

**This case (`r05_curry4`, the nutrition/allergen worker's `get_nutrition`
returning a persistent simulated HTTP 500) should end in `failed`, not pause
at `input-required`.**

The distinction that decides it: `input-required` means the task cannot
proceed *because the agent is missing something only the user can supply* —
an ambiguous or absent allergy list, a serving count the user never gave, a
clarification the model genuinely needs. `failed` means the task cannot
proceed *because something the agent depends on broke*, and no amount of
user input fixes it. Our injected 500 is the second kind: the allergen list
was already fully specified in the request (`avoid=["shellfish"]`) — nothing
about the user's ask was unclear. Re-prompting the user for their allergy
list would not un-break `get_nutrition`; it would just be a task that ends
`failed`, carries the real error (`GetNutrition failed: simulated upstream
HTTP 500`), and is safe for the caller to retry later once the dependency
recovers.

Where `input-required` WOULD legitimately apply here: if a request arrived
with an empty or missing `avoid` list ("adapt this for my allergies" with no
allergies named), the orchestrator should pause there instead of guessing —
that is a real information gap, not an infrastructure fault.

## What A2A buys over a plain REST call to the worker

A REST call to `get_nutrition` returns a response or an HTTP status; the
caller has to invent its own convention for "still working," "needs more
info from the user," or "here is a durable task ID to poll or resume,"
and every consuming team invents that convention slightly differently. A2A
buys two things a bespoke REST wrapper does not: a **shared, typed lifecycle**
(`working`/`input-required`/`failed`/`completed`) that any A2A-aware client
already knows how to render or retry against without reading this service's
docs, and a **published AgentCard for capability discovery** — a caller can
ask "what can you do, in what modes, under what auth" before ever sending a
task, instead of that knowledge being tribal, out-of-band documentation.
