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

SHORT_NARRATION = """Write the narration for a YouTube Short (under 60 seconds) about: {topic}

SOURCE:
{facts}

Write exactly {n} paragraphs separated by blank lines, 2 sentences each, 20 to 35 words per paragraph.
Paragraph 1 opens with the single most surprising true fact (the hook) - no setup before it.
Paragraph 2 makes a specific promise of what the viewer is about to learn.
The last paragraph pays off the hook and ends with a short closing line.
{style}"""

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
