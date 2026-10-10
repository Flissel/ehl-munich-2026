"""AI design interpretation via the OpenAI Responses API with strict structured output."""
from __future__ import annotations

import logging

from design import DesignProposal
from registry import PAINTS, WHEEL_STYLES, ModelEntry

log = logging.getLogger("bmw.ai")


class AIUnavailable(Exception):
    pass


class AIFailed(Exception):
    pass


def build_instructions(model: ModelEntry) -> str:
    paints = "\n".join(f"  - {pid}: {PAINTS[pid]}" for pid in model.paints)
    wheels = "\n".join(f"  - {wid}: {WHEEL_STYLES[wid]}" for wid in model.wheel_styles)
    notes = "\n".join(f"- {n}" for n in model.notes)
    return f"""You are the design assistant of a 3D car configurator showing a {model.display_name}.
Translate the user's request into a design proposal using ONLY these supported actions:

- set_paint with paint_id one of:
{paints}
- set_wheel_style with style_id one of:
{wheels}
- reset_design (restore the original as-imported design)

Rules:
- Pick the closest supported option (e.g. "dark blue", "navy" -> midnight_blue; "red" -> racing_red;
  "sporty/performance/aggressive wheels" -> sport; "stock/normal/default wheels" -> standard).
- Never invent action types, IDs, file paths, mesh names, material names or parameters.
- Anything else the user asks for goes into `unsupported` with a category:
  geometry_modification (reshaping body parts: bumpers, fenders, diffuser, hood, bodywork...),
  component_replacement (swapping parts for other existing 3D parts), concept_image (requests for
  pictures/renders), other (interior colors, decals, lighting, etc.). Explain briefly why it is not
  applied. Do not claim unsupported changes will happen.
- If nothing supported was requested, return an empty `actions` list.
- `summary`: 1-3 sentences, friendly, describing exactly what will be applied.
Model notes:
{notes}"""


async def parse_structured(settings, instructions: str, prompt: str, schema):
    """Responses API call returning an instance of the Pydantic `schema` (strict structured output)."""
    if not settings.ai_configured:
        raise AIUnavailable("OPENAI_API_KEY is not set on the server.")
    from openai import AsyncOpenAI, OpenAIError
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout)
    try:
        response = await client.responses.parse(model=settings.openai_model, instructions=instructions,
                                                input=prompt, text_format=schema)
    except OpenAIError as e:
        log.warning("OpenAI request failed: %s", e)
        raise AIFailed(f"AI request failed: {type(e).__name__}: {getattr(e, 'message', None) or e}") from e
    if response.output_parsed is None:
        raise AIFailed("AI returned no usable proposal")
    return response.output_parsed


async def propose_design(settings, model: ModelEntry, prompt: str) -> DesignProposal:
    if not settings.ai_configured:
        raise AIUnavailable("OPENAI_API_KEY is not set on the server. Add it to backend/.env and restart "
                            "the backend. Manual design controls still work without AI.")
    try:
        from openai import AsyncOpenAI, OpenAIError
    except ImportError as e:  # pragma: no cover
        raise AIUnavailable("The 'openai' package is not installed (pip install -r requirements.txt)") from e

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout)
    try:
        response = await client.responses.parse(
            model=settings.openai_model,
            instructions=build_instructions(model),
            input=prompt,
            text_format=DesignProposal,
        )
    except OpenAIError as e:
        log.warning("OpenAI request failed: %s", e)
        raise AIFailed(f"AI request failed: {type(e).__name__}: {getattr(e, 'message', None) or e}") from e
    proposal = response.output_parsed
    if proposal is None:
        refusal = next((c.refusal for item in getattr(response, "output", []) or []
                        for c in getattr(item, "content", []) or [] if getattr(c, "type", "") == "refusal"), None)
        raise AIFailed(f"AI returned no usable proposal{': ' + refusal if refusal else ''}")
    return proposal
