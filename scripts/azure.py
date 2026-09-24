"""Provision the demo database, deploy the MCP server and update its SQL firewall."""

import argparse
import ipaddress
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.database import DATABASE_NAME

ROOT = Path(__file__).resolve().parent.parent
BUILD_FILES = (
    "Dockerfile",
    "pyproject.toml",
    "uv.lock",
    "docs/business-rules.md",
    "app/__init__.py",
    "app/server.py",
    "app/database.py",
    "app/sql_policy.py",
    "app/logging.json",
)


def az(*arguments: str):
    executable = shutil.which("az")
    if not executable:
        raise ValueError("Install Azure CLI and run az login first.")
    result = subprocess.run(
        [executable, *arguments, "--only-show-errors", "--output", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Azure CLI failed: {' '.join(arguments[:3])}. Check login, permissions and Azure deployment/build logs."
        )
    return json.loads(result.stdout) if result.stdout.strip() else None


def required_env(name: str, minimum: int = 1) -> str:
    value = os.environ.get(name, "")
    if len(value) < minimum or value.startswith("replace-"):
        raise ValueError(f"Set {name} (at least {minimum} characters).")
    return value


def ipv4(value: str) -> str:
    address = ipaddress.IPv4Address(value)
    if address.is_unspecified:
        raise ValueError("0.0.0.0 would allow all Azure services; provide a specific IPv4 address.")
    return str(address)


def deploy_template(group: str, template: str, parameters: dict):
    document = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {key: {"value": value} for key, value in parameters.items()},
    }
    with tempfile.TemporaryDirectory(prefix="sqlday-parameters-") as directory:
        path = Path(directory) / "parameters.json"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream)
        return az(
            "deployment",
            "group",
            "create",
            "-g",
            group,
            "--template-file",
            str(ROOT / "infra" / template),
            "--parameters",
            "@" + str(path),
        )


def copy_build_context(destination: Path) -> None:
    for name in BUILD_FILES:
        source = ROOT / name
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Missing or symlinked build input: {name}")
    for name in BUILD_FILES:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)


def database(args) -> None:
    password = required_env("AW_ADMIN_PASSWORD", 16)
    group = az("group", "show", "-n", args.resource_group)
    parameters = {
        "location": group["location"],
        "administratorLogin": os.getenv("AW_ADMIN_USER", "sqldayadmin"),
        "administratorPassword": password,
        "presenterIPv4": ipv4(args.client_ip),
    }
    if args.sql_server:
        parameters["sqlServerName"] = args.sql_server
    result = deploy_template(args.resource_group, "database.bicep", parameters)
    fqdn = result["properties"]["outputs"]["sqlFqdn"]["value"]
    print(f"Set AW_SQL_SERVER={fqdn} in .env, then run presenter.prepare --reset-demo.")


def copy_database(args) -> None:
    databases = az("sql", "db", "list", "-g", args.resource_group, "-s", args.sql_server)
    if any(item["name"].casefold() == DATABASE_NAME.casefold() for item in databases):
        raise ValueError("The demo database already exists; refusing to overwrite it.")
    az(
        "sql",
        "db",
        "copy",
        "-g",
        args.resource_group,
        "-s",
        args.sql_server,
        "-n",
        args.source_database,
        "--dest-name",
        DATABASE_NAME,
    )
    print("Database copied. Set AW_SQL_SERVER in .env, then run presenter.prepare --reset-demo.")


def firewall(args) -> None:
    client_ip = ipv4(args.client_ip)
    app = az("containerapp", "show", "-g", args.resource_group, "-n", args.app_name)
    outbound = app["properties"].get("outboundIpAddresses")
    if not outbound:
        raise ValueError("No outbound IPs returned; inspect the Container Apps network.")
    addresses = sorted({ipv4(address) for address in outbound} | {client_ip})
    prefix = f"mcp-{args.app_name}-"
    wanted = {prefix + address.replace(".", "-"): address for address in addresses}
    common = ("-g", args.sql_resource_group, "-s", args.sql_server)
    for name, address in wanted.items():
        az(
            "sql",
            "server",
            "firewall-rule",
            "create",
            *common,
            "-n",
            name,
            "--start-ip-address",
            address,
            "--end-ip-address",
            address,
        )
    for rule in az("sql", "server", "firewall-rule", "list", *common):
        if rule["name"].startswith(prefix) and rule["name"] not in wanted:
            az("sql", "server", "firewall-rule", "delete", *common, "-n", rule["name"])
    print("SQL firewall synchronized. Run scripts.smoke to verify connectivity.")


def deploy(args) -> None:
    sql_password = required_env("AW_SQL_PASSWORD", 16)
    token = required_env("AW_MCP_TOKEN", 32)
    ipv4(args.client_ip)
    server = az("sql", "server", "show", "-g", args.sql_resource_group, "-n", args.sql_server)
    location = server["location"]
    az("group", "create", "-n", args.resource_group, "-l", location)
    deploy_template(
        args.resource_group,
        "registry.bicep",
        {
            "registryName": args.registry_name,
            "location": location,
        },
    )
    print("Building container image in ACR...")
    with tempfile.TemporaryDirectory(prefix="sqlday-acr-") as directory:
        context = Path(directory)
        copy_build_context(context)
        az(
            "acr",
            "build",
            "-r",
            args.registry_name,
            "-g",
            args.resource_group,
            "--image",
            f"adventureworks-mcp:{args.image_tag}",
            "--file",
            str(context / "Dockerfile"),
            "--no-logs",
            str(context),
        )
    print("Deploying Container App...")
    result = deploy_template(
        args.resource_group,
        "main.bicep",
        {
            "location": location,
            "appName": args.app_name,
            "registryName": args.registry_name,
            "imageTag": args.image_tag,
            "sqlServer": server["fullyQualifiedDomainName"],
            "sqlUser": os.getenv("AW_SQL_USER", "aw_demo_reader"),
            "sqlPassword": sql_password,
            "mcpToken": token,
        },
    )
    firewall(args)
    print("MCP endpoint: " + result["properties"]["outputs"]["mcpUrl"]["value"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, function in (
        ("database", database),
        ("copy-database", copy_database),
        ("deploy", deploy),
        ("firewall", firewall),
    ):
        descriptions = {
            "database": "Create Azure SQL with the AdventureWorksLT sample",
            "copy-database": "Copy an existing database without overwriting the demo",
            "deploy": "Build and deploy the MCP container",
            "firewall": "Synchronize SQL firewall rules for the app",
        }
        child = sub.add_parser(command, help=descriptions[command])
        child.set_defaults(function=function)
        child.add_argument("--resource-group", required=True)
        child.add_argument("--sql-server", required=command != "database")
        if command != "copy-database":
            child.add_argument("--client-ip", required=True, type=ipv4)
        if command in {"deploy", "firewall"}:
            child.add_argument("--sql-resource-group", required=True)
            child.add_argument("--app-name", default="sqlday-mcp")
        if command == "deploy":
            child.add_argument("--registry-name", required=True)
            child.add_argument("--image-tag", default=datetime.now(UTC).strftime("%Y%m%d%H%M%S"))
        if command == "copy-database":
            child.add_argument("--source-database", required=True)
    args = parser.parse_args()
    for field in (
        "resource_group",
        "sql_resource_group",
        "sql_server",
        "app_name",
        "registry_name",
        "image_tag",
        "source_database",
    ):
        value = getattr(args, field, None)
        if value and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value):
            parser.error(
                f"Invalid {field.replace('_', '-')}; use letters, digits, dots, hyphens or underscores."
            )
    try:
        args.function(args)
    except (ValueError, RuntimeError, OSError) as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
