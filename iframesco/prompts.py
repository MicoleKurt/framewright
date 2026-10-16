"""Prompt templates for the local writer model. The retention framework (docs/RESEARCH.md):

  cold open (most dramatic true moment, no greeting)  0-15 s
  promise   (what the viewer will understand)          15-25 s
  stakes    (why it mattered / what was at risk)       25-40 s
  chapters  (each ends on an open loop into the next)
  payoff    (answers the cold open) + one-line bridge to the next video

Small local models drift into clichés and invented numbers, so every prompt pins them to the
source text and bans the usual filler.
"""

BANNED_WORDS = ["fascinating", "journey", "delve", "tapestry", "testament", "in a world", "buckle up",
                "little did", "game-changer", "unleash", "dive in", "let's dive", "welcome back",
                "in this video", "subscribe", "smash that", "human spirit", "resilience", "stood the test of time",
                "forever changed", "rich history", "it's important to note"]

STYLE = """Style rules:
- Spoken documentary narration: calm, concrete, vivid. Short sentences mixed with longer ones.
- Every claim must come from SOURCE. Never invent dates, numbers, quotes or names.
- Concrete details beat adjectives: a place, a year, a person, an object.
- No greetings, no "in this video", no calls to subscribe, no questions to the viewer, no exclamation marks.
- Plain narration only: no headings, no labels like "Promise:" or "Chapter 1", no lists.
- Never use these words: """ + ", ".join(BANNED_WORDS) + "."

# ---------------------------------------------------------------- Shorts
# Written for 7-8B local models: one job per prompt, numbered hard limits, a worked example to copy
# the *shape* (not the facts) from, and a self-check list the model reads last.

SHORT_EXAMPLE = """Example of the shape (different subject; copy the structure, never these facts):
Everyone knows the Wright brothers flew. Few know they were bicycle mechanics with no college degrees.

In 1896 Orville and Wilbur Wright ran a small bicycle shop in Dayton, Ohio. They read every paper on flight they could find.

By 1900 they were testing gliders on the windy dunes of Kitty Hawk. The first ones barely lifted off the sand.

The published lift tables were wrong. So in 1901 they built their own wind tunnel and tested two hundred wing shapes.

On December 17, 1903, their engine plane flew for twelve seconds. Everyone knows how their story ends. This is how it started."""

SHORT_NARRATION = """You write narration for a 40-second YouTube Short about how a famous person or thing STARTED.

SUBJECT: {topic}

SOURCE (the only facts you may use):
{facts}

{example}

Write exactly {n} paragraphs separated by blank lines.
Hard limits:
1. 18 to 28 words per paragraph, 1 or 2 sentences. About 120 words in total.
2. Paragraph 1 is the HOOK. Sentence one is 12 words or fewer and names the subject plus a surprising,
   true contrast between the famous end and an unknown beginning. Do not resolve it.
3. Paragraph 2 jumps back in time and opens with a year from SOURCE ("In 1939, ...").
4. Every paragraph contains at least one concrete detail from SOURCE: a year, a place, a person or a number.
5. The middle paragraphs move forward in time: first setback, first win, the turning decision.
6. The last paragraph is the payoff: first one sentence (12+ words) with the turning-point fact that answers
   the hook, then exactly: "Everyone knows how {pronoun} story ends. This is how it started."
7. Keep events apart: never put two events in one sentence or paragraph as if they happened together
   unless SOURCE says so. Each event keeps its own year. Do not exaggerate ("failed the exam" when SOURCE
   says he failed part of it is wrong).
8. Present facts as facts. If SOURCE says something is a claim or legend, say "according to" or "by his own account".

Before answering, check: no invented years, numbers, names or quotes; no greetings; no questions to the viewer;
no exclamation marks; no headings or labels; none of the banned words.
{style}"""

SHORT_PACKAGE = """You package a YouTube Short so people stop scrolling and click.

NARRATION:
{narration}

Return JSON with:
- "title": max 60 characters. The story's hook with one concrete detail, then " | {subject}".
  It must be true to the narration and must not reuse the exact words of hook_text.
- "hook_text": 2 to 4 words shown in big letters on the first frame. The single most surprising claim
  from paragraph 1, e.g. "TOO SHORT FOR VARSITY". No subject name.
- "thumbnail_hook": 2 to 4 words that start with "Before", e.g. "Before the shot". Different from hook_text.
- "first_line": one sentence for the top of the description, under 120 characters, with the subject's name.
- "tags": 10 search phrases people would type, most specific first.
Reply with JSON only."""

IMAGE_PICK = """Pick a picture for each line of a video narration.

LINES:
{lines}

PICTURES (from Wikipedia articles about the subject):
{images}

For each line, choose up to 2 picture numbers that show what the line is about: the same person, place,
event or time period. Prefer a picture of the exact moment or place named in the line. Use a picture at
most twice in the whole video. If no picture fits a line, give an empty list for that line.
Reply with JSON only: {{"picks": [[int, ...], ...]}} with exactly {n} lists, in line order."""

QUERIES = """For each numbered narration line below, give 2 image search queries of 2-4 words
for finding a matching photograph or film still. Queries must be concrete and photographable, and
include the subject "{subject}" or a specific place, person or object named in the line. Never abstract ideas.
{lines}
Reply with JSON only: {{"queries": [[str, str], ...]}} with exactly {n} pairs, in order."""

# ---------------------------------------------------------------- Long-form

OUTLINE = """You are planning a {minutes}-minute YouTube documentary about: {topic}

SOURCE (the only facts you may use):
{facts}

Plan the video for maximum audience retention:
- "cold_open": one full sentence describing the single most dramatic or surprising TRUE moment in the
  source (who, where, what happened). The video starts here, in the middle of the action.
- "promise": one sentence saying what the viewer will understand by the end. Specific, not vague.
- "stakes": one sentence on what was at risk or why it mattered.
- "chapters": {chapters} chapters in story order. Each has a 2-5 word "title", 3-5 "beats" and an
  "open_loop". Every beat is one full sentence stating a concrete fact from SOURCE: who, what,
  where, when, with the real names, places, dates and numbers. Not a vague label like
  "engineers race" - write what actually happened. The "open_loop" is an unanswered question or
  tension that makes the viewer want the next chapter. The last chapter's open_loop is "".
- "payoff": one sentence that answers the cold open.
- "titles": 3 YouTube titles, max 60 characters, curiosity + a concrete detail, true to the content.
- "thumbnail_hook": 2-4 words for the thumbnail. It must not repeat the title.
- "mood": one of {moods}.
- "tags": 10 search tags.

Reply with JSON only:
{{"titles": [str, str, str], "thumbnail_hook": str, "mood": str, "cold_open": str, "promise": str,
  "stakes": str, "chapters": [{{"title": str, "beats": [str], "open_loop": str}}], "payoff": str, "tags": [str]}}"""

COLD_OPEN = """Write the opening {words} words of a documentary about {topic}.

SOURCE:
{facts}

Write 3 paragraphs separated by blank lines, with no headings or labels:
- First paragraph: put the viewer inside this moment, as if it is happening now: {cold_open}
- Second paragraph: in your own words, tell the viewer what they will understand by the end. Based on: {promise}
- Third paragraph: why it mattered and what was at risk. Based on: {stakes}
  End it with one line that takes us back to where the story really began.
{style}"""

CHAPTER = """You are writing chapter {k} of {n} of a documentary about {topic}.
Chapter title: {title}
Beats to cover, in order:
{beats}

SOURCE for this chapter:
{facts}

The previous paragraph was:
"{previous}"

Write about {words} words as {paras} paragraphs separated by blank lines, 40 to 70 words each.
Continue naturally from the previous paragraph. Do not repeat it. Do not write the chapter title.
{ending}
{style}"""

CHAPTER_END_LOOP = "End the last paragraph on this open question, phrased as narration (not a question to the viewer): {open_loop}"
CHAPTER_END_FINAL = ("This is the final chapter. Pay off the opening: {payoff} Then end with one short, "
                     "resonant closing line.")
