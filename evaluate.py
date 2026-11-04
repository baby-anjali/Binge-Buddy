"""Automated Evaluation & Test Suite for Second Brain: Personalized Media Matchmaker

Tests PII sanitization guardrails, PreferenceStore consolidation,
Pydantic schemas, offline agent pipeline, and slash command auto-completion.
"""

import sys
import asyncio
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from prompt_toolkit.document import Document

from guardrails import sanitize_pii
from rag import PreferenceStore, get_media_category_filename, save_review_to_markdown
from models import MediaReview, MediaResearch, MatchVerdict
from main import SlashCommandCompleter, is_likely_review

def test_pii_sanitization():
    print("🧪 Running Test: PII Sanitization Guardrail...")

    # Email tests
    email_sample = "Contact author at reader.one+media@example.co.uk. Or admin@domain.org!"
    sanitized_email = sanitize_pii(email_sample)
    assert "[REDACTED_EMAIL]" in sanitized_email, "Email was not redacted"
    assert "reader.one" not in sanitized_email, "Email username leaked"
    assert sanitized_email.endswith("!"), "Punctuation was stripped improperly"

    # Phone tests
    phone_samples = [
        "Call (555) 123-4567 for info",
        "Reach out at +1-555-123-4567 please",
        "Direct line: +1 (555) 123-4567",
        "Number: 555.123.4567",
        "Local 5551234567"
    ]
    for sample in phone_samples:
        result = sanitize_pii(sample)
        assert "[REDACTED_PHONE]" in result, f"Failed to redact phone in: {sample}"
        assert "555" not in result, f"Phone digits leaked in: {sample}"

    # Benign numbers should be preserved
    benign_text = "I gave this book 5/5 stars in 2024 at chapter 320."
    assert sanitize_pii(benign_text) == benign_text, "Benign numbers were incorrectly redacted"

    print("   ✅ PII Sanitization passed.")

def test_preference_store():
    print("🧪 Running Test: Consolidated PreferenceStore...")
    ps = PreferenceStore(data_dir="data")

    # Verify initialized preferences
    context = ps.get_preferences_context()
    assert "User Confirmed Likes" in context
    assert "User Confirmed Dislikes" in context
    assert len(ps.data["likes"]) > 0
    assert len(ps.data["dislikes"]) > 0

    # Test adding a review
    new_rev = MediaReview(
        title="Arcane",
        media_type="Show",
        genre="Animation, Action",
        status="Completed",
        rating="5/5",
        liked=["Sister conflict dynamics", "Exceptional fluid animation"],
        disliked=["Long wait between seasons"],
        verdict="Masterpiece."
    )
    ps.add_review(new_rev)
    assert "Sister conflict dynamics" in ps.data["likes"]
    assert "Long wait between seasons" in ps.data["dislikes"]
    assert any(h["title"] == "Arcane" for h in ps.list_reviews())

    print("   ✅ PreferenceStore consolidation passed.")

def test_slash_command_completion():
    print("🧪 Running Test: Slash Command Auto-Completion...")
    completer = SlashCommandCompleter()

    # User types '/'
    doc = Document('/', 1)
    completions = list(completer.get_completions(doc, None))
    assert len(completions) == 4, f"Expected 4 slash commands, got {len(completions)}"
    cmd_names = [c.text for c in completions]
    assert "/review" in cmd_names
    assert "/list" in cmd_names
    assert "/help" in cmd_names
    assert "/quit" in cmd_names

    # User types '/re'
    doc_re = Document('/re', 2)
    completions_re = list(completer.get_completions(doc_re, None))
    assert len(completions_re) == 1
    assert completions_re[0].text == "/review"

    # User types a media title (e.g. 'Arcane')
    doc_title = Document('Arcane', 6)
    completions_title = list(completer.get_completions(doc_title, None))
    assert len(completions_title) == 0, "No completions should appear for regular media titles"

    print("   ✅ Slash Command Auto-Completion passed.")

def test_pydantic_schemas():
    print("🧪 Running Test: Pydantic Data Models Validation...")

    review = MediaReview(
        title="Dune",
        media_type="Movie",
        genre="Sci-Fi, Adventure",
        status="Completed",
        rating="4.5/5",
        liked=["Deep political intrigue", "Epic worldbuilding"],
        disliked=["Abrupt cliffhanger ending"],
        verdict="A visually stunning cinematic experience."
    )
    assert review.title == "Dune"
    assert len(review.liked) == 2

    research = MediaResearch(
        title="Dune",
        media_type="Movie",
        genres=["Sci-Fi", "Adventure"],
        themes_and_tropes=["Chosen one subversion", "Political intrigue"],
        pacing="Epic / Slow burn",
        character_archetypes=["Reluctant leader", "Mystic order"],
        summary="A desert epic exploring political destiny."
    )
    assert research.title == "Dune"

    verdict = MatchVerdict(
        title="Dune",
        match_score=90,
        recommendation="Strong Match",
        positive_coincidences=["Loves political intrigue and rich worldbuilding"],
        negative_coincidences=["Dislikes cliffhangers"],
        verdict="Highly aligned with your preferences."
    )
    assert 0 <= verdict.match_score <= 100
    assert verdict.recommendation == "Strong Match"

    print("   ✅ Pydantic Schemas passed.")

async def test_offline_agent_pipeline():
    print("🧪 Running Test: Offline Agent Execution via TestModel...")

    # 1. Test Ingestor with TestModel
    sample_review_payload = {
        "title": "Solo Leveling",
        "media_type": "Manhwa",
        "genre": "Action, Fantasy",
        "status": "Completed",
        "rating": "4/5",
        "liked": ["Fast pacing", "Power fantasy"],
        "disliked": ["Shallow side characters"],
        "verdict": "Fun hype read."
    }
    test_ingestor = Agent(
        TestModel(custom_output_args=sample_review_payload),
        output_type=MediaReview
    )
    res_ingest = await test_ingestor.run("Process review...")
    assert isinstance(res_ingest.output, MediaReview)
    assert res_ingest.output.title == "Solo Leveling"

    # 2. Test Matchmaker with TestModel
    sample_verdict_payload = {
        "title": "Solo Leveling",
        "match_score": 85,
        "recommendation": "Recommended",
        "positive_coincidences": ["Likes power fantasy and fast pacing"],
        "negative_coincidences": ["Dislikes weak side characters"],
        "verdict": "Great fit for your action preferences."
    }
    test_matchmaker = Agent(
        TestModel(custom_output_args=sample_verdict_payload),
        output_type=MatchVerdict
    )
    res_match = await test_matchmaker.run("Calculate match...")
    assert isinstance(res_match.output, MatchVerdict)
    assert res_match.output.match_score == 85

    print("   ✅ Offline Agent Pipeline passed.")

def test_media_category_markdown_separation():
    print("🧪 Running Test: Media Category Markdown Separation...")

    # 1. Filename mapping
    assert get_media_category_filename("Movie") == "movies.md"
    assert get_media_category_filename("Show") == "shows.md"
    assert get_media_category_filename("Manhwa") == "manhwa.md"
    assert get_media_category_filename("Anime") == "manhwa.md"
    assert get_media_category_filename("Manga") == "manhwa.md"
    assert get_media_category_filename("Novel") == "novels.md"
    assert get_media_category_filename("Web Novel") == "novels.md"
    assert get_media_category_filename("Book") == "novels.md"

    # 2. Test saving reviews into separate markdown files
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        movie_review = MediaReview(
            title="Jailer",
            media_type="Movie",
            genre="Action, Thriller",
            status="Completed",
            rating="3/5",
            liked=["Story was great", "Unexpected twists"],
            disliked=["Too violent", "Felt like aura-farming"],
            verdict="Great story and unexpected twists, but overly violent."
        )
        saved_movie = save_review_to_markdown(movie_review, data_dir=tmpdir)
        assert saved_movie.name == "movies.md"
        movie_text = saved_movie.read_text(encoding="utf-8")
        assert "## Jailer" in movie_text
        assert "Story was great" in movie_text
        assert "Too violent" in movie_text

        novel_review = MediaReview(
            title="Lord of the Mysteries",
            media_type="Novel",
            genre="Fantasy, Mystery",
            status="Reading",
            rating="5/5",
            liked=["Victorian steampunk aesthetic", "Praise the Fool"],
            disliked=["Slow start in volume 1"],
            verdict="Masterclass in worldbuilding and magic systems."
        )
        saved_novel = save_review_to_markdown(novel_review, data_dir=tmpdir)
        assert saved_novel.name == "novels.md"
        novel_text = saved_novel.read_text(encoding="utf-8")
        assert "## Lord of the Mysteries" in novel_text

    print("   ✅ Media Category Markdown Separation passed.")

def test_smart_review_detection():
    print("🧪 Running Test: Smart Review Detection Guardrail...")

    # Actual user prompt that previously caused an error
    user_review_prompt = "Jailer: The movie was too violent for me and it felt like an aura-farming specific to those who like aura-farming. Story was great and twists were unexpected. My rating would be 3/5"
    assert is_likely_review(user_review_prompt) is True

    # Other reviews without slash command
    assert is_likely_review("Arcane: Incredible animation and emotional depth. 5/5") is True
    assert is_likely_review("Dune: Slow burn pacing with incredible visuals, but ending was abrupt. My rating: 4/5") is True

    # Plain media title searches (must NOT be treated as reviews)
    assert is_likely_review("Jailer") is False
    assert is_likely_review("Arcane") is False
    assert is_likely_review("Solo Leveling") is False
    assert is_likely_review("Lord of the Mysteries") is False
    assert is_likely_review("") is False

    print("   ✅ Smart Review Detection passed.")

def main():
    print("=" * 60)
    print("🚀 RUNNING MATCHMAKER TEST & EVALUATION SUITE")
    print("=" * 60)

    try:
        test_pii_sanitization()
        test_preference_store()
        test_slash_command_completion()
        test_pydantic_schemas()
        test_media_category_markdown_separation()
        test_smart_review_detection()
        asyncio.run(test_offline_agent_pipeline())

        print("=" * 60)
        print("🎉 ALL TESTS PASSED SUCCESSFULLY! (7/7 test suites)")
        print("=" * 60)
        return 0
    except AssertionError as ae:
        print(f"\n❌ Assertion Failed: {ae}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected Failure: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
