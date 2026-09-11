# Verification

**Not built.** This describes what is meant to run, so that it can be built without being
re-invented. [tasks.md](tasks.md) is the mechanism it uses; [status.md](status.md) says what
actually runs.

---

## The problem it solves

Extraction produces claims. Nothing checks them. [status.md](status.md) records the consequence:
zero associations have been confirmed by a person, so the hit rate of the matching rule is unknown
and unknowable from inside the system.

Worse, the rule is now visibly out of road. Size is the only quantity text extraction yields, a
size belongs to several features, and no amount of tuning invents a discriminator that the input
does not contain. Twelve of fifteen hole callouts find nothing at all. That is not a threshold
problem.

The way out is not a better rule. It is a person, used sparingly and in the right place, and a
system that remembers what they said.

## Three passes, in this order

**Each side is verified alone before the two are related.** An association between an unverified
reading and an unverified detection has two independent ways to be wrong and no way to tell which
one fired.

### Pass 1 — the drawing

Every callout is drawn as a box on the page it came from. Clicking one zooms the page to it. The
person answers about the *reading only*: is this the text, is this the value, is this the count,
**is this a diameter**.

That last question is worth the whole pass on its own. The diameter symbol does not survive text
extraction — not once on the drawing in `assets/` — so today a bare `21.00` is a diameter by
inference. One click makes it a fact, and the inference disappears from everything downstream.

Nothing here is about the model. A callout can be read perfectly and refer to nothing that was
detected.

### Pass 2 — the model

Detected features, shown in the 3D view, isolated one at a time. The person confirms the detection
and, optionally, **labels** it: *these are the mounting bolts*.

The label is where domain vocabulary is allowed to enter. The architecture rule is that geometry
gives the kind and documents give the role; a person is the third source of a role, and the only
one available when the drawing does not say. A label is stored as an ordinary fact with the person
as its source, never as a rename of the geometric kind — `hole_pattern:5` stays a hole pattern and
acquires a role.

### Pass 3 — associations

Only pairs whose **both sides are already confirmed** are offered. Confirm or decline.

A decline is worth as much as a confirmation. Confirmations alone measure nothing; it is the
declines that give the rule a false-positive rate, and after a few dozen of both across two or
three parts there is a measured number where there is currently an assurance.

**Conflicts are raised only on confirmed associations.** A count disagreeing between two things
that may not be the same feature is not a conflict, it is noise. Nothing is confirmed today, so
nothing qualifies, and the interface shows no conflicts at all — the same information appears one
link earlier as a task. See [tasks.md](tasks.md) for where each link sits.

## What is put in front of a person

The part in `assets/` has 719 detected features. Queueing them is the same as queueing nothing.

**Verification is spent only where it changes an outcome.** An item enters the queue when it meets
one of four tests, and the reason is shown on the item:

| reason | why it is worth a person |
|---|---|
| a callout has candidates | there is an association to confirm or deny |
| a pairing is ambiguous or unresolved | the rule has already refused; a person is the only resolver |
| a callout has **no** candidate | detection failed, and a person pointing at the model says what it missed |
| the feature is, or could become, a parameter | generation will move it; nothing else downstream cares |

Everything else stays reachable through the model index and out of the queue.

On the current part that is roughly eighteen items rather than seven hundred: fifteen hole
callouts, of which three have candidates and twelve have none, plus two unresolved pairings and one
refused ambiguity.

**Ranking the queue is judgement, not a rule** — see [the agent](#where-the-agent-belongs).

## Labelling, and the search it triggers

The person opens the 3D view, selects faces, and names them. That is not filing; it starts a search.

1. The label and the selected geometry go to the agent.
2. It searches the drawing for callouts that could describe them — count, size, thread form, the
   view a callout sits in — including callouts the deterministic rule discarded.
3. It reports one of three outcomes, never a fact:
   - **found**, with the page and box, offered as a candidate association for pass 3;
   - **candidates**, ranked, with what separates them;
   - **not found**, with what it looked for.

**Not found is a real answer.** If the drawing does not dimension those holes, no association
exists, and the system should say so rather than manufacture one. The current pipeline has no way
to distinguish *not on the drawing* from *not matched by the rule*, and that distinction is most of
what is wrong with it.

## Storage

Verified work is written to `assets/<project>/verified.jsonl` — one record per line, append-only.

Append-only because a review session that goes wrong must not be able to destroy earlier work, and
because the sequence of decisions is the audit trail. The application writes it; nobody types into
it. That does not reopen hand-written configuration: a verification is *evidence produced by a
named person at a known time*, which is what the provenance model already exists to carry. It adds
a source kind, `HUMAN`, alongside CAD and DRAWING.

Each record carries who, when, what was decided, and — the part that actually matters — **two ways
to find the subject again**:

- the CAD content digest plus the feature id, which replays exactly on an unchanged file;
- a geometric fingerprint — kind, size, axis direction, centroid in the part's own frame — which
  survives a re-export that renumbers faces.

On load, a record that matches by digest is applied as **exact**. One that matches only by
fingerprint is applied as **re-matched** and says so on the card, because a re-exported model is
not the model that was verified. One that matches neither is kept, shown as **orphaned**, and never
silently dropped.

The queue itself, and how a task opens a specialised card, are described in
[tasks.md](tasks.md).

## Where the agent belongs

Four jobs, all of them ones no rule does well:

**Rank the queue.** What deserves a person's attention depends on what the drawing yielded and on
what generation will later move. Both are context, not thresholds.

**Search on a label.** The loop above.

**Propose detection where there is none.** Twelve callout families have no detected pattern.
Given the callout and the model, look for holes of that size that the detector missed — not on a
circle, not axial, below a threshold — and propose a region for confirmation.

**Generalise one confirmation into several proposals.** If a person confirms that `25X 26.00`
covers both the Ø26.00 and Ø26.50 families, that teaches that this drawing groups what the model
splits. The same reading can then be proposed for the other counted callouts — as queued
candidates, never as facts.

**The invariant: an agent proposes, a person disposes.** Nothing an agent produces enters the
record as verified. It can rank, search, propose and explain; it cannot confirm.

## The interface

A **review** view on the Extract stage, with the three passes as tabs and a queue that carries
across them.

```
+------------------+--------------------------------+------------------+
| queue            | evidence                       | decision         |
|                  |                                |                  |
| grouped by pass  | drawing page, zoomed to the    | confirm          |
| each item shows  | callout's box                  | decline          |
| why it is here   |   - or -                       | label ______     |
|                  | 3D view, feature isolated      | skip             |
| 18 of 719        |                                |                  |
+------------------+--------------------------------+------------------+
```

Three things this layout is for:

**The evidence is always visible beside the decision.** A person confirming a reading must be
looking at the page it was read from, at a legible zoom, not at a transcription of it.

**Single-key confirm, decline and next.** A review queue that needs the mouse for every item does
not get finished, and an unfinished queue produces no measurement.

**The count is shown honestly.** *18 of 719* states plainly that this is a filtered view and that
the filter is a judgement.

Labelling opens from the 3D view itself — select faces, name them, and the search above runs.

## What changes in the code

| now | after |
|---|---|
| an association becomes a `Fact` | it becomes a `Candidate`; only confirmation makes a `Fact` |
| conflicts raised on any size match | raised only on a confirmed association |
| `Evidence` sources are CAD and DRAWING | a `HUMAN` source, carrying who and when |
| the drawing reader yields text | it yields text **with boxes** — `pdfplumber` for word geometry, `pdf.js` to render the page |
| nothing persists between runs | `verified.jsonl`, loaded before the queue is built |
| `hole_basis` infers whether a value is a diameter | a confirmed reading replaces the inference |

Positional extraction is the prerequisite for all of it: without a box there is nothing to draw on
the page, nothing to zoom to, and no leader line for the agent to reason about.
