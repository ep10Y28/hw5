"""The one and only model for every agent: gpt-6-luna through Portkey.

The model name is a constant on purpose. HW5 deducts points if any other
model shows up in code or runs, so there is no env override.

API style: gpt-6-luna on this Portkey/Azure route rejects function tools on
/v1/chat/completions while reasoning is on ("use /v1/responses or set
reasoning_effort to 'none'"). Agents need tools AND reasoning, so we use
the OpenAI **Responses** API by default. Fallback: PORTKEY_API_STYLE=chat
uses chat completions with reasoning_effort='none'. Same model either way.

Portkey lesson from earlier homework: this workspace rejects requests that
carry `Authorization: Bearer`, and wants the key ONLY in `x-portkey-api-key`.
The OpenAI SDK always adds Authorization, so an httpx hook strips it.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from openai import AsyncOpenAI
from pydantic_ai.models import Model
from pydantic_ai.models.openai import (
    OpenAIChatModel,
    OpenAIChatModelSettings,
    OpenAIResponsesModel,
    OpenAIResponsesModelSettings,
)
from pydantic_ai.providers.openai import OpenAIProvider

MODEL_NAME = "gpt-6-luna"
REASONING_EFFORT = "low"  # enough to plan tool calls; keeps token use down
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def build_model() -> Model:
    _load_env()
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to hw5/.env (see .env.example).")

    async def strip_bearer(request: httpx.Request) -> None:
        request.headers.pop("Authorization", None)

    http_client = httpx.AsyncClient(
        headers={"x-portkey-api-key": key},
        timeout=httpx.Timeout(90.0),
        event_hooks={"request": [strip_bearer]},
    )
    client = AsyncOpenAI(
        api_key="portkey-key-is-in-header",  # placeholder; stripped by the hook
        base_url=os.environ.get("PORTKEY_BASE_URL", PORTKEY_BASE_URL),
        http_client=http_client,
        max_retries=1,
    )
    provider = OpenAIProvider(openai_client=client)
    if os.environ.get("PORTKEY_API_STYLE", "responses").lower() == "chat":
        return OpenAIChatModel(MODEL_NAME, provider=provider,
                               settings=OpenAIChatModelSettings(openai_reasoning_effort="none"))
    return OpenAIResponsesModel(MODEL_NAME, provider=provider,
                                settings=OpenAIResponsesModelSettings(openai_reasoning_effort=REASONING_EFFORT))
