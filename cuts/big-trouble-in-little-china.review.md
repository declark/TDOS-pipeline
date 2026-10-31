# Big Trouble in Little China — cut review

**Verdict:** Close to ready. The story holds together, every `must` beat is in, and the checker reports no FAIL. The biggest problem: the hook moment, Jack driving the truck through Lo Pan, falls in a 3.8s source skip, so the payoff of a `must` beat and our reaction to it never play. A handful of smaller payoffs are clipped the same way (Lightning's death, "Only a dream...", "nothing to triple", our Wild Man and Thunder shouts).

## Checker

`python src/check_cuts.py --cuts cuts/big-trouble-in-little-china.json --verbose`

- 848 segments, 43.0 min.
- Layout mix: `panel` 60.6%, `_hosts_only` 22.0%, `pip_circles` 14.9%, `hosts_full` + `hosts_movie_audio` 2.5%. All inside target, `panel` and `pip_circles` both at the edge.
- 0 FAIL, 1 WARN: 28 of 722 film-audio runs go past 4s. 158 segments have no transcribed words (silent beats).

Of the 28 over-4s runs, most give a real reason (a line that would be chopped). Three don't: segments 157, 178 and 183 say "no usable word boundary near 4s", but they sit over the wordless alley battle with our own fragments in them, so a cut at 4s is easy. Five more (356, 540, 663, 675, 676) say "an overlapping word of ours runs past 4s". The film line is the actual reason in each case, so those only need the reason rewritten.

## Beat coverage

| rank | beat | status | segments |
|---|---|---|---|
| **must** | Pork Chop Express CB opener | covered | 24–36 |
| **must** | The bet, bottle slice, "It's all in the reflexes" | covered | 49–70 |
| **must** | Alley battle; the Three Storms | covered (layout thin: 1170–1340 is almost all `panel`) | 139–181 |
| **must** | Lo Pan appears; Jack drives straight through him | **thin**: the drive-through itself is in the 1437.3–1441.0 skip | 182–199 |
| **must** | The Storms smash in and take Miao Yin | covered | 265–281 |
| **must** | Gracie's office; "Like the wind"; "call the president" | covered | 282–299 |
| **must** | Old Lo Pan: "Shut up, Mr. Burton!", "Indeed!" | covered | 347–379 |
| **must** | The Guardian | covered | 629–654 |
| **must** | Egg's potion; six-demon bag; "hot in here" | covered | 655–670 |
| **must** | Wedding; Jack fires into the ceiling and knocks himself out | **thin**: 2.8s skipped right before our "He's got knocked out" | 671–689 |
| **must** | Wedding fight: Wang vs Rain, Egg vs Lo Pan | covered | 690–738 |
| **must** | Lipstick | covered | 739–751 |
| **must** | Knife catch, Lo Pan killed, "It's all in the reflexes" | covered | 752–768 |
| **must** | Thunder swells up and explodes | covered (our "my god and" is cut) | 769–779 |
| **must** | "Shook the pillars of heaven"; Pork Chop Express drives off; Wild Man on the truck | covered | 836–846 |
| strong | Run for the bus; the Wild Man takes Gracie | thin: our "My god / Oh" peak (3657.7–3660.1) is cut | 493–514 |
| strong | Storeroom: "Only a dream can kill a dream" | thin: line starts at "a dream", "Only" (4412.3) cut | 610–628 |
| strong | Escape: Egg drops the statue on Lightning | thin: cut ends 5519.8, before the crush and our "they booted him" | 780–803 |
| strong | Restaurant ending: "Nothing to triple" | thin: the callback to the opener's "nothing to double" (5697.7–5701.2) is skipped | 819–835 |

What fans come for: everything is visibly in except the two lines the research sheet couldn't find in the film transcript ("Everybody relax, I'm here" and "Son of a bitch must pay!"). Both probably sit in the wordless holes at 3185–3413 and 5357–5410. They need a picture check in the timeline; they can't be placed from the transcripts. `iconic` is on the `must` beats and nowhere else.

## Findings

### 1. [must-fix] The truck going through Lo Pan isn't in the cut
- **Where:** segments 187–188 (1433.10–1437.28, skip to 1441.03)
- **Problem:** Jack's line "What the hell could I run straight through him?" ends at 1437.0 and the cut jumps to "Okay. I'm going home." The drive-through (wordless, 1437.0–1438.9) and our "Oh, oh, get" (1438.9–1441.0) are both skipped. The viewer hears the setup but never sees the payoff, and the cutter's own hook isn't in the cut.
- **Fix:** extend 187 to end at 1438.66 (5.6s run, reason: the payoff lands right after the line). Add a `pip_circles_hosts_only` 1438.66–1441.02 carrying "Oh, oh get" over the picture. Hook end → 1441.02.

### 2. [should-fix] Lightning's death is skipped
- **Where:** segments 797–798 (ends 5519.80, skip to 5528.80)
- **Problem:** "Lightning crushed under a statue" is on the fans list. The cut stops on our "That's what's gonna get rid of the..." and skips the crush and our "mighty powerful dude, Buddha Buddha, they booted him" (5519.8–5524.1).
- **Fix:** add `pip_circles_hosts_only` 5519.80–5524.12 after 797.

### 3. [should-fix] Jack knocking himself out may fall in a skip
- **Where:** segments 688–689 (4846.83–4849.23, skip to 4852.01)
- **Problem:** the knock-out is wordless. Our "He's got knocked out" at 4852.3 says it landed just before, and the cut skips the 2.8s right before our line. That breaks event-before-reaction on a `must` beat.
- **Fix:** move 688 to 4847.95–4851.80 (3.85s) so it runs straight into the `hosts_full` reaction.

### 4. [should-fix] Missed peak: our "My god / Oh" at the Wild Man
- **Where:** between segments 504 and 505 (3657.49–3660.12)
- **Problem:** one of the sheet's three named reaction spikes. The cut goes from "Where's Gracie?" straight to the Wild Man pip and drops our shout.
- **Fix:** add `pip_circles_hosts_only` 3657.49–3660.12 after 504.

### 5. [should-fix] Missed peak: "Oh... my god and... poof" at Thunder
- **Where:** between segments 775 and 776 (5393.48–5395.42)
- **Problem:** the cut keeps "He's just gonna Oh" and "poof" but skips "My god and", so the run-up to the best-remembered death loses its middle.
- **Fix:** add `pip_circles_hosts_only` 5393.48–5395.42 after 775.

### 6. [should-fix] "Only a dream can kill a dream" is clipped
- **Where:** segment 620 (4415.20–4417.77)
- **Problem:** it starts at "a dream...". "Only" (4412.31–4413.27) is cut, so the quoted line plays as "a dream can kill a dream".
- **Fix:** start 620 at 4412.06 (5.7s run, reason: a 2s pause sits inside the line). Gap from 619 stays 4.0s.

### 7. [should-fix] "Nothing to triple" callback is skipped
- **Where:** segment 826 (5701.46–5705.18)
- **Problem:** the bet's "nothing to double" (segments 56–57) pays off at the end with "Nothing to triple. Nothing to double. Triple." The cut keeps the less useful "You earned it" right after it instead.
- **Fix:** replace 826 with `panel` 5697.73–5701.42.

### 8. [should-fix] Over-4s runs with no real reason
- **Where:** 157 (1194.40–1199.92, 5.5s), 178 (1369.64–1375.20, 5.6s), 183 (1401.13–1406.27, 5.1s)
- **Problem:** "no usable word boundary" doesn't hold. The film is wordless here, and the extra time is our dangling fragments ("other", "now,", "going").
- **Fix:** 157 start → 1197.20 (2.7s). 178 → 1370.58–1374.47 (3.9s of wordless battle between our "Scratcher" and "now"). 183 start → 1401.90 (4.4s; the closest start to a word boundary after "going", with the reason stated). Rewrite the reasons on 356, 540, 663, 675, 676 to name the film line that actually forces the length.

### 9. [should-fix] The alley battle plays almost entirely in a small panel
- **Where:** segments 139–181 (1072–1392)
- **Problem:** it's the biggest visual `must` beat and our biggest reaction peak, but from 1170 to 1340 the only `pip_circles` is 1.2s (167). Talky dialogue scenes get more fullscreen time than the fight.
- **Fix:** 145 (1108.76–1112.00, the action breaking out just before "I'm very confused... I love it"), 155 (1181.59–1185.19) and 170 (1316.85–1319.45) → `pip_circles`. All three are wordless. To keep `pip_circles` at ~15%, move the same time back to `panel` from talky stretches where the pip isn't what's holding a panel streak down: 26–27 (CB monologue, both flanked by pip), 102 (our "goes right into action" commentary), 541 (Lo Pan and the brides), 757 (our "what's his name" chatter).

### 10. [should-fix] Dead weight
- **Where:** 92 (746.00–746.87), 129 (1013.37–1014.54), 316 (2273.51–2288.18), 91 (732.29–745.84)
- **Problem:** 92 ("even know") and 129 ("duck if") are leftover fragments. 316 ("They want horror movies... I don't want to be scared") is 14.7s of off-film tangent, muting Egg's I Ching scene, and it isn't strong enough to stand alone. 91 is a 13.6s stunner-shades argument whose second half only repeats the first.
- **Fix:** drop 92, 129, 316. Trim 91 to end at 737.19 (after "I don't even know."). Add 316 and the back half of 91 to `near_misses`.

### 11. [consider] Long muted cell conversation
- **Where:** segment 395 (2826.50–2850.11, 23.6s `pip_circles_hosts_only`)
- **Problem:** the "girl ninjas / guys can't hit girls / I'll hit anybody" disagreement mutes Wang's "Lo Pan has plans for us". It's long, but it's the dynamic (a disagreement), and the legend that matters (400–405) still plays.
- **Fix:** none. Leave as is.

Story coherence: no other holes found. Event before reaction: only finding 3. Rhythm: lengths and layouts vary well. No metronome stretches beyond what the checker lists. Intro (segment 1, 16.1s): fine, it names the film, says we've never seen it, and stops.

## Hook

The cutter's hook, 1433.05–1441.0 (Jack drives through Lo Pan, our "Oh, oh, get"), is the right one: a famous visual on a `must` beat with our shout landing on it. Before this review it wasn't actually in the cut (finding 1). The runner-up stays Thunder, 5389.5–5410.3.

## Changes applied

Segment numbers are the original ones. The new list is renumbered: the 4 added segments and 3 drops shift everything after them.

- Finding 1: 187 now ends 1438.66 (5.6s, reason updated). New `pip_circles_hosts_only` 1438.66–1441.02 ("Oh, oh get") after it. Hook end → 1441.02.
- Finding 2: new `pip_circles_hosts_only` 5519.80–5524.12 after 797 (Lightning crushed, "they booted him").
- Finding 3: 688 moved to 4847.95–4851.80, running into the 689 `hosts_full` reaction.
- Finding 4: new `pip_circles_hosts_only` 3657.49–3660.12 after 504 ("My god ... Oh").
- Finding 5: new `pip_circles_hosts_only` 5393.48–5395.42 after 775 ("My god and").
- Finding 6: 620 now starts 4412.06 (5.7s, reason updated).
- Finding 7: 826 replaced by `panel` 5697.73–5701.42 ("Nothing to triple. Nothing to double. Triple.").
- Finding 8: 157 → 1197.20–1199.92. 178 → 1370.58–1374.47 (now a silent beat). 183 → 1401.90–1406.27. Reasons rewritten on 356, 540, 663, 675, 676.
- Finding 9: 145, 155, 170 → `pip_circles`. 26, 27, 102, 541, 757 → `panel` (panel streak cap still holds, max 4).
- Finding 10: dropped 92, 129, 316. 91 trimmed to 732.29–737.19. Both cut pieces added to `near_misses`.

**Left alone:** Finding 11 (segment 395), because it's the disagreement dynamic and the story beat around it still plays. Also left: "Everybody relax, I'm here" and "Son of a bitch must pay!", which are on no transcript, so finding them needs a picture check in the timeline. Our "Oh boy, it's a stampede" (1942.1) when the Storms crash in stays out: adding it would make a continuous film-audio run over 6s, and the beat is well covered without it.

**After:** 848 → 849 segments, 43.0 → 42.8 min. Layout mix: `panel` 60.6% → 61.0%, `_hosts_only` 22.0% → 21.6%, `pip_circles` 14.9% → 14.9%, `hosts_full` + `hosts_movie_audio` 2.5% → 2.5%. Checker: 0 FAIL before and after. Over-4s runs 28 → 27, each with its reason. `build_timeline.py --dry-run` accepts the list.
