import base64
import json
from pathlib import Path

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import GeoInfo, Node, Score
from geminiroute.generation.generator import ScoredNode, build_stats_payload, generate


def scored(name: str, score: float, gemini: bool = True, latency: float = 200.0,
           country: str | None = "Germany") -> ScoredNode:
    node = Node(
        protocol=ProtocolType.VLESS, address=f"{name}.example.net", port=443,
        credential="uuid", remark=name, raw=f"vless://uuid@{name}.example.net:443#{name}",
    )
    return ScoredNode(
        node=node,
        score=Score(node.fingerprint, 1.0, 1.0, 1.0, 1.0, score),
        gemini_passed=gemini,
        latency_ms=latency,
        geo=GeoInfo(country=country),
    )


def decode(path: Path) -> list[str]:
    return base64.b64decode(path.read_text()).decode().splitlines()


def test_subscription_is_base64_and_contains_the_original_lines(tmp_path: Path) -> None:
    """The published line must be the source's own config, not a
    re-serialisation that could silently drop an unmodelled parameter."""
    generate(tmp_path, [scored("a", 0.9)])
    assert decode(tmp_path / "sub" / "all.txt") == ["vless://uuid@a.example.net:443#a"]


def test_plain_variant_is_written_for_humans(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9)])
    assert "vless://uuid@a.example.net:443#a" in (tmp_path / "sub" / "all.plain.txt").read_text()


def test_nodes_are_ranked_by_score(tmp_path: Path) -> None:
    generate(tmp_path, [scored("low", 0.2), scored("high", 0.95), scored("mid", 0.5)])
    lines = decode(tmp_path / "sub" / "all.txt")
    assert [line.split("#")[1] for line in lines] == ["high", "mid", "low"]


def test_gemini_file_excludes_unverified_nodes(tmp_path: Path) -> None:
    generate(tmp_path, [scored("ok", 0.9), scored("bad", 0.8, gemini=False)])
    assert len(decode(tmp_path / "sub" / "all.txt")) == 2
    assert len(decode(tmp_path / "sub" / "gemini.txt")) == 1


def test_fast_file_applies_the_latency_ceiling(tmp_path: Path) -> None:
    generate(tmp_path, [scored("quick", 0.9, latency=120), scored("slow", 0.9, latency=2000)])
    assert [line.split("#")[1] for line in decode(tmp_path / "sub" / "fast.txt")] == ["quick"]


def test_per_country_files_are_written(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9, country="Germany"), scored("b", 0.9, country="Japan")])
    assert (tmp_path / "sub" / "country" / "germany.txt").exists()
    assert (tmp_path / "sub" / "country" / "japan.txt").exists()


def test_nodes_without_geo_land_in_unknown(tmp_path: Path) -> None:
    generate(tmp_path, [scored("a", 0.9, country=None)])
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
