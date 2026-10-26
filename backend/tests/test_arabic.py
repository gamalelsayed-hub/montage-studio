from montage.arabic import normalize


def test_removes_diacritics_and_tatweel():
    assert normalize("بِسْمِ اللَّهِ الرَّحْمَٰنِ") == "بسم الله الرحمن"
    assert normalize("الـــربا") == "الربا"


def test_unifies_letters():
    assert normalize("أإآ") == "ااا"
    assert normalize("على مدرسة") == "علي مدرسه"


def test_strips_punctuation_and_digits():
    assert normalize("«ورقة بورقة»، زي دهب!") == "ورقه بورقه زي دهب"
    assert normalize("١٠٠ جنيه") == "100 جنيه"
