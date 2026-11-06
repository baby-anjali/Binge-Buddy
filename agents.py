import asyncio
import os
import random
import warnings

from dotenv import load_dotenv

# Suppress harmless upstream syntax warnings from google.genai in Python 3.15
warnings.filterwarnings("ignore", category=SyntaxWarning, module="google.genai")

# Suppress Pydantic AI ASCII banner and ensure v1beta for function calling
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
os.environ.setdefault("GOOGLE_GENAI_API_VERSION", "v1beta")

# Load env vars immediately to ensure API keys are accessible
load_dotenv()

from typing import Any

from pydantic_ai import Agent

from models import MatchVerdict, MediaResearch, MediaReview
from rag import LocalRAG

# Allow model configuration via environment variable (defaults to Google Gemini 3.8 Flash)
DEFAULT_MODEL = os.getenv("LLM_MODEL", "google:gemini-3.8-flash")
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "google:gemini-2.5-flash")


async def run_agent_with_fallback(
    agent: Agent[Any, Any], prompt: str, max_retries_per_model: int = 3, **kwargs: Any
):
    """Executes an agent run with exponential backoff, real-time status notices, and multi-model cascade."""
    models_to_try = [DEFAULT_MODEL, FALLBACK_MODEL, "google:gemini-2.5-flash"]
    candidate_models = list(dict.fromkeys([m for m in models_to_try if m]))

    last_error = None
    for m_idx, model_name in enumerate(candidate_models):
        for attempt in range(1, max_retries_per_model + 1):
            try:
                return await agent.run(prompt, model=model_name, **kwargs)
            except Exception as e:
                err_msg = str(e).lower()
                last_error = e

                is_transient = any(
                    code in err_msg
                    for code in [
                        "503",
                        "404",
                        "429",
                        "high demand",
                        "unavailable",
                        "resource_exhausted",
                        "no longer available",
                    ]
                )
                if not is_transient:
                    raise e

                # If this model is deprecated/not found (404), skip immediately to the next model
                if "404" in err_msg or "no longer available" in err_msg or "not found" in err_msg:
                    print(
                        f"⚠️  [Model Outdated]: '{model_name}' is not found. Trying next available model..."
                    )
                    break

                # For 503 / 429 high demand: wait with exponential backoff and display informative updates
                if attempt < max_retries_per_model:
                    delay = round((1.3**attempt) + random.uniform(0.2, 0.5), 1)
                    print(
                        f"⏳ [Google API Busy]: High demand on '{model_name}'. Retrying in {delay}s (Attempt {attempt}/{max_retries_per_model})..."
                    )
                    await asyncio.sleep(delay)
                else:
                    if m_idx < len(candidate_models) - 1:
                        next_model = candidate_models[m_idx + 1]
                        print(
                            f"🔄 [Failover]: Continuous high demand on '{model_name}'. Switching to '{next_model}'..."
                        )
                        await asyncio.sleep(0.8)

    if last_error:
        raise last_error
    raise RuntimeError("All candidate models failed to respond.")


# Initialize RAG
rag = LocalRAG()
rag.ingest_documents()

# 1. The Researcher Agent (Extracts structural DNA, genres, tropes, and pacing)
researcher_agent = Agent(
    model=DEFAULT_MODEL,
    output_type=MediaResearch,
    system_prompt=(
        "You are an expert Media Researcher. When given the title of a book, movie, show, anime, manga, or manhwa, "
        "analyze its structural storytelling 'DNA': genres, key narrative tropes, pacing style, and character archetypes.\n"
        "CRITICAL RULE: You must NEVER reveal plot spoilers or twists. Focus strictly on narrative style and mechanics."
    ),
)

# 2. The Profiler Agent (Synthesizes taste patterns from relevant past reviews)
profiler_agent = Agent(
    model=DEFAULT_MODEL,
    system_prompt=(
        "You are a User Taste Profile Analyst. Review the provided past media reviews from the user's personal archive. "
        "Summarize their exact preferences, particularly as they relate to the tropes, pacing, and themes in question. "
        "Highlight what they consistently love, what they dislike, and any dealbreakers in a concise bulleted summary."
    ),
)

# 3. The Matchmaker Agent (Cross-references media traits with user taste into a structured verdict)
matchmaker_agent = Agent(
    model=DEFAULT_MODEL,
    output_type=MatchVerdict,
    system_prompt=(
        "You are a Personalized Media Matchmaker. You will receive:\n"
        "1. The structural research of a candidate media (genres, tropes, pacing, archetypes).\n"
        "2. The user's taste profile derived from their personal review archive.\n\n"
        "Your task:\n"
        "- Identify positive coincidences (traits the user loves that the media contains).\n"
        "- Identify negative coincidences (traits the user dislikes that the media contains).\n"
        "- Calculate an objective compatibility match score from 0 to 100 based on overlap.\n"
        "- Choose a recommendation tier: 'Strong Match', 'Recommended', 'Mixed / Conditional', or 'Not Recommended'.\n"
        "- Deliver a spoiler-free verdict summarizing why it is or isn't a good fit."
    ),
)

# 4. The Ingestor Agent (Archives free-form user thoughts into structured reviews)
ingestor_agent = Agent(
    model=DEFAULT_MODEL,
    output_type=MediaReview,
    system_prompt=(
        "You are a meticulous personal data archivist. Extract media review details from the user's "
        "raw, unstructured thoughts and format them strictly into the requested MediaReview schema."
    ),
)

# 5. Emergency Single-Pass Matchmaker Agent
# Combines structural research and matchmaking in 1 single network call if Researcher fails
emergency_matchmaker_agent = Agent(
    model=DEFAULT_MODEL,
    output_type=MatchVerdict,
    system_prompt=(
        "You are an Emergency Direct Media Matchmaker. When given a candidate media title and user preferences:\n"
        "1. Identify its structural storytelling traits (genres, narrative tropes, pacing, archetypes) without spoilers.\n"
        "2. Directly cross-reference those traits with the user's confirmed likes and dislikes.\n"
        "3. Produce a structured MatchVerdict: compatibility score (0-100), recommendation tier, positive coincidences, "
        "watch-outs, and a spoiler-free verdict synthesis."
    ),
)
