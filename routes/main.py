from .connect_page import connect_page
from .handle_connect import handle_connect

ALL_ROUTES = [
    ("/connect", ["GET"], connect_page),
    ("/connect", ["POST"], handle_connect),
]


def register_routes(mcp):
    for path, methods, handler in ALL_ROUTES:
        mcp.custom_route(path, methods=methods)(handler)
