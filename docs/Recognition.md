# Recognition

The recognition module parses anime titles from filenames or raw text into structured metadata.

## Architecture

```
┌───────────────┐
│BaseRecognizer │ (core/interfaces/recognition/base.py)
└──────┬────────┘
       │
  ┌────┴─────┐
  │          │
  ▼          ▼
Aniparse   LLM Recognizer
```

## Interface

**File:** `core/interfaces/recognition/base.py` → `BaseRecognizer`

### Methods

| Method | Description |
|--------|-------------|
| `parse(title)` | Parse a single title/filename into structured data |
| `parse_batch(titles)` | Parse multiple titles |

### RecognitionResult

```python
class RecognitionResult(TypedDict, total=False):
    anime_title: str               # resolved anime title
    episode_number: Optional[int]  # episode number
    season_number: Optional[int]   # season number
    release_group: Optional[str]   # fansub/release group
    video_resolution: Optional[str] # e.g. "1080p", "720p"
    source: str                    # which recognizer produced this ("aniparse", "llm")
    raw: dict                      # full unprocessed output
```

## Implementations

### Aniparse Recognizer

**Extra:** `recognition`

Uses the [aniparse](https://pypi.org/project/aniparse/) library to extract metadata from anime filenames. Fast, deterministic, no network calls. Works well for standard fansub naming conventions.

**Example:**
```
Input:  "[SubsPlease] Frieren - Beyond Journey's End - 01 (1080p) [hash].mkv"
Output: {
    "anime_title": "Frieren - Beyond Journey's End",
    "episode_number": 1,
    "video_resolution": "1080p",
    "release_group": "SubsPlease",
    "source": "aniparse",
    "raw": { ... }
}
```

### LLM Recognizer

**Extra:** `llm`

Uses an LLM endpoint (via the [LLM module](LLM.md)) to parse titles that aniparse can't handle — non-standard naming, missing metadata, ambiguous titles, or complex multi-season releases.

The LLM recognizer sends the title to the configured LLM endpoint with a structured prompt asking for JSON output matching `RecognitionResult`.

**When to use LLM over aniparse:**
- Titles with non-standard formatting
- Batch renaming with inconsistent patterns
- When contextual knowledge is needed (e.g., knowing "S2" refers to a specific sequel)

## Implementing a New Recognizer

```python
from core.interfaces.recognition import BaseRecognizer, RecognitionResult

class CustomRecognizer(BaseRecognizer):
    _name = "custom"

    def parse(self, title: str) -> RecognitionResult:
        # Your parsing logic
        return RecognitionResult(
            anime_title="...",
            episode_number=1,
            source=self._name,
            raw={}
        )

    def parse_batch(self, titles: list[str]) -> list[RecognitionResult]:
        return [self.parse(t) for t in titles]
```

## Factory

```python
from core.recognition import get_recognizer

# Use aniparse (default)
recognizer = get_recognizer("aniparse")

# Use LLM
recognizer = get_recognizer("llm", endpoint="http://localhost:8080/v1")
```
