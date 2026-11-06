import json
import re
from pathlib import Path
from typing import Any

from models import MediaResearch, MediaReview


class ResearchCache:
    """Persistent local cache for media structural DNA to eliminate duplicate network calls and 503 errors."""

    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.data_dir / "research_cache.json"
        self.cache: dict[str, dict[str, Any]] = {}
        self.load()

    def _normalize_title(self, title: str) -> str:
        return re.sub(r"[^\w\s]", "", (title or "").lower()).strip()

    def load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}
        else:
            self.cache = {}

    def save(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)

    def get(self, title: str) -> MediaResearch | None:
        key = self._normalize_title(title)
        if key and key in self.cache:
            try:
                return MediaResearch.model_validate(self.cache[key])
            except Exception:
                return None
        return None

    def put(self, title: str, research: MediaResearch):
        key = self._normalize_title(title)
        res_key = self._normalize_title(research.title)
        data = research.model_dump()
        if key:
            self.cache[key] = data
        if res_key:
            self.cache[res_key] = data
        self.save()


CATEGORY_FILES = {
    "movie": "movies.md",
    "show": "shows.md",
    "manhwa": "manhwa.md",
    "novel": "novels.md",
}

CATEGORY_HEADERS = {
    "movies.md": "# Movie Reviews\n\nPersonal archive of movie reviews and ratings.\n",
    "shows.md": "# Show & Series Reviews\n\nPersonal archive of TV and streaming show reviews.\n",
    "manhwa.md": "# Manhwa, Manga & Anime Reviews\n\nPersonal archive of manhwa, manga, and anime reviews.\n",
    "novels.md": "# Novel & Book Reviews\n\nPersonal archive of novel, web novel, and book reviews.\n",
}


def get_media_category_filename(media_type: str) -> str:
    """Maps a media type string to its corresponding category markdown filename (movies.md, shows.md, manhwa.md, novels.md)."""
    mt = (media_type or "").lower().strip()
    if "movie" in mt or "film" in mt or "cinema" in mt:
        return "movies.md"
    elif "show" in mt or "series" in mt or "tv" in mt or "drama" in mt:
        return "shows.md"
    elif "manhwa" in mt or "manga" in mt or "anime" in mt or "webtoon" in mt:
        return "manhwa.md"
    elif "novel" in mt or "book" in mt or "fiction" in mt:
        return "novels.md"
    return "other.md"


def save_review_to_markdown(review: MediaReview, data_dir: str | Path = "data") -> Path:
    """Saves or updates a review in the media-specific markdown file (movies.md, shows.md, manhwa.md, novels.md)."""
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    filename = get_media_category_filename(review.media_type)
    target_path = data_path / filename

    if not target_path.exists():
        header = CATEGORY_HEADERS.get(
            filename, f"# {filename.replace('.md', '').capitalize()} Reviews\n\n"
        )
        target_path.write_text(header, encoding="utf-8")

    current_content = target_path.read_text(encoding="utf-8")

    liked_bullets = "\n".join(f"* {item}" for item in review.liked) or "* None specified"
    disliked_bullets = "\n".join(f"* {item}" for item in review.disliked) or "* None specified"

    entry = (
        f"## {review.title}\n"
        f"**Type:** {review.media_type}  \n"
        f"**Genre:** {review.genre}  \n"
        f"**Status:** {review.status}  \n"
        f"**My Rating:** {review.rating}  \n\n"
        f"### What I Liked\n"
        f"{liked_bullets}\n\n"
        f"### What I Disliked\n"
        f"{disliked_bullets}\n\n"
        f"### Final Verdict\n"
        f"{review.verdict}\n"
    )

    pattern = rf"(?ms)^##\s+{re.escape(review.title)}\b.*?(?=\n##\s+|\Z)"
    if re.search(pattern, current_content):
        updated_content = re.sub(pattern, entry.strip(), current_content)
    else:
        updated_content = current_content.rstrip() + "\n\n" + entry

    target_path.write_text(updated_content.strip() + "\n", encoding="utf-8")
    return target_path


class PreferenceStore:
    """Manages the user's consolidated taste memory (likes, dislikes, and history)

    Eliminates context bloat and hallucination by storing a single consolidated
    preference knowledge base rather than dozens of separate markdown files.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pref_file = self.data_dir / "preferences.json"
        self.data: dict[str, Any] = {"likes": [], "dislikes": [], "history": []}
        self.load()

    def load(self):
        if self.pref_file.exists():
            try:
                with open(self.pref_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self._initialize_default()
        else:
            self._initialize_default()

    def _initialize_default(self):
        # Initial taste anchor
        self.data = {
            "likes": [
                "Clever, strategic protagonists who use planning rather than brute strength",
                "High stakes from the start without dragging out initial setup",
                "Morally grey characters who make ruthless, calculated survival decisions",
            ],
            "dislikes": [
                "Supporting characters fading into the background during major solo arcs",
                "Slow, dragging middle pacing with excessive filler",
            ],
            "history": [
                {
                    "title": "Omniscient Reader's Viewpoint",
                    "type": "Web Novel / Manhwa",
                    "rating": "5/5",
                }
            ],
        }
        self.save()

    def save(self):
        with open(self.pref_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def add_review(self, review: MediaReview):
        """Extracts tropes and elements from review into centralized likes & dislikes."""
        existing_likes = set(self.data.get("likes", []))
        for item in review.liked:
            cleaned = item.strip().rstrip(".")
            if cleaned:
                existing_likes.add(cleaned)

        existing_dislikes = set(self.data.get("dislikes", []))
        for item in review.disliked:
            cleaned = item.strip().rstrip(".")
            if cleaned:
                existing_dislikes.add(cleaned)

        self.data["likes"] = sorted(list(existing_likes))
        self.data["dislikes"] = sorted(list(existing_dislikes))

        history = self.data.get("history", [])
        if not any(h.get("title", "").lower() == review.title.lower() for h in history):
            history.append(
                {
                    "title": review.title,
                    "type": review.media_type,
                    "rating": review.rating,
                }
            )
        self.data["history"] = history
        self.save()
        return save_review_to_markdown(review, self.data_dir)

    def get_preferences_context(self) -> str:
        """Returns clean, formatted text of user likes and dislikes for the Matchmaker."""
        likes = self.data.get("likes", [])
        dislikes = self.data.get("dislikes", [])

        likes_text = (
            "\n".join(f"  + {item}" for item in likes) if likes else "  + None recorded yet."
        )
        dislikes_text = (
            "\n".join(f"  - {item}" for item in dislikes) if dislikes else "  - None recorded yet."
        )

        return (
            f"User Confirmed Likes (Positive Tropes & Preferences):\n{likes_text}\n\n"
            f"User Confirmed Dislikes (Negative Tropes & Dealbreakers):\n{dislikes_text}"
        )

    def list_reviews(self) -> list[dict[str, str]]:
        return self.data.get("history", [])

    # Compatibility methods for backward compatibility
    def ingest_documents(self):
        self.load()

    def query(self, query_input=None, n_results=5):
        # Returns preferences context as documents
        return [self.get_preferences_context()]


# Alias for backward compatibility
LocalRAG = PreferenceStore

# Shared research cache singleton
research_cache = ResearchCache("data")
