def main() -> None:
    from mcphybridrag_server.tool import mcp

    # Use stdio: stdout is reserved for MCP protocol messages, so don't print().
    mcp.run(transport="stdio")
