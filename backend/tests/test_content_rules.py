from montage.content_rules import apply_to_query
from montage.keywords import make_queries


def test_women_get_hijab():
    assert apply_to_query("woman shopping market") == "woman shopping market hijab"
    assert apply_to_query("mother with child") == "mother with child hijab"


def test_groups_get_muslim_hijab():
    assert apply_to_query("family dinner") == "family dinner muslim hijab"


def test_objects_unchanged_and_no_duplicates():
    assert apply_to_query("gold coins in hand") == "gold coins in hand"
    assert apply_to_query("hijab woman walking") == "hijab woman walking"


def test_dictionary_fallback_without_key():
    queries, source = make_queries(["دنانير دهب ودراهم فضة قديمة في كف إيد", "ست بتشتري من السوق"])
    assert source == "dictionary"
    assert "gold" in queries[0]
    assert queries[1].endswith("hijab")
