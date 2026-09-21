"""Authenticated end-to-end MCP + SQL check; deliberately contains no gold answers."""

import argparse
import asyncio
import os
from urllib.parse import urlparse

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def smoke(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        raise ValueError("Use HTTPS, or HTTP on localhost only.")
    token = os.environ.get("AW_MCP_TOKEN", "")
    if len(token) < 32:
        raise ValueError("Set AW_MCP_TOKEN.")
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {t.name for t in tools.tools} == {
                    "get_schema",
                    "get_business_rules",
                    "query_sql",
                }
                rules = await session.call_tool("get_business_rules", {})
                assert not rules.is_error
                resource = await session.read_resource("adventureworks://business-rules")
                assert resource.contents
                schema = await session.call_tool("get_schema", {})
                assert not schema.is_error
                result = await session.call_tool(
                    "query_sql",
                    {"sql": "SELECT COUNT_BIG(*) AS Orders FROM SalesLT.SalesOrderHeader"},
                )
                assert not result.is_error
                rejected = await session.call_tool(
                    "query_sql", {"sql": "DELETE FROM SalesLT.SalesOrderHeader"}
                )
                assert rejected.is_error
    async with httpx2.AsyncClient(timeout=10) as http:
        assert (await http.post(url, json={})).status_code == 401
    print("PASS: authentication, tools, rules resource, SQL connectivity and write rejection.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(smoke(args.url))
    except Exception as exc:
        # Do not dump HTTP client exceptions that could contain request details.
        print(
            f"FAIL: {type(exc).__name__}; check URL, token, reader configuration and server logs."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
