import asyncio
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
import uvicorn

from app import database, server
from app.sql_policy import QueryError, validate_sql
from scripts import azure, configure
from scripts.export_workspaces import export
from scripts.smoke import smoke


def test_configuration_preserves_existing_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(configure, "ROOT", tmp_path)
    example = Path(__file__).resolve().parents[1] / ".env.example"
    (tmp_path / ".env.example").write_text(example.read_text())
    monkeypatch.setattr("sys.argv", ["configure", "--admin"])
    configure.main()
    before = (tmp_path / ".env").read_bytes()
    assert b"replace-" not in before
    assert (tmp_path / ".env.admin").is_file()
    with pytest.raises(SystemExit):
        configure.main()
    assert (tmp_path / ".env").read_bytes() == before


def test_workspaces_do_not_include_answers_or_secrets(tmp_path):
    target = export(tmp_path / "workspaces", "http://127.0.0.1:8000/mcp")
    for name in ("with-mcp", "without-mcp"):
        workspace = target / name
        assert (workspace / "example-questions.md").is_file()
        assert "Oczekiwane odpowiedzi" not in (workspace / "example-questions.md").read_text(
            encoding="utf-8"
        )
        assert not (workspace / ".env").exists()
        assert not (workspace / "presenter").exists()
        assert not list(workspace.rglob("business-rules.md"))
        assert ".env" in (workspace / ".gitignore").read_text()
    config = tomllib.loads((target / "with-mcp/.codex/config.toml").read_text())
    assert config["mcp_servers"]["adventureworks"]["bearer_token_env_var"] == "AW_MCP_TOKEN"
    assert not (target / "without-mcp/app/server.py").exists()
    with pytest.raises(ValueError):
        export(target, "http://127.0.0.1:8000/mcp")


def test_build_context_has_rules_but_no_local_files(tmp_path):
    azure.copy_build_context(tmp_path)
    files = {
        path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()
    }
    assert files == set(azure.BUILD_FILES)
    assert (tmp_path / "docs/business-rules.md").read_bytes() == server.RULES_PATH.read_bytes()


def test_deployment_parameters_removed_after_failure(monkeypatch):
    paths = []

    def fail(*args):
        path = Path(args[-1][1:])
        paths.append(path)
        assert json.loads(path.read_text())["parameters"]["mcpToken"]["value"] == "secret"
        raise RuntimeError("deployment failed")

    monkeypatch.setattr(azure, "az", fail)
    with pytest.raises(RuntimeError):
        azure.deploy_template("demo-rg", "main.bicep", {"mcpToken": "secret"})
    assert not paths[0].exists()


def test_firewall_only_removes_its_own_obsolete_rules(monkeypatch):
    calls = []

    def fake_az(*args):
        calls.append(args)
        if args[:2] == ("containerapp", "show"):
            return {"properties": {"outboundIpAddresses": ["203.0.113.1"]}}
        if args[:4] == ("sql", "server", "firewall-rule", "list"):
            return [
                {"name": name}
                for name in (
                    "unrelated",
                    "mcp-demo-203-0-113-1",
                    "mcp-demo-192-0-2-1",
                )
            ]

    monkeypatch.setattr(azure, "az", fake_az)
    args = SimpleNamespace(
        resource_group="demo",
        sql_resource_group="sql",
        sql_server="server",
        app_name="demo",
        client_ip="198.51.100.1",
    )
    azure.firewall(args)
    deletes = [
        call[-1] for call in calls if call[:4] == ("sql", "server", "firewall-rule", "delete")
    ]
    assert deletes == ["mcp-demo-192-0-2-1"]


def test_invalid_firewall_addresses_cannot_change_rules(monkeypatch):
    calls = []

    def fake_az(*args):
        calls.append(args)
        return {"properties": {"outboundIpAddresses": ["203.0.113.1", "0.0.0.0"]}}

    monkeypatch.setattr(azure, "az", fake_az)
    args = SimpleNamespace(resource_group="demo", app_name="demo", client_ip="198.51.100.1")
    with pytest.raises(ValueError):
        azure.firewall(args)
    assert len(calls) == 1


def test_copy_refuses_existing_database(monkeypatch):
    calls = []

    def fake_az(*args):
        calls.append(args)
        return [{"name": database.DATABASE_NAME}]

    monkeypatch.setattr(azure, "az", fake_az)
    args = SimpleNamespace(resource_group="demo", sql_server="server", source_database="original")
    with pytest.raises(ValueError):
        azure.copy_database(args)
    assert len(calls) == 1


def test_mcp_smoke_with_stub_database(monkeypatch):
    monkeypatch.setenv("AW_MCP_TOKEN", "test-token-" * 4)
    monkeypatch.setattr(database, "get_schema", lambda schema=None: {"objects": []})

    def query(sql):
        validate_sql(sql)
        return {"columns": ["Orders"], "rows": [[6]], "row_count": 1, "truncated": False}

    monkeypatch.setattr(database, "query_sql", query)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        process = uvicorn.Server(uvicorn.Config(server.create_app(), log_level="error"))
        thread = threading.Thread(target=process.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not process.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert process.started
            asyncio.run(smoke(f"http://127.0.0.1:{port}/mcp"))
        finally:
            process.should_exit = True
            thread.join(timeout=10)
        assert not thread.is_alive()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM SalesLT.Customer",
        "SELECT * INTO SalesLT.Copy FROM SalesLT.Customer",
        "SELECT * FROM otherdb.SalesLT.Customer",
        "SELECT * FROM sys.sql_logins",
    ],
)
def test_sql_rejects_writes_and_unlisted_sources(sql):
    with pytest.raises(QueryError):
        validate_sql(sql)


@pytest.mark.parametrize("variant", ["with-mcp", "without-mcp"])
def test_codex_launcher_passes_only_variant_credentials(tmp_path, monkeypatch, variant):
    from scripts.run_codex import launch

    target = export(tmp_path / "workspaces", "http://127.0.0.1:8000/mcp")
    values = {
        "AW_MCP_TOKEN": "test-token",
        "AW_SQL_SERVER": "test-server",
        "AW_SQL_USER": "reader",
        "AW_SQL_PASSWORD": "reader-password",
        "AW_ADMIN_PASSWORD": "admin-password",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("scripts.run_codex.shutil.which", lambda name: "/tools/codex")
    monkeypatch.setattr(
        "scripts.run_codex.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout='[{"name": "adventureworks"}]'
        ),
    )
    calls = []

    def capture(command, *, env):
        calls.append((command, env))
        return 7

    monkeypatch.setattr("scripts.run_codex.subprocess.call", capture)
    assert launch(target / variant) == 7
    command, environment = calls[0]
    assert command[:3] == ["/tools/codex", "-C", str(target / variant)]
    assert "AW_ADMIN_PASSWORD" not in environment
    if variant == "with-mcp":
        assert environment["AW_MCP_TOKEN"] == "test-token"
        assert not any(name.startswith("AW_SQL_") for name in environment)
    else:
        assert "AW_MCP_TOKEN" not in environment
        assert environment["AW_SQL_PASSWORD"] == "reader-password"
        assert command[-2:] == ["-c", "mcp_servers.adventureworks.enabled=false"]


@pytest.mark.parametrize(
    "transport", [None, 'url = "http://127.0.0.1:8000/mcp"', 'command = "unused-demo-command"']
)
def test_without_mcp_configuration_with_real_codex(tmp_path, monkeypatch, transport):
    from scripts.run_codex import without_mcp_overrides

    executable = shutil.which("codex")
    if not executable:
        pytest.skip("Codex CLI is not installed")
    monkeypatch.chdir(tmp_path)
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    configuration = f"[mcp_servers.adventureworks]\n{transport}\n" if transport else ""
    (codex_home / "config.toml").write_text(configuration, encoding="utf-8")
    environment = dict(os.environ, CODEX_HOME=str(codex_home))
    overrides = without_mcp_overrides(executable, tmp_path, environment)
    result = subprocess.run(
        [executable, "-C", str(tmp_path), "mcp", "list", "--json", *overrides],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    servers = json.loads(result.stdout)
    if transport:
        assert servers[0]["name"] == "adventureworks"
        assert servers[0]["enabled"] is False
    else:
        assert overrides == []
        assert servers == []
    assert (codex_home / "config.toml").read_text(encoding="utf-8") == configuration
