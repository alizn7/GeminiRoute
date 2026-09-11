import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import GeoInfo, Node, Score
from geminiroute.generation.generator import ScoredNode, build_stats_payload, generate


def scored(name: str, score: float, gemini: bool = True, latency: float = 200.0,
           country: str | None = "Germany", code: str | None = "DE") -> ScoredNode:
    node = Node(
        protocol=ProtocolType.VLESS, address=f"{name}.example.net", port=443,
        credential="uuid", remark=name, raw=f"vless://uuid@{name}.example.net:443#{name}",
    )
    return ScoredNode(
        node=node,
        score=Score(node.fingerprint, 1.0, 1.0, 1.0, 1.0, score),
        gemini_passed=gemini,
        latency_ms=latency,
        geo=GeoInfo(country=country, country_code=code),
    )


def decode(path: Path) -> list[str]:
    return base64.b64decode(path.read_text()).decode().splitlines()


def test_subscription_keeps_the_functional_config_and_rebrands_the_label(tmp_path: Path) -> None:
    """Everything before the fragment is the source's own config; only the
    display label is ours."""
    generate(tmp_path, [scored("a", 0.9)])
    line = decode(tmp_path / "sub" / "all.txt")[0]
    assert line.startswith("vless://uuid@a.example.net:443#")
    assert "GeminiRoute" in line


def test_published_labels_are_numbered_from_one(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9), scored("b", 0.8), scored("c", 0.7)])
    labels = [line.split("#", 1)[1] for line in decode(tmp_path / "sub" / "all.txt")]
    assert labels == ["1.🇩🇪 GeminiRoute", "2.🇩🇪 GeminiRoute", "3.🇩🇪 GeminiRoute"]


def test_each_file_is_numbered_independently(tmp_path: Path) -> None:
    generate(tmp_path, [scored("bad", 0.9, gemini=False), scored("ok", 0.8)])
    lines = decode(tmp_path / "sub" / "gemini.txt")
    gemini_labels = [line.split("#", 1)[1] for line in lines]
    assert gemini_labels == ["1.🇩🇪 GeminiRoute"]


def test_plain_variant_is_written_for_humans(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9)])
    assert "vless://uuid@a.example.net:443#" in (tmp_path / "sub" / "all.plain.txt").read_text()


def test_nodes_are_ranked_by_score(tmp_path: Path) -> None:
    generate(tmp_path, [scored("low", 0.2), scored("high", 0.95), scored("mid", 0.5)])
    hosts = [urlsplit(line).hostname for line in decode(tmp_path / "sub" / "all.txt")]
    assert hosts == ["high.example.net", "mid.example.net", "low.example.net"]


def test_gemini_file_excludes_unverified_nodes(tmp_path: Path) -> None:
    generate(tmp_path, [scored("ok", 0.9), scored("bad", 0.8, gemini=False)])
    assert len(decode(tmp_path / "sub" / "all.txt")) == 2
    assert len(decode(tmp_path / "sub" / "gemini.txt")) == 1


def test_fast_file_applies_the_latency_ceiling(tmp_path: Path) -> None:
    generate(tmp_path, [scored("quick", 0.9, latency=120), scored("slow", 0.9, latency=2000)])
    hosts = [urlsplit(line).hostname for line in decode(tmp_path / "sub" / "fast.txt")]
    assert hosts == ["quick.example.net"]


def test_per_country_files_are_written(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9, country="Germany", code="DE"),
                        scored("b", 0.9, country="Japan", code="JP")])
    assert (tmp_path / "sub" / "country" / "de.txt").exists()
    assert (tmp_path / "sub" / "country" / "jp.txt").exists()


def test_nodes_without_geo_land_in_unknown(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9, country=None, code=None)])
    assert (tmp_path / "sub" / "country" / "unknown.txt").exists()


def test_api_payload_never_exposes_credentials(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9)])
    text = (tmp_path / "api" / "nodes.json").read_text()
    assert "credential" not in text
    payload = json.loads(text)
    assert payload["count"] == 1
    assert payload["nodes"][0]["score"] == 0.9


def test_stats_record_the_whole_funnel(tmp_path: Path) -> None:
    """'0 published' is unactionable; the funnel says which stage ate them."""
    stats = build_stats_payload([scored("a", 0.9), scored("b", 0.4, gemini=False)],
                                collected=20000, after_dedup=12000,
                                after_pre=5000, after_connectivity=800)
    assert stats["funnel"] == {
        "collected": 20000, "after_dedup": 12000, "after_pre_validation": 5000,
        "after_connectivity": 800, "after_gemini": 1,
    }
    assert stats["gemini_success_rate"] == 0.5


def test_empty_run_still_writes_valid_files(tmp_path: Path) -> None:
    generate(tmp_path, [])
    assert (tmp_path / "sub" / "all.txt").read_text() == ""
    assert json.loads((tmp_path / "api" / "nodes.json").read_text())["count"] == 0


def test_country_files_are_keyed_on_the_iso_code(tmp_path: Path) -> None:
    """The exit-location check reports a code, not a name, and codes stay
    stable where display names do not."""
    generate(tmp_path, [scored("a", 0.9, country=None, code="DE"),
                        scored("b", 0.9, country=None, code="JP")])
    assert (tmp_path / "sub" / "country" / "de.txt").exists()
    assert (tmp_path / "sub" / "country" / "jp.txt").exists()


def test_country_name_is_used_when_no_code_is_available(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9, country="Germany", code=None)])
    assert (tmp_path / "sub" / "country" / "germany.txt").exists()


def test_stats_publish_per_source_yield(tmp_path: Path) -> None:
    """Whether a source earns its place is the most common question about this
    pipeline, and the answer should not require cloning the database branch."""
    stats = build_stats_payload(
        [], 100, 80, 60, 40,
        sources=[("weak", 500, 100, 1), ("strong", 400, 300, 90)],
    )
    published = stats["sources"]
    assert [s["name"] for s in published] == ["strong", "weak"]   # best first
    assert published[0]["yield"] == 0.225
    assert published[1]["yield"] == 0.002


def test_source_with_no_nodes_has_no_yield(tmp_path: Path) -> None:
    stats = build_stats_payload([], 0, 0, 0, 0, sources=[("empty", 0, 0, 0)])
    assert stats["sources"][0]["yield"] is None


def test_stats_with_no_sources_still_writes_everything(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9)])
    assert json.loads((tmp_path / "api" / "stats.json").read_text())["sources"] == []
    assert (tmp_path / "index.html").exists()
