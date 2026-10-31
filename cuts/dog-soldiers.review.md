# Dog Soldiers — cut review

**Verdict:** Close to ready. The story holds and every `must` beat has footage. The biggest problem was that the mechanical chunking (fixed-length film chunks with timer-set skips) dropped or clipped several famous lines that fall between chunks. The worst cases: Spoon's "I hope I give you the shits" isn't in the cut, the silver letter-opener setup is chopped and muted, and the house explosion falls in a skip. All three are fixable in place without re-cutting.

## Checker

Draft: 737 segments, 38.7 min. panel 60.3%, `_hosts_only` 20.1%, pip_circles 14.5%, hosts_full 5.1%. 0 FAIL, 1 WARN (16 film-audio runs over 4s). 323 segments are wordless and unchecked.

Spot checks in this review went beyond the transcripts:
- Frame contact sheets of the film (woods attack, Wells' guts, Spoon's death, the explosion, the cellar, the Megan/Ryan look).
- A no-VAD whisper pass on four windows where the VAD transcript has holes (5738–5772, 5930–5960, 6058–6090, 6195–6232).

## Beat coverage

| rank | beat | status | segments (draft) |
|---|---|---|---|
| **must** | Ryan orders Cooper to shoot the dog; Cooper refuses | covered | 28–49 |
| **must** | "Spiders. And women. Spider women" | covered (joke timing broken by the skip, see 11) | 84–93 |
| **must** | Gutted cow; "dead flying fucking cow" | covered | 113–125 |
| **must** | SAS camp; "There was only supposed to be one" | covered | 144–166 |
| **must** | Woods attack: Bruce impaled, Wells gutted | covered (frames confirm Bruce on the branch 1896–1911 in 193–195, Wells' guts 1949–1975 in 201–204) | 178–211 |
| **must** | Run to the road; Megan's Land Rover | covered; the Megan/Ryan look is missing (see 5) | 212–239 |
| **must** | Superglue surgery; "Sausages"; "I love you" | covered | 308–332 |
| **must** | Megan explains the werewolves | thin: the "full moon, silver bullets, eyebrows" line is muted and "The eyebrows thing is nonsense" is missing | 336–355 |
| **must** | Generator cut; first assault | covered | 374–417 |
| **must** | "Dogs. More like pussies." / Terry taken | covered | 418–430 |
| **must** | Land Rover escape, Joe killed | covered | 484–525 |
| **must** | Ryan's confession, "You were bait" | covered | 526–553 |
| **must** | Ryan transforms and escapes | covered | 555–567 |
| **must** | Megan's reveal, "I'm the real thing" | thin: "It's that time of the month" (5526) is missing | 613–638 |
| **must** | Spoon's kitchen fight, "I hope I give you the shits" | **thin: the line is missing** | 639–682 |
| **must** | "We go together or we don't fucking go" | thin: clipped to "And we don't fucking go!" | 683–691 |
| **must** | Wells blows up the house | thin: the flash and blast (6081.4–6085.4) fall in a skip | 692–711 |
| **must** | Cellar, letter opener, "licking your own balls" | covered; the closing "it is now" is clipped | 712–724 |
| strong | Camping couple; the silver letter opener | thin: the gift line is chopped and "solid silver" is muted | 2–17 |

All `must` segments carry `iconic: true` and no others do. That's correct.

## Findings

### 1. [must-fix] Spoon's "I hope I give you the shits" is not in the cut
- **Where:** segments 656–657 (5751.50–5753.00, 5759.50–5762.40)
- **Problem:** The line is one of the "What fans come for" items. A no-VAD pass puts it at about 5750.7–5757.26 ("...you fucking wimp" also appears in the VAD transcript at 5756.19–5757.19). Frames show the werewolf's jaws beside Spoon's face from 5753 to 5759. The chunker skipped from 5753.00 to 5759.50, straight past the line, so the viewer gets the pan fight and then a dog close-up.
- **Fix:** Make 656 `pip_circles` 5752.80–5757.44 (4.64s; the reason notes that the line runs past 4s). Move 657's start to 5759.60 to keep the 2s skip. 659 ("watching him get devoured") then reads as the reaction to it.

### 2. [must-fix] The silver letter-opener setup is chopped and muted
- **Where:** segments 10–12 (194.00–217.38)
- **Problem:** "No knight should be without his sword" (198.65–200.11) is cut to "sword." because 11 starts at 199.83. Segment 11 also runs 5.7s on "no usable word boundary", which isn't true. Segment 12 is `panel_hosts_only`, which mutes "it's also solid silver, so don't lose it" (210.03–212.69). That line sets up the ending (the "silver letter opener payoff" fans item) and Megan's silver rule.
- **Fix:** Trim 10 to 194.00–196.24. Set 11 to 198.40–200.36, the whole line. Split 12 into `panel` 207.82–212.79 (the silver line with our "Is it a letter opener?" over it; 4.97s, justified) and `panel_hosts_only` 212.79–217.38 ("I thought it was a sword...").

### 3. [should-fix] The house explosion falls in a skip, in a small panel
- **Where:** segments 703–705 (6079.00–6096.10)
- **Problem:** Frames show Wells flicking the lighter at 6081, a white flash at 6082 and the house blowing apart from 6083 to 6089. Segment 703 ends at 6081.40 and 704 starts at 6085.40, so the blast itself is skipped. What's left is in `panel`, even though it's the biggest visual payoff in the film. Our "Oh" (6082.89) also falls in the gap.
- **Fix:** Set 703 to `pip_circles` 6079.55–6083.55 (lighter, flash, blast, our "Oh") and 704 to `pip_circles` 6085.60–6088.60. Turn 705 into `panel` to hold the pip share.

### 4. [should-fix] Two famous closing lines are clipped
- **Where:** segment 686 (5952.77–5956.02) and segment 724 (6215.09–6216.03)
- **Problem:** Segment 686 starts at "And we don't fucking go!". The "We go together or" half (about 5951.7 per the no-VAD pass) is cut, and the segment carries muddled filler after it. Segment 724 is 0.94s of "is now." The whole line is "I think it's all over... it is now" (6212.2–6215.98). It's Cooper answering Ryan's "They think it's all over" (4717, which is in the cut), and it's the film's last spoken payoff.
- **Fix:** Set 686 to 5951.43–5953.97 and drop 687 ("Fuck is for", 5.6s of filler). Set 724 to `pip_circles` 6211.93–6216.03, and move 725's start to 6218.30.

### 5. [should-fix] "She knows him for sure" comes before the look it's about, and the farmhouse line is muted
- **Where:** segment 239 (2210.39–2227.84, `panel_hosts_only`, 17.45s)
- **Problem:** Frames show Megan glancing back at Ryan and Ryan's close-up from 2206.5 to 2210. That look is in the 19.5s skip before 239, so our call has no event. Segment 239 also mutes "There's only one farm in this glen, but the owners are friends. We can take your men there." That line is the only setup for the farmhouse, and it's Megan's lie. The segment is also 12s of silence between two short lines.
- **Fix:** Replace 239 with four segments:
  - `panel` 2205.68–2210.39: the look, under "...before we can take him too far"
  - `panel_hosts_only` 2210.39–2212.25: "she knows him for sure"
  - `panel` 2212.25–2215.80: "but the owners are friends. We can take your men there."
  - `panel_hosts_only` 2224.14–2227.84: "Why do you think she knows him..."

### 6. [should-fix] Megan's werewolf rules are muted and "the eyebrows thing is nonsense" is missing
- **Where:** segments 346–347 (3214.20–3220.91) and 352 (3258.48–3259.56)
- **Problem:** Segment 347 mutes "full moon, silver bullets, and eyebrows that join in the middle?" (3215.81–3218.97) under our "it's silver bullets". Segment 352 is a bare "Just blood." and skips "The eyebrows thing is nonsense. It's just dark-age paranoia." (3261.39–3264.27). Both lines are on the fans list.
- **Fix:** Set 346 to 3214.62–3219.06 (4.44s, justified as one line) and 347 to 3219.06–3220.91. Set 352 to `pip_circles` 3261.14–3264.52.

### 7. [should-fix] Megan's reveal stops short of "It's that time of the month"
- **Where:** segments 626–627 (5521.49–5530.00)
- **Problem:** The line is at 5525.71–5527.21, between 626 (ending 5524.88) and 627 (starting 5528.28). It's named on the beat sheet.
- **Fix:** Set 626 to 5523.30–5527.46 ("I just unlocked the door. It's that time of the month."; 4.16s, justified). Drop 627, a wordless 1.7s pip that would otherwise sit inside the 2s skip.

### 8. [should-fix] Over-4s runs whose reasons don't hold
- **Where:** 7 (4.9s), 11 (5.7s), 55 (5.6s), 82 (4.6s), 85 (5.1s), 95 (4.3s), 287 (5.7s), 381 (5.3s), 533 (5.6s), 687 (5.6s)
- **Problem:** Each says either "no usable word boundary near 4s" or "the film's line finishes just past 4s". The transcript shows usable boundaries in every case, and most cover throwaway or garbled text ("then. I've got 0730", "it. I'll make you okay. Got", "aren't we, Cooper? I believe this.", "Fuck is for"). Segment 85 holds a 3.3s dead pause.
- **Fix:**
  - 7 → 172.17–174.21
  - 82 → 940.95–943.47
  - 85 → 962.85–963.83 (ends on the "Castration." punchline)
  - 95 → 1036.64–1039.76
  - 532 → 4737.66–4741.58 ("You just can't get past the dog, can you? We're losing, Ryan.")
  - 533 → 4744.30–4746.82 ("At the very least, I wanna even the score.")
  - Drop 55, 287, 381 and 687.
  - Segment 11 is handled in finding 2.

### 9. [should-fix] Sub-second fragments and clipped words
- **Where:**
  - Our mumbles: 5 ("film"), 138 ("Yeah"), 143 ("people."), 408 ("sleeping here."), 676 ("Are"), 721 ("With")
  - Film shards: 20 ("Seven"), 47 ("All"), 110 ("unlucky."), 252 ("there, Cooper?"), 355 ("Right."), 467 ("You what?"), 469 ("Stay."), 479 ("Stids!"), 525 ("It's gone."), 576 ("Somewhere")
  - Clipped line: 280 ("that plan.")
- **Problem:** These are leftovers of the chunker hitting a word boundary at the wrong moment, usually 0.6–1.2s long. They read as glitches rather than cuts.
- **Fix:** Drop all of them except 280. Restore 280 to "I put the kibosh on that plan." (2588.67–2590.95).

### 10. [should-fix] Our recap plays over the start of the woods attack
- **Where:** segments 178–180 (1809.78–1828.83) and 236 (2176.45–2177.91)
- **Problem:** The `near_misses` list says "I'm on this practice exercise... wiped out their camp" was cut as narration, but the chunker put it back in as `panel` over dark running footage (frames 1809–1827). Segment 236 is the half-sentence "The they're" over film.
- **Fix:** Drop 178–180 and 236, and update `near_misses`.

### 11. [should-fix] The "Spider women" joke loses its pause
- **Where:** segments 88–89 (982.36–990.78)
- **Problem:** "Spiders. And women." (ends 986.09) → a 4s pause → "Spider women." (990.17). The 3.6s skip cuts the joke's beat.
- **Fix:** Insert a `panel_hosts_only` bridge at 986.34–989.92. The picture is held and the film is muted, which is silent at that point anyway. This keeps the timing and still counts as a break.

### 12. [consider] Long action stretches are cut on a timer
- **Where:** for example 639–680 (the kitchen, 40 chunks), 499–523 (the Land Rover escape), 382–392 and 394–402 (the first assault)
- **Problem:** The wordless action is covered by 1.5–4s chunks with 2–10s skips that repeat the same length cycle. The frame spot checks found the key images inside the chunks (Bruce, Wells' guts, the pan fight), so nothing is lost, but it doesn't cut on motivation.
- **Fix:** Left alone. Re-placing ~200 wordless chunks on picture is a re-cut, not a review fix. If the timeline reads as robotic in Resolve, the first place to rework is the kitchen fight.

### 13. [consider] The intro never says we haven't seen it
- **Where:** segment 1 (70.26–86.20)
- **Problem:** "I watched the trailer..." implies it, and the next sentence ("So we are gonna see if I was totally wrong", 86.4–93) would say it, but it would push the intro to about 23s.
- **Fix:** Left alone. It's under 20s and the pitch lands.

### 14. [consider] "There is no spoon"
- **Where:** 5912.56–5914.52, next to segment 681
- **Problem:** The no-VAD pass hears the Matrix line just before "Spoon! No!". The VAD transcript only has "The spoon.", so it isn't verified.
- **Fix:** Added to `near_misses`. Check it by ear before extending 681.

Passes with nothing further:
- **Missed peaks:** every strong reaction is in. That includes Grey's Anatomy (1978–2013), "Get to the Jeep" (2077–2090), "how big is that friggin thing" (2129), "That was intense" (2172), "Oh my god" (3766), "There's more than one" (4378) and "I just ripped his head off" (4453).
- **Running bits:** the sword, Ryan-turns, Megan-knows-Ryan (including the "I said that already" squabble) and the Thing-plus-Werewolf verdict all have setup, middle and payoff in the cut.
- **Layout:** apart from finding 3, no `_hosts_only` segment mutes a needed line other than the ones in findings 2, 5 and 6.

## Hook

The cutter's hook is 2076.67–2090.53, "Get to the Jeep... He's a werewolf driving the Jeep". I agree with it: it's our biggest spoken peak, it's on a `must` beat, and it's fullscreen.

Runner-up: Joe's death, 4437.0–4457.5. The werewolf drags him from the back seat in silence, then we say "Eating somebody. Oh, I just ripped his head off."

## Changes applied

All edits were made by `.tmp_ds/rev/fix.py`, which reads `cuts/dog-soldiers.draft.json` and writes `cuts/dog-soldiers.json`. Segment numbers below are from the draft.

- **Finding 1:** 656 → `pip_circles` 5752.80–5757.44; 657 → 5759.60–5762.40.
- **Finding 2:** 10 → 194.00–196.24; 11 → 198.40–200.36; 12 → `panel` 207.82–212.79 + `panel_hosts_only` 212.79–217.38.
- **Finding 3:** 703 → `pip_circles` 6079.55–6083.55; 704 → `pip_circles` 6085.60–6088.60; 705 → `panel`.
- **Finding 4:** 686 → 5951.43–5953.97; 687 dropped; 724 → `pip_circles` 6211.93–6216.03; 725 → starts 6218.30.
- **Finding 5:** 239 → four segments: 2205.68–2210.39 `panel`, 2210.39–2212.25 `panel_hosts_only`, 2212.25–2215.80 `panel`, 2224.14–2227.84 `panel_hosts_only`.
- **Finding 6:** 346 → 3214.62–3219.06; 347 → 3219.06–3220.91; 352 → 3261.14–3264.52.
- **Finding 7:** 626 → 5523.30–5527.46; 627 dropped.
- **Finding 8:** 7, 82, 85, 95, 532 and 533 trimmed as listed; 55, 287 and 381 dropped.
- **Finding 9:** 5, 20, 47, 110, 138, 143, 252, 355, 408, 467, 469, 479, 525, 576, 676 and 721 dropped; 280 → 2588.67–2590.95.
- **Finding 10:** 178, 179, 180 and 236 dropped; `near_misses` updated.
- **Finding 11:** a `panel_hosts_only` bridge was inserted at 986.34–989.92.
- **Knock-on fixes:**
  - Dropping the muted fragments merged eight `panel` streaks past 4. Each was broken by dropping the shortest wordless panel chunk in it: 143.50, 470.48, 496.00, 1451.91, 1470.01, 3750.71, 4251.70, 4356.94, 5859.40, 5867.80, 5889.43 and 6201.80.
  - Seven filler "breaking up a run of panel" pip chunks went back to `panel` to keep pip under 15% without creating layout patterns: 711.37, 778.88, 1721.86, 2481.50, 2836.79, 3344.11 and 4191.53.
  - 111 → starts 1172.60, to break a run of three ~1.5s segments.
- `hook` is unchanged; `near_misses` gained the woods recap and "There is no spoon".

**Left alone:**
- Finding 12 (timer rhythm): fixing it would be a re-cut.
- Finding 13 (intro): it's under 20s and the pitch lands.
- Finding 14 ("There is no spoon"): unverified, so it went into `near_misses`.
- Three new segment boundaries sit off the VAD word list and the checker warns about them: 5752.80 and 5951.43 are anchored on the no-VAD whisper pass, and 6079.55 is anchored on frames.
- Segments 406, 420 and 517 (film chunks with a half-sentence of ours over them) are minor and stay.

**After:**
- Segments: 737 → 705
- Runtime: 38.7 → 37.4 min
- panel: 60.3% → 60.0%
- `_hosts_only`: 20.1% → 19.9%
- pip_circles: 14.5% → 14.7%
- hosts_full: 5.1% → 5.3%
- Over-4s film runs: 16 → 11, each with a reason that holds
- Checker: 0 FAIL. Remaining WARNs are the over-4s runs and the three boundaries off the VAD word list described above.
