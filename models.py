from pydantic import BaseModel, Field
from typing import List, Literal

class MediaReview(BaseModel):
    title: str = Field(description="Title of the book, movie, show, anime, or manhwa")
    media_type: Literal[
        "Book", "Novel", "Web Novel", "Web Novel / Manhwa", "Show", "Movie", "Manhwa", "Manga", "Anime"
    ] = Field(description="Type of media")
    genre: str = Field(description="Genres separated by commas")
    status: str = Field(
        default="Completed",
        description="Current status, e.g., 'Completed', 'Dropped', 'Reading', 'Watching'"
    )
    rating: str = Field(description="Rating out of 5, e.g., '5/5'")
    liked: List[str] = Field(description="Specific tropes, pacing choices, or elements liked")
    disliked: List[str] = Field(description="Specific tropes, pacing choices, or elements disliked")
    verdict: str = Field(description="1-2 sentence summary of the overall vibe")

class MediaResearch(BaseModel):
    title: str = Field(description="Title of the media analyzed")
    media_type: str = Field(description="Format or type of media (e.g., Anime, Novel, Show)")
    genres: List[str] = Field(description="List of primary genres, e.g., ['Fantasy', 'Action']")
    themes_and_tropes: List[str] = Field(
        description="Key narrative tropes and themes, e.g., ['Morally grey protagonist', 'Survival game']"
    )
    pacing: str = Field(description="Pacing style (e.g., 'Fast-paced', 'Slow burn')")
    character_archetypes: List[str] = Field(description="Notable character archetypes or dynamics")
    summary: str = Field(description="Spoiler-free summary of the structural DNA")

class MatchVerdict(BaseModel):
    title: str = Field(description="Title of the candidate media")
    match_score: int = Field(ge=0, le=100, description="Compatibility percentage from 0 to 100")
    recommendation: Literal[
        "Strong Match", "Recommended", "Mixed / Conditional", "Not Recommended"
    ] = Field(description="Recommendation classification")
    positive_coincidences: List[str] = Field(
        description="Aspects of the media that directly match what the user enjoys"
    )
    negative_coincidences: List[str] = Field(
        description="Aspects of the media that clash with user preferences"
    )
    verdict: str = Field(description="Detailed spoiler-free synthesis of the match decision")
