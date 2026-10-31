# Child's Play (1988) — research & beat sheet

Offset: film starts at **92.05s** in the reaction recording (`Watch Childs Play.mov`).
Times below are **recording time** (film time + 92.05).

## Corrections from the `--no-vad` pass (added at the cut stage)

`Childs Play (1988).novad.words.json` now exists and fills most of the holes
listed below. Where it disagrees with an estimated (`~`) time in this sheet,
it wins. It also hallucinates over music ("Okay.", "Chucky.", "No!", "Ha, ha",
"Thank you." repeated), so ignore runs of one repeated word. Located lines, in
recording time:

| line / moment | recording time |
|---|---|
| "Eddie! Don't leave me!" | 173.7–178.2 |
| "Oh God, I'm dying" / "I'm gonna get you ... and I'm gonna get Eddie" | 279.1 / 293.5–299.3 |
| "I gotta find somebody" | 314.6–319.9 |
| Opening chant ends "...I beg of you!"; lightning hits the store; explosion (picture-checked at review) | 372.6–375.3; 411.5; 415.5–420.5 |
| "Hi, I'm Chucky, and I'm your friend to the end. Hidey-ho!" | 936.8–941.6 |
| "I'm scaring myself half to death" | 1491.9–1496.9 |
| **Hammer hit**; through the window; hits the truck (picture-checked at review; the `Ah!` at 1522.9 is Karen's bus, not the hit) | **1499.0**; 1502.2–1502.9; 1509.4 |
| "His real name is Charles Lee Ray ... sent down from heaven by daddy" | 1926.3–1935.3 |
| "Maggie was a real bitch and got what she deserved" | 1944.1–1948.8 |
| "I have to go tinkle" | 2234.6–2236.4 |
| Station: "friend to the end. Hidey-ho" | 2532.1–2536.8 |
| **"Hi, I'm Chucky. Wanna play?" (head turn)** | **2709.9–2712.7** |
| **"You stupid bitch! You filthy slut! ..."** | **2803.8–2809.1** |
| "I won't do you any good, Mikey! You can't hurt me!" (car) | 3467.4–3472.1 |
| "You're turning human" | 3697.6–3699.9 |
| "I have a date with a six-year-old boy" | 3805.2–3809.4 |
| "Ugly doll." / "Fuck you." | 4234.4–4239.3 |
| Second chant; "Give me the power, I beg of you!" | 4400.2–4416.0; 4421.4–4424.2 |
| **"We're friends to the end. Remember?" / "This is the end, friend."** | **4616.9–4622.2** |
| "Hello, Andy." (burnt Chucky) / "Give me the boy and I'll let you live" | 4721.5 / 4735.6–4741.2 |
| "Shoot him in the heart!" | 5003.9–5009.3 |
| "Hi, I'm Chucky. Wanna play?" (dying) | 5035.4–5038.5 |

So two beat ranges below are off: **Maggie's death is ~1488–1517** (not
1454–1537; our "Oh, no. Oh, no." at 1455 is the end of the phone call; Karen's
bus arrives at 1517), and
**the burn is ~4605–4681** with the line at 4617–4622 (not 4650–4665). The
three lines quoted "from memory" are confirmed by this pass, except the first
is "We're friends to the end. Remember?".

## Transcript notes

Only the default VAD pass exists (`Childs Play (1988).words.json`, 3,105 words
for an 87-minute film). There is no `.novad.words.json`. The film transcript is
badly holed wherever the score or effects carry the scene, and those holes sit
on most of the set pieces. **A `--no-vad` pass would help a lot**
(`python src/transcribe.py --project cuts/childs-play.media.json --no-vad`).

Holes in the film transcript, in recording time:

| recording time | what the film has there | anchored on instead |
|---|---|---|
| 98–529 | Opening chase, toy store, Ray's dying threats, the voodoo chant, explosion, titles, Andy's breakfast | our lines 134–419 and the film echo "gotta / find somebody" in our transcript at 302–321 |
| 1166–1415 | Maggie stalked around the apartment (mostly wordless) | "Andy?" 1275; our "chair in front of the door" 1353 |
| 1454–1552 | Hammer hit and Maggie's fall | "I'm ... scaring myself" (transcript splits it: "I'm" ~1453, "scaring myself" 1495); our "Oh, no. Oh, no." 1455 |
| 2097–2444 | Andy skips school, the El, Eddie Caputo's hideout, the gas explosion | our lines 2135–2431 |
| 2647–2782 | Batteries fall out of the box, the empty compartment, the head turn | our "so creepy ... clown vibe" 2697; "feel like an absolute crazy person" 2757 |
| 2808–2905 | Chucky comes alive in Karen's hands, bites her, runs | "or else I'm gonna throw you in the fire" 2800; our "I would have shit my pants" 2847 |
| 3290–3624 | Chucky attacks Norris in the car; start of the scene at Ray's apartment | our lines 3329–3455 |
| 3931–4150 | The whole hospital sequence and Dr. Ardmore's death | our lines 3912–4147 |
| 4239–4401 | Andy waits with the bat, gets knocked out | our "Where's the bat?" 4288 |
| 4480–4681 | Apartment fight and the fireplace burn | our lines 4504–4674 |
| 4686–4888 | Burnt Chucky's return, Karen shooting him apart | our lines 4698–4840 |
| 4986–5037 | The body attacks Jack, the heart shot | "I told you not to touch it" 4962; "wanna play" 5037 |

Misheard or missing famous lines:

- **"Hi, I'm Chucky, and I'm your friend till the end. Hidey-ho!"** is in as
  "hi Oh / Chuckie and I'm your friend to the end" 930–938. "Hidey-ho" itself
  is only caught later, at the station, as "Heidi ho" 2536.
- **"Hi, I'm Chucky. Wanna play?"** on the head turn (batteries scene) is
  **missing**. The transcript has it only as "wanna play" 995 (Chucky to Andy
  at the TV) and as the dying "wanna play" 5037.
- **"Ade due Damballa. Give me the power, I beg of you!"** The opening chant is
  missing entirely. The second chant, over Andy, is in as "Dembella" 4401 /
  "give me the power I beg" 4421.
- **"You stupid bitch! You filthy slut! I'll teach you to fuck with me!"** is
  missing (sits just after 2807).
- **"This is the end, friend."** is missing (sits around 4650–4665).
- **"Ugly doll." / "Fuck you."** is in as "like doll fuck you" 4235–4239.
- "Good Guy doll" is heard as "good guy dog" 546; "Barclay" as "Barkley" or
  "sparkly"; "Criswell" as "Chris well"; "Wabash" as "wall bash"; "Aunt Maggie
  was a real bitch" loses its first words ("that night he was a real bitch").
- Three lines quoted below ("You stupid bitch...", "We're friends till the
  end, remember?", "Give me the boy and I'll let you live") are from memory of
  the film. The web sources confirmed the scenes but not that exact wording, and
  the transcript has none of them, so check them against picture before
  putting them on screen.

Film echo in our transcript: "Okay, gotta" 302 / "find somebody" 321 is Ray's
"I gotta find somebody", not us. "Get me out of here" 3912 is likely Andy in
the hospital cell.

Times in rows marked `~` are estimated from our commentary and the edges of
the surrounding dialogue, not from film dialogue.

## Sources

- [Wikipedia: Child's Play (1988 film)](https://en.wikipedia.org/wiki/Child%27s_Play_(1988_film)): plot in order, deaths, production trivia (nine puppeteers, Kevin Yagher, Ed Gale in the suit, Brad Dourif, the Manson / Oswald / Ray name, the "Blood Buddy" script where Andy might be the killer), release and controversy.
- [SlashFilm: How One Iconic Scene In 'Child's Play' Rewrote The Movie's Rules](https://www.slashfilm.com/572116/scariest-scene-in-childs-play/): the batteries scene as the film's defining moment, and why (it ends the "is it Andy?" ambiguity).
- [SYFY Wire: Chucky's 5 scariest movie moments](https://www.syfy.com/syfy-wire/chucky-scariest-scenes-ever-childs-play): three scenes from the original: Maggie and the hammer, burnt Chucky, the batteries.
- [Strange Harbors: Revisiting 1988's Child's Play](https://strangeharbors.com/blog/2019/6/20/revisiting-1988s-childs-play): soul transfer, the Maggie stalking sequence, the battery discovery ("the most skin-crawlingly iconic scare of the series").
- [Wikiquote: Child's Play (1988 film)](https://en.wikiquote.org/wiki/Child%27s_Play_(1988_film)): wording of the famous lines ("sent down from heaven by daddy", "I have to go tinkle", "This is the end, friend", "I gotta find somebody").
- [Favorite things about Child's Play (The Motion Pictures)](https://themotionpictures.net/2012/11/12/favorite-things-about-childs-play/): search hit confirming the elevator "Ugly doll" exchange, "a date with a six-year-old boy" and "This is the end, friend" as fan favourites.
- [Headhunter's Horror House wiki: Child's Play](https://headhuntershorrorhouse.fandom.com/wiki/Child%27s_Play): search hit for the full "friend till the end. Hidey-ho!" wording.
- Not reachable (403 / 402): Bloody Disgusting's 35th anniversary piece and the Child's Play fandom wiki.

## What fans come for

- **The batteries scene / "Hi, I'm Chucky. Wanna play?"**: named by every source as the scene; the film's turn from "is it the kid?" to a living doll. The head rotating with no batteries in him is the image.
- **"You stupid bitch!" — Chucky comes alive in Karen's hands**: the payoff seconds later; first time we see him fully animated and hear Brad Dourif let rip.
- **Maggie, the hammer and the window**: the first kill and the franchise's best-known jump scare; the long stalk before it is singled out for its staging.
- **The soul transfer in the toy store**: the origin. Dying strangler, voodoo chant, lightning, "Ade due Damballa".
- **"Hi, I'm Chucky, and I'm your friend till the end. Hidey-ho!"**: the catchphrase, on Andy unwrapping him.
- **"Aunt Maggie was a real bitch and got what she deserved."**: a six-year-old relaying it deadpan; also where Andy learns the name Charles Lee Ray, which is why Chucky needs him later.
- **Burnt Chucky**: the melted doll that keeps coming with a knife, then gets shot apart piece by piece and still keeps coming.
- **"This is the end, friend."**: Andy's line as he drops the match.
- **"Ugly doll." / "Fuck you."**: the elevator gag; the film's best laugh.
- **"I have a date with a six-year-old boy."**: the Dr. Death scene, where the rules are laid out (he's turning human, he must take Andy, the heart is the weak spot).
- **The car attack on Norris**: knife through the seat, the car on its roof, and Chucky finding out he can bleed.
- **Dr. Ardmore and the electroshock machine**: the nastiest kill.
- **The effects**: full animatronic puppet run by nine puppeteers, with Ed Gale in a suit on oversized sets for the walking and burning shots. The doll's face gets more human as the film goes on (we spot this at 3823).
- **The "is it Andy?" thread**: the script's original idea; the first half keeps the footprints, the hammer and the trip to Caputo's pointing at the kid.

## Beat sheet (film order)

| rank | beat | recording time | anchor |
|---|---|---|---|
| strong | Opening chase: Norris runs down Charles Lee Ray through the streets; Eddie Caputo drives off and leaves him | ~92–245 | our "it's right into it police chase" 134; our "You think he's a cop though?" 161 |
| **must** | Toy store: shot and dying, Ray swears revenge on Norris and Eddie, chants his soul into a Good Guy doll; lightning, the store blows up | ~245–400 | not in film transcript. Our "bad guy soul goes into the doll" 250; film echo "gotta / find somebody" 302–321; our "all the toys done, no more toys" 410–419 lands just after the explosion |
| optional | Titles; Andy makes his mum breakfast in front of the Good Guys cartoon | ~400–529 | our "It's like a Chucky cartoon" 495; our "three megas in toast" 510 |
| strong | The Good Guy doll TV advert: three sentences, turns its head, blinks | 529–600 | "we've got a very important Good Guy message just for you" 529; "say three different sentences, we even turn our heads" 547–555; our "toast is burning" 570 |
| strong | Andy's birthday: he hopes the big box is a Good Guy and gets clothes | 645–757 | "how many years old are you today" 674; "I want a Good Guy to go with it" 747; our "you think you're getting one present and you're getting clothes" 722 |
| strong | Maggie tips Karen off; they buy the doll from a peddler in the alley for $30 | 765–832 | "there's a peddler in the alley behind the store" 771; "50 bucks" 804; "may bring you and your kid a lot of joy" 818; "how do we know the damn thing isn't stolen" 820 |
| optional | Criswell makes Karen work the late shift on Andy's birthday; Maggie offers to babysit | 842–892 | "are you happy with your job here" 875; our "a jerk" 875 |
| **must** | Andy unwraps Chucky: "Hi, I'm Chucky, and I'm your friend till the end" | 902–954 | "this isn't groceries" 909; "show me how he works" 930; "Chuckie and I'm your friend to the end" 938 |
| strong | News flash that Eddie Caputo has escaped; "Chucky wants to watch the 9 o'clock news"; Maggie puts Andy to bed | 975–1062 | "Eddie Caputo reputed accomplice of Charles Lee Ray has just escaped" 975; "wanna play" 995; "Chucky wants to watch the 9 o'clock news" 1001–1017 |
| strong | Maggie finds Chucky sat in front of the news and blames Andy; "I didn't put Chucky in front of the TV" | 1103–1170 | "what did Chucky do, walk into the living room and turn it on all by himself" 1144–1150; our "Chucky's an old man and watches the news" 1104 |
| strong | Maggie stalked: noises, something running past, the empty chair, her phone call with Karen | 1170–1454 | "Andy?" 1275; our "chair in front of the door" 1353; "how's it going, how's Andy" 1415; "a bit of the alone-at-night willies" 1427–1435 |
| **must** | Maggie's death: "I'm scaring myself", the hammer to the face, out of the kitchen window onto the truck | ~1454–1537 | "scaring myself" 1495 (transcript timing is shaky here); our "Oh, no. Oh, no." 1455; ends before our "how is she able to squeeze her way through" 1538 |
| strong | Karen comes home to police; Norris introduces himself; tiny footprints on the counter; he checks Andy's feet, then we see Chucky's sneakers | 1537–1832 | "I'm detective Mike Norris, homicide" 1594; "Miss Peterson's dead ... she fell from your kitchen window" 1628–1640; "very small footprints" 1671; "I've just lost my best friend tonight" 1741; our "Look at Chucky's sneakers" 1776 |
| optional | Norris orders the autopsy and bags the toy hammer | 1832–1862 | "possible murder weapon" 1857; our "tiny little hammer" 1859 |
| **must** | Andy caught whispering to Chucky: his real name is Charles Lee Ray, sent down from heaven by daddy; "Aunt Maggie was a real bitch and got what she deserved"; Karen insists he's only a doll | 1865–2030 | "who are you talking to" 1896; "his real name / and he's been sent down from heaven by daddy" 1919–1930; "a real bitch and got what she deserved" 1945; "Chuckie is a doll, he's made of plastic" 1964 |
| optional | Next morning, off to school: "Chucky's only a doll, right?" | 2081–2097 | "no bad dreams about aunt Maggie" 2081; "off to school with you" 2093 |
| strong | Andy skips school and rides the El with Chucky to a derelict street; "I have to go tinkle" | ~2097–2390 | no film dialogue. Our "The school just let the kid leave" 2135; our "where the hell he's going" 2222; our "gonna go tinkle" 2252 |
| strong | Eddie Caputo's hideout: Chucky turns on the gas, Eddie fires and the house blows up; Andy found at the scene | ~2390–2444 | no film dialogue. Our "sleep with a gun" 2303–2307; our "Don't run towards the gunshots" 2320–2375; our "Where the hell is the kid?" 2431 |
| strong | Police station: Andy says Chucky did it, Karen begs the doll to talk, it only says "Hidey-ho"; Dr. Ardmore takes Andy to the psychiatric ward | 2444–2562 | "do you have any idea why your aunt Maggie fell out of that window" 2461; "they're going to take you away from me" 2496; "Heidi ho" 2536; "my name is Dr. Ardmore, I'm from County General" 2546; our "She had to leave him" 2560 |
| strong | Karen home alone with the doll: "Say something, you little bastard"; it only gives its stock lines | 2585–2650 | "something you little bastard / say something damn it" 2594–2599; "hi I'd like to be hung [hugged]" 2600; "wants you for a best friend" 2647 |
| **must** | The batteries: they drop out of the box, she opens the empty compartment, the head turns: "Hi, I'm Chucky. Wanna play?"; she drops him and he rolls under the sofa | ~2650–2782 | **line missing from transcript.** Sits between "wants you for a best friend" 2647 and "talk to me damn it" 2782; our "so creepy ... clown vibe" 2697–2703; our "makes me feel like an absolute crazy person" 2757 |
| **must** | She threatens the fireplace and Chucky comes alive: "You stupid bitch! ... I'll teach you to fuck with me!"; bites her arm, runs for the lift | 2782–2905 | "talk to me damn it" 2782; "or else I'm gonna throw you in the fire" 2800–2806; outburst itself missing (~2807–2830); our "I would have shit my pants" 2847 |
| strong | Karen tells Norris; he doesn't believe her even with the bite mark | 2905–2980 | "Chucky is alive and he killed Eddie Caputo" 2908; "moving and talking for days without any batteries in him" 2917; "Chucky bit me" 2951 |
| strong | Karen tracks down the peddler, he attacks her, Norris pulls him off; the doll came from the burnt-out toy store; Norris admits he killed Ray there | 3072–3197 | "a burnt-out toy store on Wabash" 3128–3133; "it was struck by lightning the night that Charles Lee Ray died" 3170–3175; "I was the man who killed him" 3179 |
| optional | In the car: "Chucky is Charles Lee Ray"; 730 Stony Island; "I'm a loose end"; Norris drives off | 3197–3290 | "I found out that Chuck is Charles Lee Ray" 3220–3227; "Chuckie killed Caputo, that leaves you" 3256; "you said you didn't like loose ends" 3280 |
| **must** | Chucky attacks Norris from the back seat: strangling, knife through the seat, car flips; Norris shoots him and he bleeds | ~3290–3530 | no film dialogue. Our "Chuckie's in that frigging car" 3329; our "Jesus Christ" 3399; our "Get the fuck out of the car man" 3406; our "a little harder now that he's upside down" 3455 |
| optional | Karen at Ray's apartment with the voodoo wall; Norris turns up a believer, with Ray's file and a photo of John | 3530–3645 | our "She wasn't crazy" 3529; our "quite the mural" 3551; "his nickname was Chuckie" 3630; "find him before Chuckie does" 3643 |
| **must** | Chucky and John ("Dr. Death"): getting shot hurt and bled; he's turning human; voodoo-doll torture; he must take the first person he told, Andy | 3645–3817 | "hello John" 3653; "it hurt like a son of a bitch, it even bled" 3685–3693; "you're an abomination" 3719; "I'm gonna be six years old again" 3799; "I have a date with a six-year-old boy" 3808 |
| **must** | Dying John tells Karen and Norris how to kill him: stop the chant; "his heart is almost human ... through the heart" | 3817–3900 | "you must stop him before he can say the chant" 3874; "hard [heart] is almost human" 3886; "it's the only way, through the heart" 3890 |
| strong | Hospital: Andy sees Chucky coming and nobody listens; Chucky gets in; Andy fools him and slips out of the cell | ~3900–4050 | almost no film dialogue. "Get me out of here" 3912 (echo); our "like doll hand" 3982; our "an action superstar" 4053 |
| strong | Dr. Ardmore grabs Andy to sedate him; Chucky stabs him with the scalpel and fries him with the electroshock headset | ~4050–4150 | no film dialogue. Our "sharp scalpel" 4065; our "Go for his little Chucky heart" 4071; our "he's electro shocking him" 4119–4134; our "holy crap" 4147 |
| optional | Karen and Norris at the hospital: Ardmore "fried to a crisp"; Andy will have gone home | 4150–4192 | "fried to a crisp with the electric shock machine" 4155; "he'd go home" 4190 |
| strong | Lift gag: the old couple leave the doll behind. "Ugly doll." "Fuck you." | 4215–4242 | "some child left their doll on the elevator" 4224; "like [ugly] doll / fuck you" 4235–4239 |
| **must** | Andy waits with the bat; Chucky knocks him out and starts the chant over him; storm gathers; Karen and Norris burst in | ~4242–4440 | our "Where's the bat?" 4288; "Dembella" 4401; "give me the power I beg" 4421; our "thunder storm / lightning" 4420–4423; our "the cop's like oh no, not again" 4429 |
| strong | Apartment fight: Chucky stabs Norris, goes for Karen and Andy, is bundled into the fireplace | ~4440–4640 | film transcript garbled (chant tail 4435–4455). Our "He's like possessed" 4504; our "How hard can you hit him with that little bat" 4543; our "He's going nuts" 4598 |
| **must** | "We're friends till the end, remember?" "This is the end, friend." Andy drops the match and Chucky burns | ~4640–4681 | **line missing from transcript.** Sits between our "now there's gonna be a fire" 4643 and "first aid kit under the kitchen sink" 4681; our "He's not dead, no chance he's dead" 4674 |
| **must** | Burnt Chucky: the fireplace is empty; the melted doll chases Andy with a knife; Karen shoots off head, arm and leg; "Give me the boy and I'll let you live" | 4681–4888 | "first aid kit under the kitchen sink" 4681; "Chuckie's dead" 4686; our "No, he got up" 4698; our "You gotta go for the heart" 4749; our "one leg" 4840 |
| strong | Jack arrives and won't believe it: "the kid was right, the doll's alive"; he picks up the head anyway | 4888–4965 | "I got a cop down here, multiple stab wounds" 4888; "the kid was right, the doll's alive" 4894–4900; "there's no way this thing is alive" 4958; "I thought I told you not to touch it" 4962 |
| **must** | The body bursts out and strangles Jack; Norris shoots it through the heart; the head winds down: "Hi, I'm Chucky. Wanna play?" | ~4965–5042 | "Chuckie" 4986; "wanna play" 5037; our "it's gonna be like hi I'm Chucky" 4928 called it a minute early |
| strong | Ending: "Now who's gonna believe me?"; they leave, Andy looks back at what's left of Chucky; freeze frame | 5042–5075 | "now what [who] is gonna believe me" 5052–5057; our "a little love romance with these two" 5069 |

## Our running dynamic

- **She's been scared of Chucky since she was a kid (four older brothers, "I just wanted my Barbies")**: set up at 13–24 and 103–108, "creeps me out" 217, "So glad we're watching this right before you go on a business trip" 1387, "Don't want to look at him" 1980, flips to "I remember being so scared of it, now it just looks funny" 4356, then back to sweaty hands 5115 and "no dolls in the room" 5193.
- **Goofy or intense?**: "so funny-looking" / "I'm sure it's not funny to the kid" 4356–4368, paid off in the wrap-up, "It was goofy, but super intense" / "I don't think it was goofy" 5128–5147.
- **Calling the premise before it happens**: can't tell which man is the cop 161–196, then "bad guy soul goes into the doll ... I think that's the premise" 250–257, a minute or so before the chant.
- **"Go for the heart"**: "Go for his little Chucky heart" 4071 (hospital), "It's his heart, you gotta go for the heart" 4749 (burnt Chucky), paid off by the heart shot ~5000.
- **Late prediction that lands**: "I was gonna touch him and it's gonna be like hi I'm Chucky" 4928, and the head says exactly that at 5037.
- **How big the doll is**: "It's like the size of the kid" / "big enough to do some damage" 1039–1056; "Everything's like miniature in this movie" 4297.
- **Biggest reaction peak:** the car attack, 3329–3455: "Chuckie's in that frigging car" 3329, "Jesus Christ" 3399, "Get the fuck out of the car man" 3406, "it's a little harder now that he's upside down" 3455. Close second is Ardmore's death, 4119–4147: "Oh my goodness. Oh my gosh, he's electro shocking him ... holy crap." Judged from the words only; our transcript is sparse (1,831 words) and drops gasps and screams, so check the waveform around Maggie's fall (1410–1537) too.
