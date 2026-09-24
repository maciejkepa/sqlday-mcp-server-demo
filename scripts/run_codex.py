"""Launch Codex in an exported workspace with its database credentials."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

WORKSPACE_VARIABLES = {
    "with-mcp": ("AW_MCP_TOKEN",),
    "without-mcp": ("AW_SQL_SERVER", "AW_SQL_DATABASE", "AW_SQL_USER", "AW_SQL_PASSWORD"),
}


def without_mcp_overrides(
    executable: str, workspace: Path, environment: dict[str, str]
) -> list[str]:
    result = subprocess.run(
        [executable, "-C", str(workspace), "mcp", "list", "--json"],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        raise ValueError("Cannot read Codex MCP configuration. Run codex mcp list to diagnose it.")
    servers = json.loads(result.stdout)
    if any(server["name"] == "adventureworks" for server in servers):
        return ["-c", "mcp_servers.adventureworks.enabled=false"]
    return []


def launch(workspace: Path) -> int:
    workspace = workspace.resolve()
    if workspace.name not in WORKSPACE_VARIABLES or not (workspace / "AGENTS.md").is_file():
        raise ValueError("Choose an exported with-mcp or without-mcp directory.")
    executable = shutil.which("codex")
    if not executable:
        raise ValueError("Install Codex CLI first: npm install -g @openai/codex")
    allowed = WORKSPACE_VARIABLES[workspace.name]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AW_")}
    for name in allowed:
        if value := os.environ.get(name):
            environment[name] = value
    required = set(allowed) - {"AW_SQL_DATABASE"}
    missing = sorted(name for name in required if not environment.get(name))
    if missing:
        raise ValueError("Load .env with uv run --env-file .env. Missing: " + ", ".join(missing))
    command = [executable, "-C", str(workspace)]
    if workspace.name == "without-mcp":
        command.extend(without_mcp_overrides(executable, workspace, environment))
    return subprocess.call(command, env=environment)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        return launch(args.workspace)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
