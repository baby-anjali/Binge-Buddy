import os
from dotenv import load_dotenv

# Load env vars immediately to ensure API keys are accessible
load_dotenv()

from pydantic_ai import Agent
from rag import LocalRAG
from models import MediaReview, MediaResearch, MatchVerdict

# Allow model configuration via environment variable (defaults to Google Gemini 3.8 Flash)
DEFAULT_MODEL = os.getenv("LLM_MODEL", "google:gemini-3.8-flash")
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "google:gemini-3.8-flash")

async def run_agent_with_fallback(agent: Agent, prompt: str, **kwargs):
    """Executes an agent run with automatic fallback on 503 / 404 / high-demand errors."""
    try:
        return await agent.run(prompt, **kwargs)
    except Exception as e:
        err_msg = str(e).lower()
        if any(term in err_msg for term in ["503", "404", "high demand", "unavailable", "resource_exhausted", "no longer available"]):
            current_model_str = str(getattr(agent, "model", ""))
            if FALLBACK_MODEL not in current_model_str:
                print(f"\n⚠️  [Model Overloaded / Unavailable]: Primary model encountered an issue. Failing over to '{FALLBACK_MODEL}'...")
                return await agent.run(prompt, model=FALLBACK_MODEL, **kwargs)
        raise

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
    )
)

# 2. The Profiler Agent (Synthesizes taste patterns from relevant past reviews)
profiler_agent = Agent(
    model=DEFAULT_MODEL,
    system_prompt=(
        "You are a User Taste Profile Analyst. Review the provided past media reviews from the user's personal archive. "
        "Summarize their exact preferences, particularly as they relate to the tropes, pacing, and themes in question. "
        "Highlight what they consistently love, what they dislike, and any dealbreakers in a concise bulleted summary."
    )
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
    )
)

# 4. The Ingestor Agent (Archives free-form user thoughts into structured reviews)
ingestor_agent = Agent(
    model=DEFAULT_MODEL,
    output_type=MediaReview,
    system_prompt=(
        "You are a meticulous personal data archivist. Extract media review details from the user's "
        "raw, unstructured thoughts and format them strictly into the requested MediaReview schema."
    )
)
