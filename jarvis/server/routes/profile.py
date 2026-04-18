"""User-profile REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from jarvis.server.auth import require_api_key
from jarvis.server.deps import get_runtime

router = APIRouter(dependencies=[Depends(require_api_key)])


class ProfilePatch(BaseModel):
    name: str | None = None
    preferred_address: str | None = None
    timezone: str | None = None
    humor_level: int | None = Field(default=None, ge=0, le=3)
    verbosity: str | None = None
    speech_rate: int | None = Field(default=None, ge=80, le=400)


class NoteBody(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    tag: str = "observation"


class JokeBody(BaseModel):
    text: str = Field(min_length=1, max_length=280)


@router.get("/v1/profile")
async def get_profile(request: Request) -> dict:
    runtime = get_runtime(request)
    profile = await runtime.profile_store.load()
    return profile.to_json()


@router.patch("/v1/profile")
async def patch_profile(body: ProfilePatch, request: Request) -> dict:
    runtime = get_runtime(request)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    profile = await runtime.profile_store.update(**data)
    # Push a few of the mutated fields into the live persona too.
    if "preferred_address" in data:
        runtime.persona.address = data["preferred_address"]
    if "humor_level" in data:
        runtime.persona.humor_level = data["humor_level"]
    if "verbosity" in data:
        runtime.persona.verbosity = data["verbosity"]
    if "speech_rate" in data:
        runtime.persona.voice_speech_rate = data["speech_rate"]
    return profile.to_json()


@router.post("/v1/profile/notes")
async def add_note(body: NoteBody, request: Request) -> dict:
    runtime = get_runtime(request)
    await runtime.profile_store.add_note(body.text, tag=body.tag)
    return {"ok": True}


@router.post("/v1/profile/jokes")
async def add_joke(body: JokeBody, request: Request) -> dict:
    runtime = get_runtime(request)
    await runtime.profile_store.add_inside_joke(body.text)
    return {"ok": True}
