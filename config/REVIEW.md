---
name: tdoffscript cut review
description: Review rules for a long-form cut list - check it against the research sheet, the transcripts and config/SKILL.md, report what's weak, then fix it.
---

# TDOffScript cut review

This is the third of three stages:

1. **Research** (`config/RESEARCH.md`) → `cuts/<slug>.research.md`
2. **Cut** (`config/SKILL.md`) → `cuts/<slug>.json`
3. **Review** (this file) → `cuts/<slug>.review.md`, and a revised
   `cuts/<slug>.json`

You didn't make this cut. Read it the way an editor reads an assistant's first
assembly: is the story there, are the best moments in, does it play. The
cutter's `reason` on a segment is a claim to check against the transcripts,
not evidence.

`config/SKILL.md` is the rulebook. This file doesn't restate its rules or
change its numbers; it says what to look for and in what order. Read
`config/SKILL.md` in full first.

## ATTACHED

1. The cut list, `cuts/<slug>.json`: the segments, plus the cutter's `hook`
   and `near_misses`.
2. The research sheet, `cuts/<slug>.research.md`.
3. Both word-level transcripts and [OFFSET], as in `config/SKILL.md`.
4. The output of `python src/check_cuts.py --cuts cuts/<slug>.json`.

## WHAT A GOOD CUT DOES

In order of importance. When two of these pull against each other, the higher
one wins.

1. A stranger to the film can follow it start to finish.
2. Every moment fans come for is in it, and can be seen properly.
3. Our best reactions are in it, each one after the thing that caused it.
4. Nothing in it is there only to fill time.
5. It plays like a person cut it.

## THE PASSES

Do them in this order. Each finding gets a severity:

- **must-fix** — breaks a hard limit in `config/SKILL.md`, drops a `must`
  beat, or loses the story.
- **should-fix** — the cut is clearly better with the change.
- **consider** — a judgement call; say what you'd do and why.

### 1. Hard rules

Run the checker. Every `FAIL` is a must-fix. Read the `WARN` lines as leads
for the passes below rather than as findings in themselves: a layout share
just outside its target matters less than a missing beat.

For the film-audio runs it lists as over the 4s default, read each segment's
`reason`. If it doesn't say why the run had to go long, or the why doesn't
hold up against the transcript, it's a should-fix.

### 2. Beat coverage

Go down the beat sheet and mark each beat as covered, thin or missing, using
the segments' times against the beat's recording-time range (don't trust
`film_beat` labels alone).

- A `must` beat that's missing is a must-fix.
- A `must` beat that's thin is a should-fix: the payoff isn't on screen, the
  famous line is clipped, or it's only our reaction with no event.
- Every item under "What fans come for" must be visibly in the cut, with its
  line or image intact.
- `strong` beats may be skipped for runtime. Flag one only if its absence
  leaves a hole in the story or a later segment refers back to it.
- Check that `iconic` is true on the segments of famous `must` beats and
  nowhere else.

### 3. Story coherence

Read the cut in order as someone who has never seen the film, using only what
would be on screen and audible. Flag every place where they'd be lost:

- a payoff whose setup was cut, or a setup that never pays off;
- a character who matters appearing with no introduction, or vanishing;
- a jump in place, time or stakes with nothing to bridge it;
- the ending: is it clear how it ends and what happened to whom?

The fix is usually a short `panel` chunk of the missing setup, not a longer
scene.

### 4. Event before reaction

For each reaction segment (`hosts_full`, `_hosts_only`, or a `panel` kept for
our shout), find what we're reacting to and check it against STEP 3 rule 2 of
`config/SKILL.md`:

- the event is on screen before the reaction, not after;
- the event segment runs up to or just into the moment it lands, so the
  viewer sees it;
- the reaction follows closely enough to read as a reaction to that.

### 5. Missed peaks

Independently scan our transcript for the STEP 2 signals in `config/SKILL.md`
(shouts, both talking at once, a burst after silence, laughter, a call proved
right or wrong) and list every strong one that isn't in the cut. Then look at
the cutter's `near_misses`.

For each, decide whether it beats something that IS in the cut. If it does,
that's a swap: name what goes in and what comes out. Check the research
sheet's "Our running dynamic" too. A running bit needs its setup, at least
one middle beat and its payoff to land; flag it if a leg is missing.

### 6. Dead weight

Flag segments that don't earn their place:

- us narrating what's already visible on screen;
- dead air with no payoff, false starts, trailing-off sentences;
- a second, weaker take on a moment the cut already covers;
- standalone commentary that isn't strong enough to stand alone;
- film chunks that neither advance the story nor set up a reaction.

Cutting these is how the swaps in pass 5 fit inside the runtime.

### 7. Layout choices

Check each layout against "When to use which" in `config/SKILL.md`:

- `pip_circles` is on the film's big visual beats, and those beats aren't
  stuck in a small `panel`;
- `_hosts_only` layouts are where our conversation is the content, and aren't
  muting a line of film dialogue the viewer needs;
- `hosts_full` is short and lands on a real reaction;
- long stretches that look the same get a change that suits the moment.

### 8. Rhythm

Use the checker's rhythm warnings as a starting list, then read the lengths
and layouts as a sequence. Flag metronome stretches, repeating layout
patterns, too many runs over the 4s default, and beats that all get the same
treatment regardless of size. Check that a big reaction gets room and a quick
gag gets a snap cut.

### 9. Intro and hook

The intro is under 20 seconds and says only what the INTRO section asks for.
Judge the cutter's `hook` against the peaks you found in pass 5. If a
stronger 5 to 15 second moment exists, name it.

## THE REPORT

Write `cuts/<slug>.review.md`:

```markdown
# <Title> — cut review

**Verdict:** one or two sentences. Is it ready, and what's the biggest problem?

## Checker

The checker's summary: runtime, layout mix, FAIL and WARN counts.

## Beat coverage

| rank | beat | status | segments |
|---|---|---|---|
| **must** | ... | covered / thin / missing | 41–47 |

`must` beats and anything thin or missing. Leave out covered `strong` and
`optional` beats.

## Findings

Ranked by impact on the finished video, most important first.

### 1. [must-fix] Short title
- **Where:** segments 212–215 (3591.1–3604.8)
- **Problem:** what's wrong, in terms of what the viewer sees.
- **Fix:** the exact change: new start/end/layout, drop, add, or swap.

## Hook

The cutter's hook, and yours if it differs.
```

Every finding names segment numbers (1-based, as the checker and the dry run
print them) and recording-time timestamps, and gives a fix specific enough to
apply without rethinking it. No finding without a fix. Don't pad the list: if
a pass found nothing, say so in a line.

## THEN FIX IT

After the report is written:

1. Copy the cut list as it stands to `cuts/<slug>.draft.json`. If that file
   already exists from an earlier review, leave it; it's the cutter's
   original.
2. Apply every must-fix and should-fix to `cuts/<slug>.json`. Apply a
   `consider` only when you're confident it's an improvement. Every new or
   moved boundary follows `config/SKILL.md`'s TIMESTAMPS rule, and every edit
   keeps to its BREAKS, exposure caps, hosts-only cap and 4-in-a-row `panel`
   cap. Update `hook` and `near_misses` to match.
3. Run the checker again. Repeat until it reports no `FAIL`, and until the
   fixes haven't pushed runtime or the layout mix outside their targets.
4. Append to the review file:

```markdown
## Changes applied

- Finding 1: what changed (segments before → after).
- ...

**Left alone:** findings not applied, and why.

**After:** segment count, runtime and layout mix, before → after.
```

Fix what the review found; don't re-cut the film. If the cut is so far off
that fixing means redoing most of it (the story doesn't hold together, or
many `must` beats are missing), stop after the report, leave the cut list
untouched, and say in the verdict that it should go back through the cut
stage.

In the chat summary, give the verdict, the count of findings by severity,
what was changed, what was left alone, and the before → after runtime and
layout mix.
