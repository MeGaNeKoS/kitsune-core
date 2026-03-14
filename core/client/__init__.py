from core.features import is_available
from core.interfaces.torrent.client import Client, ClientMapping


def _get_clients():
    clients = {}
    if is_available("downloader"):
        from core.client.qbittorrent import QBittorrent
        clients[QBittorrent.get_name()] = QBittorrent
    return clients


def get_client(config: dict) -> Client:
    name = config.pop(ClientMapping.NAME.value, None)
    clients = _get_clients()
    client = clients.get(name)
    if client:
        return client(**config)

    available = list(clients.keys()) or ["none — install kitsune-core[downloader]"]
    raise ValueError(f"Client {name!r} not found. Available: {', '.join(available)}")
