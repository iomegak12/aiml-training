"""CRM profile and support ticket MCP server (FastMCP, SQLite, streamable HTTP).

Modules:

- ``config``    -- settings from environment variables
- ``models``    -- Pydantic models and enums for customers and tickets
- ``db``        -- SQLite repository (schema, queries, paging)
- ``rules``     -- business rules (inactive customers, resolution, enums, duplicates)
- ``tools``     -- MCP tools
- ``resources`` -- MCP resources
- ``prompts``   -- MCP prompts
- ``seed``      -- loading the deterministic demo data
- ``banner``    -- colourful startup console
- ``server``    -- server assembly and entry point
"""

__version__ = "0.1.0"
