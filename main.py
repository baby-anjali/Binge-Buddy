import asyncio
import os
import re
from pathlib import Path

# Disable noisy banner if not explicitly opted in
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory

from agents import researcher_agent, matchmaker_agent, ingestor_agent, rag, run_agent_with_fallback
from guardrails import sanitize_pii
from models import MediaReview, MediaResearch, MatchVerdict
from rag import save_review_to_markdown, get_media_category_filename

def is_likely_review(text: str) -> bool:
    """Detects whether user input looks like a review rather than a simple title lookup."""
    clean = text.strip()
    if not clean:
        return False

    # Check for rating formats (e.g. "3/5", "4.5/5", "8/10", "3 stars", "rating: 3/5")
    has_rating = bool(re.search(r'\b(?:\d(?:\.\d)?\s*/\s*(?:5|10)|\d(?:\.\d)?\s*stars?|rating\s*[:=]?\s*\d)\b', clean, re.IGNORECASE))

    # Common review keywords
    review_keywords = [
        "my rating", "i liked", "i disliked", "what i liked", "what i disliked",
        "too violent", "slow pacing", "fast pacing", "plot twist", "felt like",
        "movie was", "show was", "anime was", "manhwa was", "book was", "novel was",
        "aura-farming", "aura farming", "cinematography", "worldbuilding", "soundtrack"
    ]
    has_keywords = any(kw in clean.lower() for kw in review_keywords)

    # Title with colon followed by substantial review body: "Title: Body..."
    has_colon_review = bool(re.match(r'^[^:\n]{2,35}:\s+.{25,}', clean, re.DOTALL))

    if has_rating and len(clean) > 25:
        return True
    if has_colon_review and (has_keywords or len(clean) > 40):
        return True
    if has_keywords and len(clean) > 45:
        return True

    return False

HELP_MESSAGE = """
Available Commands:
  • <media title>    Ask for a match verdict on any book, show, movie, anime, or manhwa.
  • /review [text]   Add thoughts on a media to extract and update your likes & dislikes.
  • /list            View all media titles currently logged in your history.
  • /help            Display this help message.
  • /quit            Exit the application.

Tip: Type '/' to open the interactive command menu, then use the Up & Down arrows to select.
"""

class SlashCommandCompleter(Completer):
    COMMANDS = [
        ("/review", "Update your likes & dislikes from a new review"),
        ("/list", "View all media titles in your history"),
        ("/help", "Show available commands and usage"),
        ("/quit", "Exit the application"),
    ]

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd, desc in self.COMMANDS:
                if cmd.startswith(text.lower()):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta=desc
                    )

def is_api_key_configured() -> bool:
    """Checks whether a non-placeholder API key is set for Gemini or the active provider."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    placeholder_values = {
        "your_gemini_api_key_here",
        "your_api_key_here",
        "placeholder",
        ""
    }
    return gemini_key.strip().lower() not in placeholder_values

def render_verdict(verdict: MatchVerdict):
    bar_length = 20
    filled = int((verdict.match_score / 100) * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)

    print("\n" + "=" * 60)
    print(f"🎬 MATCHMAKER VERDICT: {verdict.title.upper()}")
    print("=" * 60)
    print(f"📊 Compatibility: [{bar}] {verdict.match_score}%  ({verdict.recommendation})")

    if verdict.positive_coincidences:
        print("\n✅ Positive Coincidences (What matches your tastes):")
        for item in verdict.positive_coincidences:
            print(f"   • {item}")

    if verdict.negative_coincidences:
        print("\n⚠️  Watch Outs (Elements you typically dislike):")
        for item in verdict.negative_coincidences:
            print(f"   • {item}")

    print("\n📝 Verdict:")
    print(f"   {verdict.verdict}")
    print("=" * 60)

async def handle_match_request(user_input: str):
    if not is_api_key_configured():
        print(
            "\n⚠️  [Configuration Notice]: Your Gemini API key is currently set to a placeholder.\n"
            "   1. Open '.env'\n"
            "   2. Replace 'your_gemini_api_key_here' with your real key from https://aistudio.google.com/\n"
            "   3. Run your request again!"
        )
        return

    clean_input = sanitize_pii(user_input)

    # 1. Researcher: Analyze structural DNA without spoilers
    print(f"\n🔬 [Researcher] Analyzing structural DNA for '{clean_input}' (No Spoilers)...")
    research_res = await run_agent_with_fallback(researcher_agent, f"Analyze structural DNA for: {clean_input}")
    research: MediaResearch = research_res.output

    print(f"   Format: {research.media_type} | Genres: {', '.join(research.genres)}")
    print(f"   Themes/Tropes: {', '.join(research.themes_and_tropes[:4])}")

    # 2. Matchmaker: Compare directly with User Confirmed Likes & Dislikes
    print("⚖️  [Matchmaker] Comparing media traits against your taste preferences...")
    user_preferences_context = rag.get_preferences_context()

    matchmaker_prompt = (
        f"Candidate Media Research:\n{research.model_dump_json(indent=2)}\n\n"
        f"{user_preferences_context}\n\n"
        "Cross-reference user preferences with candidate media traits and produce a structured MatchVerdict."
    )
    verdict_res = await run_agent_with_fallback(matchmaker_agent, matchmaker_prompt)
    render_verdict(verdict_res.output)

async def show_list():
    reviews = rag.list_reviews()
    if not reviews:
        print("\n📂 Your history is currently empty. Use /review to add one.")
        return

    print("\n" + "=" * 60)
    print(f"📚 MEDIA HISTORY ({len(reviews)})")
    print("=" * 60)
    for idx, r in enumerate(reviews, 1):
        print(f" {idx}. {r.get('title', 'Unknown')} [{r.get('type', 'Media')}] — Rating: {r.get('rating', 'N/A')}")
    print("=" * 60)

async def save_new_review(raw_text: str, session: PromptSession):
    if not is_api_key_configured():
        print(
            "\n⚠️  [Configuration Notice]: Cannot parse review without an active Gemini API key.\n"
            "   Please set GEMINI_API_KEY in '.env'."
        )
        return

    clean_text = sanitize_pii(raw_text)
    print("\n📥 [Ingestor] Extracting your likes and dislikes...")
    result = await run_agent_with_fallback(ingestor_agent, f"Process this review: {clean_text}")
    review: MediaReview = result.output

    # Update the central preference store and archive in category markdown (movies.md, shows.md, manhwa.md, novels.md)
    target_path = rag.add_review(review)

    print(f"\n✅ Updated your taste preferences based on '{review.title}'!")
    print(f"   📂 Archived in: data/{target_path.name}")
    print(f"   + Liked added: {', '.join(review.liked)}")
    print(f"   - Disliked added: {', '.join(review.disliked)}")

async def main():
    print("🧠 Second Brain: Personalized Media Matchmaker Initialized!")
    print("Type a media title (e.g., 'Arcane', 'Dune'), or type '/' to pick a command.")
    print("-" * 60)

    # Initialize prompt_toolkit session for smooth arrow-key line editing & history
    session = PromptSession(
        history=InMemoryHistory(),
        completer=SlashCommandCompleter(),
        complete_while_typing=True
    )

    while True:
        try:
            raw_input = await session.prompt_async("\nYou: ")
            user_input = raw_input.strip()

            if not user_input:
                continue

            lower_input = user_input.lower()
            if lower_input in {"/quit", "/exit", "exit", "quit"}:
                print("Shutting down Second Brain. Happy reading and watching!")
                break

            if lower_input == "/help":
                print(HELP_MESSAGE)
                continue

            if lower_input == "/list":
                await show_list()
                continue

            if lower_input == "/review" or lower_input.startswith("/review "):
                review_content = user_input[len("/review"):].strip()
                if not review_content:
                    review_content = (await session.prompt_async("Enter your review thoughts: ")).strip()
                if review_content:
                    await save_new_review(review_content, session)
                continue

            if is_likely_review(user_input):
                print("\n📝 [Detected Review]: Processing your review and archiving into category markdown...")
                await save_new_review(user_input, session)
                continue

            await handle_match_request(user_input)

        except (KeyboardInterrupt, EOFError):
            print("\nShutting down Second Brain. Happy reading and watching!")
            break
        except Exception as e:
            err_str = str(e)
            if (
                "api_key" in err_str.lower()
                or "401" in err_str
                or "403" in err_str
                or "unauthenticated" in err_str.lower()
                or "invalid argument" in err_str.lower()
            ):
                print(
                    "\n❌ [Authentication Error]: Gemini API key is missing or invalid.\n"
                    "Please open '.env' and set GEMINI_API_KEY with your key from Google AI Studio:\n"
                    "👉 https://aistudio.google.com/"
                )
            elif any(k in err_str.lower() for k in ["503", "high demand", "unavailable", "resource_exhausted"]):
                print(
                    "\n❌ [Service Busy]: Google Gemini is experiencing temporary high demand (503 Service Unavailable).\n"
                    "   • This spike is usually temporary. Please try again in a few moments.\n"
                    "   • Tip: You can configure 'LLM_MODEL=google:gemini-3.8-flash' in '.env' for reliable availability."
                )
            elif "404" in err_str and ("no longer available" in err_str.lower() or "not found" in err_str.lower()):
                print(
                    "\n❌ [Model Deprecated / Not Found]: The configured Gemini model is no longer available.\n"
                    "   • Update 'LLM_MODEL=google:gemini-3.8-flash' in your '.env' file."
                )
            elif "nodename nor servname" in err_str.lower() or "connection" in err_str.lower():
                print(
                    "\n❌ [Network Error]: Could not reach Google Gemini API.\n"
                    "Please check your internet connection."
                )
            else:
                print(f"\n❌ [Error]: {err_str}")
            print("Try again or type '/quit' to exit.")

if __name__ == "__main__":
    asyncio.run(main())
