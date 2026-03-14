import logging

from devlog import log_on_error

from core.features import require

require("recognition")
import aniparse


@log_on_error(logging.ERROR, "Failed to parse title: {error!r}")
def parse(file_name, track):
    """
    Parse file name and return a dict of parsed result
    """
    # TODO: update this once the aniparse finished
    if track:
        anime = aniparse.parse(file_name)
    else:
        anime, _ = aniparse.parse(file_name, False)
    if anime.get("anilist", 0) == 0:
        anime["anime_type"] = "unknown"

    return anime
