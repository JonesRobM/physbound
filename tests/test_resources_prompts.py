"""MCP resource and prompt tests — formula reference resource and review prompts."""

import asyncio

import pytest

from physbound import server as server_module
from physbound.server import _formulas_markdown, mcp

try:
    from fastmcp.client import Client

    HAS_CLIENT = True
except ImportError:
    HAS_CLIENT = False


def run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture()
def client():
    """Create an MCP client connected to the PhysBound server."""
    if not HAS_CLIENT:
        pytest.skip("fastmcp.client not available")
    return Client(mcp)


class TestFormulaResource:
    def test_resource_listed(self, client):
        async def check():
            async with client:
                resources = await client.list_resources()
                uris = {str(r.uri) for r in resources}
                assert "docs://physbound/formulas" in uris

        run_async(check())

    def test_resource_content_round_trip(self, client):
        async def check():
            async with client:
                contents = await client.read_resource("docs://physbound/formulas")
                text = contents[0].text
                assert "PhysBound Formula Reference" in text
                assert "Shannon" in text
                assert "Boltzmann" in text

        run_async(check())

    def test_loader_dev_fallback_reads_repo_docs(self):
        # In a dev checkout the wheel data file does not exist, so the loader
        # must fall back to the repository's docs/formulas.md.
        text = _formulas_markdown()
        assert "PhysBound Formula Reference" in text

    def test_loader_prefers_packaged_copy(self, monkeypatch, tmp_path):
        # Simulate an installed wheel where physbound/data/formulas.md exists.
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "formulas.md").write_text("# Packaged copy", encoding="utf-8")

        monkeypatch.setattr(server_module.importlib.resources, "files", lambda _package: tmp_path)
        assert _formulas_markdown() == "# Packaged copy"


class TestPrompts:
    def test_prompts_registered(self, client):
        async def check():
            async with client:
                prompts = await client.list_prompts()
                names = {p.name for p in prompts}
                assert {"review_link_budget", "validate_physics_claims"} <= names
                for prompt in prompts:
                    assert prompt.description, f"{prompt.name} has no description"

        run_async(check())

    def test_review_link_budget_renders(self, client):
        async def check():
            async with client:
                result = await client.get_prompt(
                    "review_link_budget", {"link_budget": "EIRP 53 dBm, 500 Mbps in 20 MHz"}
                )
                text = result.messages[0].content.text
                assert "rf_link_budget" in text
                assert "EIRP 53 dBm" in text

        run_async(check())

    def test_validate_physics_claims_renders(self, client):
        async def check():
            async with client:
                result = await client.get_prompt(
                    "validate_physics_claims", {"text": "Our radar sees 0.01 m^2 at 200 km."}
                )
                text = result.messages[0].content.text
                assert "physbound tool" in text
                assert "200 km" in text

        run_async(check())
