from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Response
from openai import OpenAI, OpenAIError

from app.api.schemas import IntroNarrationRequest

router = APIRouter(prefix="/audio", tags=["audio"])

NARRATOR_INSTRUCTIONS = (
    "Perform as an original epic fantasy strategy-game narrator. Use a deep, "
    "commanding, weathered baritone with a refined British theatrical accent. "
    "Speak slowly, with solemn grandeur, long dramatic pauses between clauses, "
    "and a sense that kingdoms are being founded in myth. Build from quiet awe "
    "to a powerful final line. Do not imitate or reference any real actor, "
    "celebrity, or public figure."
)


@router.post("/intro")
def create_intro_narration(req: IntroNarrationRequest) -> Response:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.getenv("OPENAI_TTS_VOICE", "cedar")

    try:
        client = OpenAI()
        speech = client.audio.speech.create(
            model=model,
            voice=voice,
            input=req.text,
            instructions=NARRATOR_INSTRUCTIONS,
            response_format="mp3",
        )
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=f"voice generation failed: {exc}") from exc

    return Response(
        content=speech.content,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )
