# Childs Play — cut review

**Verdict:** The draft passed the checker and carried every beat and nearly every line we said, but it was cut blind: the film's biggest visual moments sat in the gaps between chunks. The worst case was Maggie's death, where the `pip_circles` "hammer hit" was actually Karen getting off a bus, because the research sheet's located time (1522.9) is wrong; the real hit is at 1499.0. Fixed here against the picture; it is ready to build, with one listen-through recommended on the set pieces.

Segment numbers below are the draft's (`cuts/childs-play.draft.json`), as the checker printed them before the fixes. Times are recording time.

How this was checked: besides the transcripts, I pulled contact sheets of film frames for the set pieces (movie file, film time + 92.05) and a loudness envelope of the reaction recording. The lav mics are clean (about -63 dB when we're quiet, -25 dB speech, -10 dB screams), so the envelope shows where we shouted even when the transcript has nothing. It has nothing for most of our biggest reactions.

## Checker

Draft: 851 segments, 42.3 min. `panel` 61.7%, `_hosts_only` 19.4%, `pip_circles` 14.6%, `hosts_full` 4.3%. 0 FAIL, 2 WARN (45 of 695 film-audio runs over the 4s default; 4 boundaries inside a word in our transcript).

The 45 over-4s runs: I compared each with the film words inside it. All of them carry one whole line or exchange and none can be trimmed to 4s without chopping it, so the stated reason holds. 45 is still a lot for "the exception" (see finding 16).

## Beat coverage

| rank | beat | status | segments |
|---|---|---|---|
| **must** | Toy store: soul transfer, lightning, explosion | **thin** — chant covered, but the strike was muted in a small panel and the explosion (415.5–417) skipped | 34–68 |
| **must** | Andy unwraps Chucky: "friend to the end. Hidey-ho" | covered | 143–151 |
| **must** | Maggie's death | **thin** — hit clipped at the first frame of a small panel, window crash skipped, truck impact skipped, `pip_circles` spent on a bus | 235–245 |
| **must** | "Aunt Maggie was a real bitch" / Charles Lee Ray | covered | 300–327 |
| **must** | The batteries / "Hi, I'm Chucky. Wanna play?" | covered (batteries drop, compartment, head turn all on screen, checked on picture) | 420–445 |
| **must** | "You stupid bitch!" — alive in Karen's hands | covered | 446–468 |
| **must** | Car attack on Norris | **thin** — both knife strikes, the knife between his legs and the gunshot each fell in a skipped gap | 523–572 |
| **must** | Chucky and John: "a date with a six-year-old boy" | covered | 588–615 |
| **must** | Dying John: through the heart | covered | 616–632 |
| **must** | Andy with the bat; the second chant | covered | 688–730 |
| **must** | "This is the end, friend." — the burn | **thin** — line intact, but the match landing and Chucky going up (4623.8–4625.5) skipped | 757–769 |
| **must** | Burnt Chucky | covered | 770–814 |
| **must** | The body attacks Jack; the heart shot; "Wanna play?" | **thin** — the body's grab (4968.5) skipped; the shot in a small panel with its impact cut off | 826–841 |
| strong | Caputo's hideout blows up | thin — cut ended on the muzzle flash, blast skipped | 383–386 |
| strong | Dr. Ardmore and the electroshock | thin — the headset going on skipped | 668–677 |

All "What fans come for" lines are in and whole: catchphrase 148, "real bitch" 313, "Wanna play?" 431, "You stupid bitch" 449, "date with a six-year-old boy" 614, "Ugly doll / Fuck you" 686, "This is the end, friend" 758, "Give me the boy" 782.

## Findings

### 1. [must-fix] Maggie's death is aimed at the wrong moment
- **Where:** segments 235–245 (1488.3–1531.3)
- **Problem:** On picture the hammer hits at 1499.0, she goes through the window at 1502.2–1502.9, falls until 1509.2 and hits the truck at 1509.4. The research sheet's "hammer hit 1522.9–1524.8" is Karen stepping off a bus (the `Ah!` there is a no-VAD artefact). So the draft's two `pip_circles` "moment itself" segments (242–243) show a bus, the hit lands on the first frame of a small `panel` (237, from 1498.97), the window crash and the truck impact are both skipped, and the two `hosts_full` "reactions" (241, 244) cut to our faces while nothing is happening. Our real reaction is a scream at 1497.2–1498.2 (the loudest thing in the first half), a shout at 1500.0–1501.0, open mouths to 1506, and a shout at 1507.0–1509.5. None of it was framed as a reaction.
- **Fix:** Drop 236–244. Add `pip_circles` 1494.80–1500.30 ("I'm scaring myself half to death" through the hit), `hosts_full` 1500.30–1502.00, `pip_circles` 1502.00–1505.00 (through the window), `pip_circles` 1507.05–1511.00 (impact on the truck), `panel` 1513.30–1516.50 (broken window), `panel` 1521.40–1524.80 and 245 as `panel` (Karen arrives), the last two relabelled to the next beat and `iconic` false.

### 2. [must-fix] The toy store never blows up
- **Where:** segments 67–72 (406.7–435.0)
- **Problem:** The bolt hits the store at 411.5, the toys fly to 415.5, the blast is 415.5–417 and the street-side explosion runs to 420.5 (the sheet's "explosion ~400–409" is early). The draft put the strike under a muted `panel_hosts_only` (68), skipped 412.3–416.8, and came back on the last embers. The pay-off of the origin scene, a "What fans come for" item, isn't in the video.
- **Fix:** 68 becomes `pip_circles_hosts_only` 409.31–411.30 (our "Okay" over the lightning, the break). Add `pip_circles` 411.30–416.90 (strike to blast). Drop 69. 70 becomes `pip_circles_hosts_only` 416.90–423.30, our "all the toys done, no more toys" over the explosion outside.

### 3. [should-fix] Car attack: the four things we scream at are off screen
- **Where:** segments 532–533, 540–543, 569–570 (3336.9–3522.3)
- **Problem:** Our four loudest moments in the scene are at 3342.2 (Chucky rises behind the seat), 3383.7 (first knife through the seat, the loudest of the recording), 3391.3 (second knife) and 3517.1 (Norris shoots Chucky off the windscreen). The draft's chunks start 0.7s after the first knife, end before the second, end 0.25s before the gunshot, and 543 stops at 3395.8 with the knife coming up between his legs at 3396.2, so "Jesus Christ" (544) reacts to something the viewer never saw.
- **Fix:** 532 end → 3339.90; 533 → `pip_circles` 3341.90–3344.36. 540 end → 3380.30; 541 → `pip_circles` 3382.30–3385.37. 542 end → 3391.80. 543 → 3395.40–3398.70, butting the `hosts_full`. 569 → 3514.30–3518.30; 570 start → 3520.35.

### 4. [should-fix] Finale: the body's jump scare and the heart shot
- **Where:** segments 826–827, 835–836 (4965.9–5020.4)
- **Problem:** The headless body grabs Jack at 4968.5 and we scream at 4968.9–4970.8; that sat in the gap between 826 and 827. The heart shot (fired 5012.8, body thrown back to 5016) was a small `panel` that ended on the impact. It is the pay-off of our "go for the heart" running bit.
- **Fix:** 826 → `pip_circles` 4966.30–4971.30, drop 827. 835 → `pip_circles` 5011.31–5016.40; 836 start → 5018.45.

### 5. [should-fix] The burn: he never catches fire
- **Where:** segments 758–759 (4616.9–4628.7)
- **Problem:** After "This is the end, friend" the draft skipped 3s and came back with the fireplace already burning in a `panel`. The match landing and Chucky screaming as he goes up are 4623.8–4625.5.
- **Fix:** Add `hosts_full` 4622.19–4623.60 as the break after the line; 759 → `pip_circles` 4623.60–4627.60.

### 6. [should-fix] Caputo's house: cut ends on the muzzle flash
- **Where:** segments 384–385 (2415.6–2426.1)
- **Problem:** Eddie fires at 2418.5 and the house goes up 2419–2421.6; 384 ended at 2419.47 and 385 picked up the tail. "Oh my goodness" (386) follows a blast the viewer mostly missed.
- **Fix:** 384 → 2417.60–2421.60; 385 start → 2423.65.

### 7. [should-fix] Nine loud reactions the transcript dropped were cut off or left out
- **Where:** after 431; 315–316; 474; 605–606; 718; 735; 749–750; 779; 798
- **Problem:** The envelope shows shouts with no words in the transcript, each right on an event, that the draft clipped or skipped: 2713.3 (gasp after the head turn), 1957.3–1959.7, 2934.0–2935.5, 3753.2 (the voodoo-doll leg snap), 4378.0–4379.5 (Andy hit with the bat), 4468.5, 4557.4–4558.7, 4720.9–4723.1 (burnt Chucky appears) and 4812.9–4814.8 (his head shot off).
- **Fix:** Add `hosts_full` 2712.66–2714.30. 315 end → 1959.75, 316 → 1961.80–1963.00. 474 → 2933.90–2937.50 ("Wait a minute. I am telling you the truth."). 605 end → 3754.10, drop 606. 718 → 4377.60–4381.40. 735 → 4468.00–4471.50. 749 end → 4555.40, 750 → 4557.45–4561.00. 779 start → 4719.50. 798 end → 4815.00.

### 8. [should-fix] Ardmore: the headset goes on off screen
- **Where:** segments 670–671 (4116.2–4126.0)
- **Problem:** Chucky straps the headset on at 4113–4114.5, in the gap after the `hosts_full`. And 671, where we say "he's electro-shocking him", is a small `panel_hosts_only` when the picture is the subject.
- **Fix:** 670 → `pip_circles` 4112.86–4116.90; 671 → `pip_circles_hosts_only`.

### 9. [should-fix] Our lines clipped at segment edges
- **Where:** 53 boundaries on `_hosts_only` / `hosts_full` segments, e.g. 87 end 529.45 ("rooms"), 216 end 1390.48 ("trip"), 218 end 1400.28 ("dolls"), 276 end 1742.43 ("babysitter"), 572 end 3530.28, 78 start 473.94
- **Problem:** The transcript's word times stretch or bunch around long silences, so some segments end while we are still audibly talking, by up to 0.9s.
- **Fix:** Where the lav level is above speech level at a boundary, move it to the nearest quiet point (0.8s limit), taking the time from the touching film chunk. These boundaries now sit on audio, not on a transcript word, which is why the checker's "not within 0.3s of a word" warning appears.

### 10. [should-fix] Three story gaps
- **Where:** segments 406–407; 586; 575
- **Problem:** Ardmore's only set-up was a fragment ("more than enough. Maybe Andy should spend a couple"). John was introduced by "Chucky, and" (586), so "find him before Chucky does" had no "him". "Quite the mural" was cut after "quite".
- **Fix:** 406 → 2550.40–2555.40 ("I've seen more than enough. Maybe Andy should spend a couple of days with us."), 407 start → 2557.40. 586 → 3630.10–3636.00 ("his nickname was Chucky, and he spent a lot of time with this man"). 575 end → 3541.45 and a new `panel_hosts_only` 3549.95–3552.10 for "quite the mural".

### 11. [should-fix] Dead weight
- **Where:** segments 70–72 (418.8–435.0); 136, 137, 142 (841.2–892.9)
- **Problem:** 70 ran 12.9s of us on whether toy stores still exist, over the titles; 72 was a 0.8s `hosts_full` of one stray word; 136/137/142 are mid-sentence fragments of an optional scene.
- **Fix:** 70 trimmed to end at 423.30 (see finding 2); drop 71, 72, 136, 137, 142. "It's my son's birthday" / "what a jerk" stays.

### 12. [should-fix] `iconic` set on beats that aren't the famous ones
- **Where:** segments 616–632, 688–730, 242–245
- **Problem:** `iconic` was true on every segment of every `must` beat. "Dying John" and "Andy waits with the bat" are `must` for the story, not for fame.
- **Fix:** `iconic` false on those two beats and on the two Karen-arrives segments.

### 13. [should-fix] `pip_circles` spent on talking heads
- **Where:** segments 139, 332, 423, 448, 675, 794, 820
- **Problem:** The draft spread `pip_circles` evenly as a streak-breaker, so dialogue close-ups got the full-screen film while the stunts sat in panels.
- **Fix:** Those seven → `panel` (only where it doesn't make a 5-panel streak), which pays for the `pip_circles` added in findings 1–8.

### 14. [consider] Film audio blipping in for 1–2s inside one of our sentences
- **Where:** segments 4–6, 10–12, 16–18, 285–287, 343–345, 617–619, 702–704, 719–721
- **Problem:** `_hosts_only` → 1.1–1.8s `panel` → `_hosts_only` on contiguous time, mid-thought ("Santa" / film / "Definitely not Santa").
- **Fix:** Merge each trio into one `_hosts_only` segment. Applied.

### 15. [consider] Film dialogue chunks start and stop mid-sentence
- **Where:** roughly a hundred `panel` chunks in the talky scenes, e.g. 90–91, 110–111, 131, 149, 151, 171–175, 470–475
- **Problem:** Boundaries are on word edges but not sentence edges ("TV in your very own home. Good guys"). It plays like sampling.
- **Fix:** Snap each to the nearest sentence edge in the cut stage. Not applied: that is a re-cut of the dialogue scenes, not a review fix.

### 16. [consider] Metronome in the set pieces
- **Where:** e.g. 420–426, 446–457, 757–766, 776–783
- **Problem:** Long stretches of ~3s on / ~2.5s off, and 1 in 13 film runs over 4s.
- **Fix:** Left alone except where findings 1–8 re-timed chunks to the events, which breaks the pattern at the moments that matter.

### 17. [consider] "Oh, no. Oh, no." at 1455
- **Where:** segment 230 (1455.0–1458.0)
- **Problem:** The words are really there (audio confirms), but the event before it (229) is 1.2s of silent panel and it isn't clear what we're reacting to.
- **Fix:** Kept; end trimmed to 1457.60 to drop a stray "How". Worth a look in Resolve.

Passes with nothing to report: the intro (18.7s, says only the film, never seen it, going in cold); running bits (scared-since-a-kid, goofy-or-intense, big doll, "go for the heart", the "hi, I'm Chucky" call all have set-up and pay-off in the cut); `near_misses` (none beats anything in the cut).

## Hook

Cutter's: 3396.5–3408.85, the knife in the car into "Jesus Christ" / "Get the fuck out of the car, man". Kept. It was a hook whose cause wasn't on screen; with finding 3 it is. Runner-up, wordless: Maggie and the hammer, 1494.8–1505.0.

## Changes applied

- Finding 1: draft 236–244 replaced by six segments (now 225–230); 245 → `panel` (now 231).
- Finding 2: 68 re-laid and shortened (now 62), new `pip_circles` 411.30–416.90 (63), 70 → `pip_circles_hosts_only` 416.90–423.30 (64); 69 dropped.
- Finding 3: 532, 533, 540–543, 569, 570 re-timed as listed (now 515–516, 523–526, 552–553).
- Finding 4: 826 → 4966.30–4971.30 (now 804), 827 dropped; 835 → `pip_circles` to 5016.40 (now 812), 836 from 5018.45.
- Finding 5: new `hosts_full` 4622.19–4623.60 (736); 759 → `pip_circles` 4623.60–4627.60 (737).
- Finding 6: 384 → 2417.60–2421.60 (now 366); 385 from 2423.65.
- Finding 7: new `hosts_full` 2712.66–2714.30 (414); 315, 316, 474, 605, 718, 735, 749, 750, 779, 798 re-timed as listed; 606 dropped.
- Finding 8: 670 → `pip_circles` 4112.86–4116.90 (now 651); 671 → `pip_circles_hosts_only`.
- Finding 9: 53 boundaries moved to the nearest quiet point.
- Finding 10: 406, 407, 586, 575 re-timed; new `panel_hosts_only` 3549.95–3552.10 (560).
- Finding 11: 71, 72, 136, 137, 142 dropped.
- Finding 12: `iconic` cleared on the two story-only `must` beats (about 60 segments) and the two Karen-arrives segments.
- Finding 13: seven `pip_circles` → `panel`.
- Finding 14: eight trios merged (16 fewer segments).
- `hook` note and `near_misses` updated (adds the trimmed toy-store chat, the Criswell opening, "What is wrong with me?", and an unplaced loud laugh at 582.2 during the advert).
- `cuts/childs-play.research.md`: corrected the two wrong located times (hammer hit, explosion).

**Left alone:** 15 (a re-cut of the dialogue scenes; belongs to the cut stage). 16 (same). 17 (kept, trimmed). The over-4s runs (each is one whole line). `pip_circles` ends at 15.2% against "~15%": getting it lower means either a 5-panel streak or taking a set piece back out of full screen.

Not verified by ear: the fixes were placed from frames and the loudness envelope, not by listening. The silent `hosts_full` cutaways the draft added (63, 531, 566, 669, 787, 801, 807, 837) were not checked against our faces.

**After:** 851 → 828 segments; 42.3 → 42.5 min. `panel` 61.7 → 60.2%, `_hosts_only` 19.4 → 20.2%, `pip_circles` 14.6 → 15.2%, `hosts_full` 4.3 → 4.4%. 0 FAIL before and after; WARN 2 → 6 (over-4s runs 45 → 53, `pip_circles` 15.2%, one same-length triple, repeating-pattern stretches, and the two word-boundary warnings, which come from boundaries placed on picture and audio where the transcript has no words).
