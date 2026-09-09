from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.dedup.deduplicator import deduplicate, duplicate_count


def node(address: str = "a.com", remark: str = "", sources: list[str] | None = None) -> Node:
    return Node(
        protocol=ProtocolType.VLESS,
        address=address,
        port=443,
        credential="uuid",
        remark=remark,
        source_names=list(sources or []),
    )


def test_three_sources_listing_one_node_collapse_to_one() -> None:
    nodes = [node(sources=["s1"]), node(sources=["s2"]), node(sources=["s3"])]
    result = deduplicate(nodes)
    assert len(result) == 1
    assert result[0].source_names == ["s1", "s2", "s3"]


def test_distinct_nodes_are_kept() -> None:
    assert len(deduplicate([node("a.com"), node("b.com")])) == 2


def test_source_names_are_not_duplicated() -> None:
    result = deduplicate([node(sources=["s1"]), node(sources=["s1"])])
    assert result[0].source_names == ["s1"]


def test_missing_remark_is_filled_from_a_later_duplicate() -> None:
    result = deduplicate([node(remark=""), node(remark="DE-01")])
    assert result[0].remark == "DE-01"


def test_first_remark_wins_when_present() -> None:
    result = deduplicate([node(remark="first"), node(remark="second")])
    assert result[0].remark == "first"


def test_input_order_is_preserved() -> None:
    result = deduplicate([node("b.com"), node("a.com"), node("b.com")])
    assert [n.address for n in result] == ["b.com", "a.com"]


def test_input_list_is_not_mutated() -> None:
    original = node(sources=["s1"])
    deduplicate([original, node(sources=["s2"])])
    assert original.source_names == ["s1"]


def test_duplicate_count_measures_source_overlap() -> None:
    assert duplicate_count([node(), node(), node("b.com")]) == 1
