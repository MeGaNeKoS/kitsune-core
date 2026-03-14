# Detection

The detection module identifies running media players and extracts information about what the user is currently watching.

## Architecture

```
┌───────────────┐
│ BaseDetector  │ (core/interfaces/detection/base.py)
└───────┬───────┘
        │
  ┌─────┴───────────┐
  │                 │
  ▼                 ▼
ProcessDetector   WindowTitleDetector (future)
```

## Interface

**File:** `core/interfaces/detection/base.py` → `BaseDetector`

### Methods

| Method | Description |
|--------|-------------|
| `detect()` | Find all running media players and return info about each |
| `is_player_running(player_name)` | Check if a specific player is running |

### DetectedMedia

```python
class DetectedMedia(TypedDict, total=False):
    player: str            # player identifier (e.g. "mpv", "vlc")
    pid: int               # process ID
    title: Optional[str]   # window title or media title if extractable
    file_path: Optional[str] # file path if detectable
```

## Implementations

### Process Detector

**Extra:** `detection`
**File:** `core/detection/process.py`

Uses [psutil](https://pypi.org/project/psutil/) to scan running processes and match against known media player executables.

**Supported players:**

| Player | Process names |
|--------|--------------|
| mpv | `mpv`, `mpv.exe` |
| VLC | `vlc`, `vlc.exe` |
| MPC-HC | `mpc-hc.exe`, `mpc-hc64.exe` |
| MPC-BE | `mpc-be.exe`, `mpc-be64.exe` |
| PotPlayer | `PotPlayerMini.exe`, `PotPlayerMini64.exe` |
| Kodi | `kodi`, `kodi.exe` |

### Window Title Detector (Future)

Will use OS-specific APIs to extract the window title from running media players. The window title often contains the filename or media title being played.

- **Windows:** Win32 API (`EnumWindows`, `GetWindowText`)
- **Linux:** X11/Wayland window properties
- **macOS:** Accessibility API

## Usage with Tracker

The typical flow:

```
1. Detection module finds "mpv" playing "Frieren - 05.mkv"
2. Recognition module parses the filename → "Frieren", episode 5
3. Tracker updates local progress → episode 5
4. Sync manager pushes to AniList/MAL
```

## Implementing a New Detector

```python
from core.interfaces.detection import BaseDetector, DetectedMedia

class WindowTitleDetector(BaseDetector):
    _name = "window_title"

    def detect(self) -> list[DetectedMedia]:
        # Use OS APIs to get window titles
        ...

    def is_player_running(self, player_name: str) -> bool:
        return any(d["player"] == player_name for d in self.detect())
```
