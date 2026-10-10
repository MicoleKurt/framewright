"""Neural voiceover (Microsoft Edge TTS, free) with word-level timings for captions."""
import asyncio
import time
import edge_tts

VOICE = "en-US-AndrewMultilingualNeural"


async def _tts(text: str, path: str, voice: str) -> list[dict]:
    words = []
    comm = edge_tts.Communicate(text, voice, rate="+8%", boundary="WordBoundary")
    with open(path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offsets are in 100ns ticks
                words.append({"text": chunk["text"],
                              "start": chunk["offset"] / 1e7,
                              "end": (chunk["offset"] + chunk["duration"]) / 1e7})
    return words


def synthesize(text: str, path: str, voice: str = VOICE, retries: int = 4) -> list[dict]:
    """Edge TTS occasionally drops a stream; retry with backoff before giving up."""
    for attempt in range(retries):
        try:
            return asyncio.run(_tts(text, path, voice))
        except edge_tts.exceptions.NoAudioReceived:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
