# Tasks

**Not built.** The mechanism by which the system asks a person for work, and the reason
[verification](verification.md) is a queue rather than a screen. Every stage uses it, not just
Extract.

---

## The chain, and where conflicts belong on it

```
extraction  ->  candidates  ->  tasks  ->  decisions  ->  facts  ->  conflicts
```

A conflict is the **last** link. It is what two confirmed facts do when they disagree.

Today the pipeline emits conflicts at the second link, between two things nobody has agreed are the
same feature — a count mismatch between a drawing callout and a pattern that may not be the pattern
it describes. That is not a disagreement, it is an unfinished question.

**So conflicts are no longer shown.** Not suppressed cosmetically: moved to where they mean
something. They return when a confirmed association can produce one. Until then the same
information appears one link earlier, as a task.

## A task

A request from the system to a person for something it cannot produce itself.

| field | what it holds |
|---|---|
| `stage` | which stage is waiting — drives the badge on the stage rail |
| `kind` | which specialised workspace opens |
| `title` | one imperative line |
| `subject` | what it is about: an artifact and a locator |
| `because` | what is unknown, in plain language |
| `unblocks` | what becomes possible, counted |
| `tried` | what the system already attempted, and why it failed |
| `effort` | estimated seconds |
| `origin` | `rule` or `agent`, named |
| `state` | open, done, declined, skipped, stale |
| `result` | written back on completion |

`tried` is not optional. **An agent must attempt a task and fail before it is allowed to ask**, and
the attempt is shown on the card. Without that field a queue becomes a way of making a person do
the machine's work, which is the failure mode of every todo system ever shipped.

`unblocks` is what makes a queue get finished. *"3 associations become checkable"* is work.
*"verify hole_pattern:2"* is a chore.

## Derive tasks, persist decisions

**Tasks are not stored.** They are recomputed on every run from what extraction produced and what
has already been decided. Only the decisions persist, in `verified.jsonl`.

A stored task can outlive its reason — detection improves, the question is moot, and the queue is
still asking it. A derived queue is always consistent with what is currently known, and a task that
has stopped making sense simply stops appearing. When one disappears because the answer arrived
from somewhere else, it is shown once as `stale` with the reason, never dropped in silence.

## What keeps the queue short

The part in `assets/` has 719 detected features and 255 callouts. A queue built by enumeration is a
queue nobody opens.

1. **A task exists only if the answer changes an outcome.** If nothing downstream reads it, there
   is no task — however interesting the question.
2. **Rank by what it unblocks**, never by order of discovery.
3. **Ask the cheapest discriminating question first.** On this part, confirming whether the
   drawing's `25X 26.00` covers both the Ø26.00 and Ø26.50 families settles *both* unresolved
   pairings at once. One question, two answers. That is information gain, and it is not the same
   ordering as importance.
4. **Batch by kind.** Seven readings to confirm is one card with seven items and single-key
   stepping, not seven cards.
5. **Nothing blocks.** Skip is always available and the pipeline continues with the item marked
   unverified. A queue that halts the product is a queue that gets abandoned.
6. **An answer changes the queue.** After each decision the agent re-runs and may propose new
   candidates or retire old ones. A count that visibly moves is what makes a queue finishable.

On the current part that is roughly a dozen tasks and a few minutes, not seven hundred items.

## A card opens a card

The todo card is an index. `kind` selects the workspace that opens:

| kind | workspace | the question it asks |
|---|---|---|
| `verify_reading` | drawing page, zoomed to the callout's box | is this what the sheet says |
| `verify_feature` | 3D view, the feature isolated | is this really there |
| `label_region` | 3D view with selection tools | what is this called |
| `confirm_association` | split — drawing box beside the feature | are these the same feature |
| `resolve_ambiguity` | the ranked candidates side by side | which of these |
| `supply_value` | a form | material, density, a load case |
| `confirm_parameter` | the model with the proposed parameter live | is this a lever worth having |

Three rules make this composable rather than a pile of modals:

**The task carries everything the workspace needs to open.** No refetch, no lookup, no guessing at
scope. A workspace that has to work out what it is looking at will get it wrong.

**A workspace never widens its own scope.** It answers exactly the task's subject. A person should
always know why this thing is in front of them, and the answer is always "because of the task you
clicked".

**The only way out is the result.** A workspace cannot write a fact directly; it returns a result,
the task closes, the queue advances. Which means every human decision automatically carries a task
id, a timestamp and a person — provenance falls out of the mechanism instead of depending on
somebody remembering to record it.

## After extraction, the stage opens on work

Extraction finishing is not the end of a stage; it is the point where the agent has read everything
and knows what it could not settle. So the Extract stage opens on the queue, not on the report:

```
+-------------------------------------------------------------+
|  Extract complete.  12 tasks - about 4 minutes               |
|                                                              |
|  [ ] Confirm 7 drawing readings           unblocks 3 pairs   |
|      tried: the diameter symbol is absent from the PDF       |
|                                                              |
|  [ ] Does 25X 26.00 cover two families?   unblocks 2 pairs   |
|      tried: matched on size; count disagrees 25 vs 23        |
|                                                              |
|  [ ] Label the Ø14 holes on the model     unblocks 4 callouts|
|      tried: no pattern detected at that size                 |
|                                                              |
|  Drawing  ·  Geometry  ·  Field >                            |
+-------------------------------------------------------------+
```

The report is a tab away, not gone. But the first screen after a run should say what the system
needs, because that is the only thing on it that a person can act on.

The stage rail carries a badge per stage: how many tasks that stage is waiting on. That is also the
answer to *which node am I talking to* — the stage with open tasks is where the session actually
is.

## Not only for verification

The same mechanism carries every human decision in the platform. Generate is the next consumer:
the standing rule that **an agent proposes parameters freely and a person confirms before one is
saved** is exactly a `confirm_parameter` task, ranked and queued like any other.

Two invariants hold everywhere:

- **An agent proposes; a person disposes.** Nothing an agent produces enters the record as
  verified.
- **Every fact with a person behind it names them**, because the task it came from did.
