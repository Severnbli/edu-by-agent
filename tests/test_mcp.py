"""MCP server: tool list, the preview / confirm_token contract, error mapping, prompts and
resources – through the in-memory MCP client against a fake constructor."""

import json
import re

import anyio
from mcp.shared.memory import create_connected_server_and_client_session
from test_write import BASE, FakeEditor, fake_site

from edu_by import mcp_server as ms
from edu_by.config import Settings
from edu_by.site import SessionExpired

READS = {
    "edu_session_status",
    "edu_tree",
    "edu_find_section",
    "edu_section",
    "edu_objects",
    "edu_object",
    "edu_types",
    "edu_trash_list",
}
WRITES = {
    "edu_object_update",
    "edu_object_create",
    "edu_object_copy",
    "edu_object_move",
    "edu_object_sort",
    "edu_object_upload_image",
    "edu_object_trash",
    "edu_section_add",
    "edu_section_update",
    "edu_section_move",
    "edu_section_delete",
    "edu_trash_restore",
    "edu_trash_purge",
}


def runtime(factory) -> ms.Runtime:
    return ms.Runtime(
        Settings(constructor_url=f"{BASE}/explorer.aspx", request_delay=0), site_factory=factory
    )


def call(server, name: str, args: dict):
    async def go():
        async with create_connected_server_and_client_session(server) as client:
            return await client.call_tool(name, args)

    return anyio.run(go)


def data(result) -> dict:
    assert not result.isError, result.content[0].text
    return json.loads(result.content[0].text)


def test_tools_and_annotations():
    server = ms.build_server(runtime(lambda: None))

    async def go():
        async with create_connected_server_and_client_session(server) as client:
            return (await client.list_tools()).tools

    tools = {t.name: t for t in anyio.run(go)}
    assert set(tools) == READS | WRITES
    for name in READS:
        assert tools[name].annotations.readOnlyHint is True
    for name in WRITES:
        a = tools[name].annotations
        assert a.readOnlyHint is False and a.idempotentHint is False
        assert a.destructiveHint is (
            name in {"edu_object_trash", "edu_section_delete", "edu_trash_purge"}
        )
        assert "confirm_token" in tools[name].inputSchema["properties"]


def test_update_previews_then_applies_with_the_token():
    fake = FakeEditor()
    server = ms.build_server(runtime(lambda: fake_site(fake.handler)))
    args = {"id": "1063", "values": {"name": "новый"}}
    preview = data(call(server, "edu_object_update", args))
    assert preview["applied"] is False and fake.posts == []
    assert preview["preview"]["changes"] == {"name": {"before": "основной", "after": "новый"}}
    token = preview["preview"]["token"]
    done = data(call(server, "edu_object_update", {**args, "confirm_token": token}))
    assert done["result"]["verified"] is True and len(fake.posts) == 1


def test_wrong_token_is_refused():
    fake = FakeEditor()
    server = ms.build_server(runtime(lambda: fake_site(fake.handler)))
    res = call(
        server,
        "edu_object_update",
        {"id": "1063", "values": {"name": "x"}, "confirm_token": "000000000000"},
    )
    assert res.isError and "TokenMismatch" in res.content[0].text
    assert fake.posts == []


def test_session_expired_becomes_a_tool_error_and_drops_the_site():
    def expired():
        raise SessionExpired("no saved session")

    rt = runtime(expired)
    res = call(ms.build_server(rt), "edu_object", {"id": "1063"})
    assert res.isError and "./edu session login" in res.content[0].text
    assert rt._site is None


def test_upload_refuses_files_outside_the_repo(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    res = call(
        ms.build_server(runtime(lambda: None)),
        "edu_object_upload_image",
        {"id": "1", "path": str(f)},
    )
    assert res.isError and "inside the repository" in res.content[0].text


def test_every_skill_has_an_mcp_scenario_naming_real_tools():
    skills = sorted(p.parent.name for p in ms.SKILLS.glob("*/SKILL.md"))
    prompts = {name: text for name, _, text in ms.skill_prompts()}
    assert sorted(n.replace("_", "-") for n in prompts) == skills
    known = READS | WRITES | set(prompts)
    for name, text in prompts.items():
        used = set(re.findall(r"\bedu_[a-z_]+\b", text))
        assert used <= known, (name, used - known)


def test_prompts_and_resources_are_listed():
    server = ms.build_server(runtime(lambda: None))

    async def go():
        async with create_connected_server_and_client_session(server) as client:
            prompts = (await client.list_prompts()).prompts
            res = (await client.list_resources()).resources
            got = await client.get_prompt("edu_publish_news", {"request": "новость о лагере"})
            text = await client.read_resource("edu://knowledge/model.md")
            return prompts, res, got, text

    prompts, res, got, text = anyio.run(go)
    assert "edu_publish_news" in {p.name for p in prompts}
    assert "edu://knowledge/model.md" in {str(r.uri) for r in res}
    body = got.messages[0].content.text
    assert "confirm_token" in body and "новость о лагере" in body
    assert text.contents[0].text.startswith("---") or "#" in text.contents[0].text
