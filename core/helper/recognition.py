import logging
import warnings

from devlog import log_on_error

from core.features import require
from core.recognition import get_recognizer

require("recognition")
warnings.warn(
    "core.helper.recognition is deprecated. Use core.recognition.get_recognizer() instead.",
    DeprecationWarning,
    stacklevel=2,
)


@log_on_error(logging.ERROR, "Failed to parse title: {error!r}")
def parse(file_name, track=False):
    """
    Parse file name and return a dict of parsed result.
    Deprecated: use core.recognition.get_recognizer('aniparse').parse() instead.
    """
    # Keep the legacy function as a compatibility shim, but route parsing
    # through the public recognizer interface so the old module does not
    # maintain a second implementation path.
    return get_recognizer("aniparse").parse(file_name) or {}
