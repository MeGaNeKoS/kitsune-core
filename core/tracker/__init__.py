from core.interfaces.tracker.local import BaseLocalTracker
from core.interfaces.tracker.service import BaseServiceTracker
from core.features import is_available


def get_local_tracker(session) -> BaseLocalTracker:
    from core.tracker.local import LocalTracker
    return LocalTracker(session)


def get_service_tracker(name: str, **kwargs) -> BaseServiceTracker:
    trackers = {}

    if is_available("tracker"):
        from core.tracker.services.anilist import AnilistTracker
        trackers[AnilistTracker.get_name()] = AnilistTracker

    # MAL, Kitsu, AniDB use urllib3 (base dep), no extra needed
    from core.tracker.services.mal import MALTracker
    from core.tracker.services.kitsu import KitsuTracker
    from core.tracker.services.anidb import AniDBTracker
    trackers[MALTracker.get_name()] = MALTracker
    trackers[KitsuTracker.get_name()] = KitsuTracker
    trackers[AniDBTracker.get_name()] = AniDBTracker

    tracker_cls = trackers.get(name)
    if tracker_cls:
        return tracker_cls(**kwargs)

    available = list(trackers.keys())
    raise ValueError(f"Service tracker {name!r} not found. Available: {', '.join(available)}")
