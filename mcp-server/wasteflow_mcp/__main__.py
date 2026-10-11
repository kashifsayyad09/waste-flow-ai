import logging
import sys

import uvicorn

from wasteflow_mcp.app import create_app
from wasteflow_mcp.config import MCPSettings


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = MCPSettings()
    problem = settings.token_problem()
    if problem:
        print(f"Refusing to start: {problem}", file=sys.stderr)
        return 2
    if settings.mcp_host not in ("127.0.0.1", "localhost", "::1"):
        logging.getLogger("wasteflow.mcp").warning(
            "MCP is listening on %s. Only allow the backend's security group to reach port %s.", settings.mcp_host, settings.mcp_port)
    uvicorn.run(create_app(settings), host=settings.mcp_host, port=settings.mcp_port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
