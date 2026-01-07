from cli_agent_orchestrator.utils import context_files as ctx


def test_write_and_get_context_provider(tmp_path, monkeypatch):
    source = tmp_path / "src.md"
    source.write_text("---\nname: developer\n---\ncontent\n")

    dest_dir = tmp_path / "agent-context"
    monkeypatch.setattr(ctx, "AGENT_CONTEXT_DIR", dest_dir)

    dest = dest_dir / "developer.md"
    dest_dir.mkdir(parents=True, exist_ok=True)

    ctx.write_context_with_provider(source, "droid", dest)

    assert dest.exists()
    assert ctx.get_context_provider("developer") == "droid"


def test_get_context_provider_missing(tmp_path, monkeypatch):
    dest_dir = tmp_path / "agent-context"
    monkeypatch.setattr(ctx, "AGENT_CONTEXT_DIR", dest_dir)

    assert ctx.get_context_provider("missing") is None


def test_get_context_working_directory_expands_vars_and_user(tmp_path, monkeypatch):
    dest_dir = tmp_path / "agent-context"
    monkeypatch.setattr(ctx, "AGENT_CONTEXT_DIR", dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))

    (dest_dir / "dev.md").write_text("---\nworking_directory: ~/$HOME_SUBDIR\n---\n")
    monkeypatch.setenv("HOME_SUBDIR", "repo")

    assert ctx.get_context_working_directory("dev") == str(fake_home / "repo")


def test_get_context_working_directory_expands_repo_root(tmp_path, monkeypatch):
    dest_dir = tmp_path / "agent-context"
    monkeypatch.setattr(ctx, "AGENT_CONTEXT_DIR", dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("REPO_ROOT", "/tmp/repo")
    (dest_dir / "dev.md").write_text("---\nworking_directory: $REPO_ROOT/sub\n---\n")

    assert ctx.get_context_working_directory("dev") == "/tmp/repo/sub"
