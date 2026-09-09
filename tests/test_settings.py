from pathlib import Path

from geminiroute.config.settings import Settings, load_sources


def write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "sources.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_sources_are_loaded(tmp_path: Path) -> None:
    path = write(tmp_path, """
[[source]]
name = "one"
type = "raw"
url = "https://example.com/sub"

[[source]]
name = "two"
type = "github"
url = "https://api.github.com/repos/o/r/contents/x"
enabled = false
""")
    sources = load_sources(path)
    assert [s.name for s in sources] == ["one", "two"]
    assert sources[0].enabled is True
    assert sources[1].enabled is False


def test_missing_file_is_not_an_error(tmp_path: Path) -> None:
    assert load_sources(tmp_path / "nope.toml") == []


def test_entries_without_a_name_or_url_are_skipped(tmp_path: Path) -> None:
    path = write(tmp_path, """
[[source]]
name = "good"
url = "https://example.com/a"

[[source]]
name = ""
url = "https://example.com/b"

[[source]]
name = "no-url"
""")
    assert [s.name for s in load_sources(path)] == ["good"]


def test_type_defaults_to_raw(tmp_path: Path) -> None:
    path = write(tmp_path, '[[source]]\nname = "a"\nurl = "https://x"\n')
    assert load_sources(path)[0].type == "raw"


def test_env_overrides_are_applied(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GR_CONNECTIVITY_CONCURRENCY", "7")
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    settings = Settings.from_env(tmp_path / "nope.toml")
    assert settings.connectivity_concurrency == 7
    assert settings.gemini_api_key == "secret"


def test_invalid_env_value_falls_back_to_the_default(tmp_path: Path, monkeypatch) -> None:
    """A typo in a workflow env var must not crash the hourly run."""
    monkeypatch.setenv("GR_CONNECTIVITY_CONCURRENCY", "many")
    assert Settings.from_env(tmp_path / "nope.toml").connectivity_concurrency == 100


def test_empty_api_key_is_treated_as_absent(tmp_path: Path, monkeypatch) -> None:
    """GitHub injects an empty string when a secret is not set."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert Settings.from_env(tmp_path / "nope.toml").gemini_api_key is None
