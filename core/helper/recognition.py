import logging
import warnings

from devlog import log_on_error

from core.features import require

require("recognition")
import aniparse

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
    return aniparse.parse(file_name) or {}
