from cli_agent_orchestrator.utils import provider_preferences as prefs


def test_set_and_get_installed_provider(tmp_path, monkeypatch):
    prefs_file = tmp_path / "provider_preferences.json"
    context_dir = tmp_path / "agent-context"

    monkeypatch.setattr(prefs, "PROVIDER_PREFS_FILE", prefs_file)
    monkeypatch.setattr(prefs, "AGENT_CONTEXT_DIR", context_dir)

    prefs.set_installed_provider("developer", "droid")

    assert prefs_file.exists()
    assert prefs.get_installed_provider("developer") == "droid"


def test_get_installed_provider_missing_returns_none(tmp_path, monkeypatch):
    prefs_file = tmp_path / "provider_preferences.json"
    context_dir = tmp_path / "agent-context"

    monkeypatch.setattr(prefs, "PROVIDER_PREFS_FILE", prefs_file)
    monkeypatch.setattr(prefs, "AGENT_CONTEXT_DIR", context_dir)

    assert prefs.get_installed_provider("missing") is None
