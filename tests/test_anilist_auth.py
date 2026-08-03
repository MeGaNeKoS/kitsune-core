import threading
import urllib.request
from http.server import HTTPServer

from core.service.anilist import AnilistAuthClient


def _serve_once(server):
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    return thread


def test_oauth_callback_reports_authorization_error_without_code():
    codes = []
    errors = []
    server = HTTPServer(
        ("127.0.0.1", 0),
        AnilistAuthClient._make_handler(codes.append, lambda code, detail: errors.append((code, detail))),
    )
    thread = _serve_once(server)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/?error=access_denied&error_description=User+cancelled",
        ) as response:
            body = response.read().decode()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert errors == [("access_denied", "User cancelled")]
    assert codes == []
    assert "not completed" in body


def test_oauth_callback_reports_code_and_success_message():
    codes = []
    server = HTTPServer(("127.0.0.1", 0), AnilistAuthClient._make_handler(codes.append))
    thread = _serve_once(server)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/?code=one-time-code",
        ) as response:
            body = response.read().decode()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert codes == ["one-time-code"]
    assert "Authentication successful" in body
