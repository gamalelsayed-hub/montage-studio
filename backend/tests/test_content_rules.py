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


def test_dictionary_fallback_keeps_the_scene_first_and_short():
    queries, _ = make_queries(["سوق قديم: واحد شايل شوال قمح، والتاني ماسك توب قماش"])
    assert queries[0] == "souk sack old"


def test_banned_results():
    from montage.content_rules import is_allowed

    assert not is_allowed("christmas, tree, house")
    assert not is_allowed("Wine glasses on a table")
    assert is_allowed("market, souk, spices")
    assert is_allowed(None)
