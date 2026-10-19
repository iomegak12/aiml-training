"""Server assembly: repository, tools, resources, prompts, health route, banner and HTTP run."""

from __future__ import annotations

import argparse
import asyncio

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_servers.crm_support import __version__
from mcp_servers.crm_support.banner import print_banner
from mcp_servers.crm_support.config import ServerSettings
from mcp_servers.crm_support.db import Repository
from mcp_servers.crm_support.prompts import register_prompts
from mcp_servers.crm_support.resources import register_resources
from mcp_servers.crm_support.seed import seed_database
from mcp_servers.crm_support.tools import register_tools

INSTRUCTIONS = (
    "CRM and support ticket server. Use get_customer_profile / search_customer_profiles to identify customers, "
    "get_tickets_by_customer / search_tickets for support history, and register_ticket / resolve_ticket to change "
    "tickets. Customers cannot be created or edited here. Read crm://schema for fields, enums and business rules."
)


def create_server(repo: Repository) -> FastMCP:
    """Build the FastMCP server with all tools, resources, prompts and the ``/health`` route."""
    mcp = FastMCP(name="crm-support", instructions=INSTRUCTIONS, version=__version__)
    register_tools(mcp, repo)
    register_resources(mcp, repo)
    register_prompts(mcp, repo)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        """Liveness and record counts for ``make mcp-server-status`` (not a Docker HEALTHCHECK)."""
        return JSONResponse({"status": "ok", "server": "crm-support", "version": __version__, **repo.counts()})

    return mcp


async def _capabilities(mcp: FastMCP) -> tuple[list[str], list[str], list[str]]:
    """Names of the registered tools, resources (incl. templates) and prompts, for the banner."""
    tools = [t.name for t in await mcp.list_tools()]
    resources = [str(r.uri) for r in await mcp.list_resources()]
    resources += [t.uri_template for t in await mcp.list_resource_templates()]
    prompts = [p.name for p in await mcp.list_prompts()]
    return sorted(tools), sorted(resources), sorted(prompts)


def main(argv: list[str] | None = None) -> None:
    """Entry point: initialise and seed the database, print the banner and serve over HTTP."""
    parser = argparse.ArgumentParser(description="CRM & Support MCP server")
    parser.add_argument("--reset-seed", action="store_true", help="delete all data and reload the seed, then exit")
    args = parser.parse_args(argv)

    settings = ServerSettings.from_env()
    repo = Repository(settings.db_path)
    repo.initialize()
    seed_status = seed_database(repo, enabled=settings.seed_on_start, force=args.reset_seed)
    if args.reset_seed:
        print(f"CRM database reset: {seed_status}")
        return

    mcp = create_server(repo)
    tools, resources, prompts = asyncio.run(_capabilities(mcp))
    print_banner(settings, repo.counts(), seed_status, tools, resources, prompts)
    mcp.run(transport="http", host=settings.host, port=settings.port, path=settings.path,
            log_level=settings.log_level, show_banner=False)
