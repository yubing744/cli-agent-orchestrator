from cli_agent_orchestrator.utils import agent_profiles


def test_load_agent_profile_expands_claude_code_launcher(tmp_path, monkeypatch):
    store_dir = tmp_path / "agent_store"
    store_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent_profiles, "LOCAL_AGENT_STORE_DIR", store_dir)

    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))

    (store_dir / "dev.md").write_text(
        "---\n"
        "name: dev\n"
        "description: Dev\n"
        "claude_code_launcher: $HOME/bin/ccc\n"
        "---\n"
        "Hello\n"
    )

    profile = agent_profiles.load_agent_profile("dev")
    assert profile.claude_code_launcher == str(fake_home / "bin" / "ccc")


def test_load_agent_profile_expands_repo_root_in_claude_code_launcher(tmp_path, monkeypatch):
    store_dir = tmp_path / "agent_store"
    store_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent_profiles, "LOCAL_AGENT_STORE_DIR", store_dir)

    monkeypatch.setenv("REPO_ROOT", "/tmp/repo")

    (store_dir / "dev.md").write_text(
        "---\n"
        "name: dev\n"
        "description: Dev\n"
        "claude_code_launcher: ${REPO_ROOT}/bin/ccc\n"
        "---\n"
        "Hello\n"
    )

    profile = agent_profiles.load_agent_profile("dev")
    assert profile.claude_code_launcher == "/tmp/repo/bin/ccc"
