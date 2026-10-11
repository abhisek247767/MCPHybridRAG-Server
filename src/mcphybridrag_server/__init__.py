import sys


def main() -> None:
    from mcphybridrag_server.tool import mcp

    mcp.run(transport="streamable-http")
