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
    raw: dict                      # full unprocessed output from the underlying parser
```

## Implementations

### Aniparse Recognizer

**Extra:** `recognition`
**Requires:** [aniparse](https://pypi.org/project/aniparse/) 2.0+

Uses aniparse to extract metadata from anime filenames. Fast, deterministic, no network calls. Works well for standard fansub naming conventions.

**Example:**
```
Input:  "[SubsPlease] Sousou no Frieren - 18 (1080p) [ABC123].mkv"

Output (RecognitionResult):
{
    "anime_title": "Sousou no Frieren",
    "episode_number": 18,
    "season_number": null,
    "release_group": "SubsPlease",
    "video_resolution": "1080p",
    "source": "aniparse",
    "raw": { ... }
}
```

**Aniparse 2.0 raw output structure:**

The `raw` field contains the native aniparse 2.0 output, which uses a nested format:

```json
{
    "file_name": "[SubsPlease] Sousou no Frieren - 18 (1080p) [ABC123].mkv",
    "file_extension": "mkv",
    "video_resolution": [
        {"video_height": 1080, "scan_method": "p"}
    ],
    "release_group": ["SubsPlease"],
    "series": [
        {
            "title": "Sousou no Frieren",
            "episode": [
                {"number": 18}
            ]
        }
    ],
    "_confidence": 0.582
}
```

Key differences from aniparse 1.x:
- `series` is a list of objects (supports multi-series filenames)
- `episode` is nested under each series entry
- `video_resolution` is a list of objects with `video_height` and `scan_method`
- `release_group` is a list
- `_confidence` score is included

The `AniparseRecognizer` normalizes this into the flat `RecognitionResult` format.

### LLM Recognizer

**Extra:** `llm`

Uses an LLM endpoint (via the [LLM module](LLM.md)) to parse titles that aniparse can't handle — non-standard naming, missing metadata, ambiguous titles, or complex multi-season releases.

The LLM recognizer sends the title to the configured LLM endpoint with a structured prompt asking for JSON output matching `RecognitionResult`.

**When to use LLM over aniparse:**
- Titles with non-standard formatting
- Batch renaming with inconsistent patterns
- When contextual knowledge is needed (e.g., knowing "S2" refers to a specific sequel)
- Streaming page titles (e.g., "Watch Frieren Episode 5 - Crunchyroll")

**Example:**
```
Input:  "Sousou no Frieren S01E05 The Hero's Party Sets Out 1080p WEB-DL"

Prompt sent to LLM:
  "Parse this anime filename/title into structured JSON..."

Output:
{
    "anime_title": "Sousou no Frieren",
    "episode_number": 5,
    "season_number": 1,
    "source": "llm",
    "raw": { ... }
}
```

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
result = recognizer.parse("[SubsPlease] Frieren - 05 (1080p).mkv")
print(result["anime_title"])  # "Frieren"

# Use LLM
recognizer = get_recognizer("llm", base_url="http://localhost:11434/v1", model="llama3")
result = recognizer.parse("Watch Frieren Episode 5 on Crunchyroll")

# Parse multiple titles at once
results = recognizer.parse_batch([
    "[SubsPlease] Frieren - 01 (1080p).mkv",
    "[SubsPlease] Frieren - 02 (1080p).mkv",
])
```
