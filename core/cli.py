"""
Kitsune Core CLI.

Usage:
    kitsune track list [--status STATUS] [--type TYPE]
    kitsune track add TITLE [--status STATUS] [--progress N] [--episodes N]
    kitsune track progress MEDIA_ID EPISODE
    kitsune track search QUERY
    kitsune track link MEDIA_ID SERVICE SERVICE_ID
    kitsune track unlink MEDIA_ID SERVICE
    kitsune track delete MEDIA_ID

    kitsune recognize TITLE [--llm]
    kitsune rss parse URL
    kitsune rss match TITLE [--pattern PAT] [--resolution RES] [--group GRP] [--exclude PAT]

    kitsune detect [--type TYPE]
    kitsune server start [--host HOST] [--port PORT] [--db DB]
    kitsune features
"""

import argparse
import json
import logging
import sys


def _setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stderr,
    )


def _json_out(data):
    print(json.dumps(data, indent=2, default=str))


# --- Commands ---

def cmd_features(args):
    from core.features import is_available
    features = ["tracker", "recognition", "downloader", "detection", "media", "llm", "server"]
    for f in features:
        status = "installed" if is_available(f) else "not installed"
        print(f"  {f:15s} {status}")


def cmd_track_list(args):
    from core.database.sqlite import DatabaseConnection
    from core.tracker import get_local_tracker
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa

    db = DatabaseConnection(args.db)
    db.create_tables()
    tracker = get_local_tracker(db.get_session())

    from core.interfaces.database.types.media import MediaStatus, MediaType
    status = MediaStatus(args.status) if args.status else None
    media_type = MediaType(args.type) if args.type else None
    entries = tracker.list_entries(status=status, media_type=media_type)
    _json_out(entries)


def cmd_track_add(args):
    from core.database.sqlite import DatabaseConnection
    from core.tracker import get_local_tracker
    from core.interfaces.database.types.media import MediaType, MediaStatus
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa

    db = DatabaseConnection(args.db)
    db.create_tables()
    tracker = get_local_tracker(db.get_session())

    kwargs = {}
    if args.progress:
        kwargs["progress"] = args.progress
    if args.episodes:
        kwargs["total_episodes"] = args.episodes

    entry = tracker.add_entry(
        title=args.title,
        media_type=MediaType(args.type or "ANIME"),
        status=MediaStatus(args.status or "PLANNED"),
        **kwargs,
    )
    _json_out(entry)


def cmd_track_progress(args):
    from core.database.sqlite import DatabaseConnection
    from core.tracker import get_local_tracker
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa

    db = DatabaseConnection(args.db)
    db.create_tables()
    tracker = get_local_tracker(db.get_session())
    entry = tracker.update_progress(args.media_id, args.episode)
    _json_out(entry)


def cmd_track_search(args):
    from core.database.sqlite import DatabaseConnection
    from core.tracker import get_local_tracker
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa

    db = DatabaseConnection(args.db)
    db.create_tables()
    tracker = get_local_tracker(db.get_session())
    results = tracker.search(args.query)
    _json_out(results)


def cmd_track_link(args):
    from core.database.sqlite import DatabaseConnection
    from core.tracker import get_local_tracker
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa

    db = DatabaseConnection(args.db)
    db.create_tables()
    tracker = get_local_tracker(db.get_session())
    result = tracker.link_service(args.media_id, args.service, args.service_id)
    _json_out(result)


def cmd_track_unlink(args):
    from core.database.sqlite import DatabaseConnection
    from core.tracker import get_local_tracker
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa

    db = DatabaseConnection(args.db)
    db.create_tables()
    tracker = get_local_tracker(db.get_session())
    success = tracker.unlink_service(args.media_id, args.service)
    _json_out({"unlinked": success})


def cmd_track_delete(args):
    from core.database.sqlite import DatabaseConnection
    from core.tracker import get_local_tracker
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa

    db = DatabaseConnection(args.db)
    db.create_tables()
    tracker = get_local_tracker(db.get_session())
    success = tracker.delete_entry(args.media_id)
    _json_out({"deleted": success})


def cmd_recognize(args):
    from core.recognition import get_recognizer
    name = "llm" if args.llm else "aniparse"
    recognizer = get_recognizer(name)
    result = recognizer.parse(args.title)
    _json_out(dict(result))


def cmd_rss_parse(args):
    from core.rss.extractor import Extractor
    extractor = Extractor()
    entries = extractor.extract_feed(args.url)
    _json_out({
        "feed_url": args.url,
        "count": len(entries),
        "entries": [
            {"title": e.title, "magnet_links": e.magnet_links,
             "info_hashes": e.info_hashes, "torrent_links": e.torrent_links}
            for e in entries
        ],
    })


def cmd_rss_match(args):
    from core.rss.matcher import RuleMatcher
    from core.interfaces.rss import MatchRule, FeedEntry

    rule = MatchRule(
        title_pattern=args.pattern or "",
        exclude_pattern=args.exclude or "",
        resolution=[args.resolution] if args.resolution else [],
        release_group=[args.group] if args.group else [],
    )
    matcher = RuleMatcher([rule])
    entry = FeedEntry(title=args.title)
    result = matcher.matches(entry)
    _json_out({"title": args.title, "matches": result})


def cmd_detect(args):
    from core.detection import get_detector
    detector_type = args.type or "process"
    detector = get_detector(detector_type)
    players = detector.detect()
    _json_out({"players": players})


def cmd_server_start(args):
    from core.features import require
    require("server")
    from core.server.app import configure_db, app
    from core.server.auth import configure_auth
    import uvicorn

    configure_db(args.db)
    if args.api_key:
        configure_auth(api_key=args.api_key)
    print(f"Starting kitsune-core server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


# --- Parser ---

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kitsune", description="Kitsune Core CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--db", default="sqlite:///kitsune.db", help="Database URL")

    sub = parser.add_subparsers(dest="command")

    # --- track ---
    track = sub.add_parser("track", help="Local media tracking")
    track_sub = track.add_subparsers(dest="track_cmd")

    t_list = track_sub.add_parser("list", help="List entries")
    t_list.add_argument("--status", help="Filter by status (WATCHING, COMPLETED, etc.)")
    t_list.add_argument("--type", help="Filter by type (ANIME, MANGA)")

    t_add = track_sub.add_parser("add", help="Add entry")
    t_add.add_argument("title", help="Anime/manga title")
    t_add.add_argument("--status", help="Status (default: PLANNED)")
    t_add.add_argument("--type", help="Type (default: ANIME)")
    t_add.add_argument("--progress", type=int, help="Current episode")
    t_add.add_argument("--episodes", type=int, help="Total episodes")

    t_prog = track_sub.add_parser("progress", help="Update progress")
    t_prog.add_argument("media_id", type=int)
    t_prog.add_argument("episode", type=int)

    t_search = track_sub.add_parser("search", help="Search entries")
    t_search.add_argument("query")

    t_link = track_sub.add_parser("link", help="Link to service")
    t_link.add_argument("media_id", type=int)
    t_link.add_argument("service", help="Service name (AniList, MyAnimeList, etc.)")
    t_link.add_argument("service_id", help="ID on the service")

    t_unlink = track_sub.add_parser("unlink", help="Unlink from service")
    t_unlink.add_argument("media_id", type=int)
    t_unlink.add_argument("service", help="Service name")

    t_del = track_sub.add_parser("delete", help="Delete entry")
    t_del.add_argument("media_id", type=int)

    # --- recognize ---
    rec = sub.add_parser("recognize", help="Parse anime title")
    rec.add_argument("title", help="Filename or title to parse")
    rec.add_argument("--llm", action="store_true", help="Use LLM instead of aniparse")

    # --- rss ---
    rss = sub.add_parser("rss", help="RSS feed operations")
    rss_sub = rss.add_subparsers(dest="rss_cmd")

    r_parse = rss_sub.add_parser("parse", help="Parse RSS feed")
    r_parse.add_argument("url", help="RSS feed URL")

    r_match = rss_sub.add_parser("match", help="Test title against rule")
    r_match.add_argument("title")
    r_match.add_argument("--pattern", help="Title regex pattern")
    r_match.add_argument("--exclude", help="Exclude regex pattern")
    r_match.add_argument("--resolution", help="Resolution filter (e.g. 1080p)")
    r_match.add_argument("--group", help="Release group filter")

    # --- detect ---
    det = sub.add_parser("detect", help="Detect media players")
    det.add_argument("--type", choices=["process", "window_title"], help="Detection method")

    # --- server ---
    srv = sub.add_parser("server", help="API server")
    srv_sub = srv.add_subparsers(dest="server_cmd")
    s_start = srv_sub.add_parser("start", help="Start server")
    s_start.add_argument("--host", default="127.0.0.1")
    s_start.add_argument("--port", type=int, default=8000)
    s_start.add_argument("--api-key", help="Require API key for all requests")

    # --- features ---
    sub.add_parser("features", help="List installed features")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)

    cmd_map = {
        "features": cmd_features,
        "recognize": cmd_recognize,
        "detect": cmd_detect,
    }

    if args.command in cmd_map:
        cmd_map[args.command](args)
    elif args.command == "track":
        track_map = {
            "list": cmd_track_list, "add": cmd_track_add,
            "progress": cmd_track_progress, "search": cmd_track_search,
            "link": cmd_track_link, "unlink": cmd_track_unlink,
            "delete": cmd_track_delete,
        }
        fn = track_map.get(args.track_cmd)
        if fn:
            fn(args)
        else:
            parser.parse_args(["track", "--help"])
    elif args.command == "rss":
        rss_map = {"parse": cmd_rss_parse, "match": cmd_rss_match}
        fn = rss_map.get(args.rss_cmd)
        if fn:
            fn(args)
        else:
            parser.parse_args(["rss", "--help"])
    elif args.command == "server":
        if args.server_cmd == "start":
            cmd_server_start(args)
        else:
            parser.parse_args(["server", "--help"])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
