"""One file per agent role. Each defines NAME, ROLE (one line other agents
see when deciding whom to delegate to), MCP_TOOLS (its allowlist on the MCP
server), OUTPUT (structured result type) and PROMPT_FILE."""

from . import accounting, boss, customer_service, facilities, inventory

ROLES = {m.NAME: m for m in (boss, inventory, accounting, facilities, customer_service)}
