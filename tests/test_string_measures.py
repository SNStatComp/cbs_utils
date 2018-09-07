import hypothesis.strategies as st
from hypothesis import given

from cbs_utils.string_measures import levenshtein_distance as lv, \
    optimal_string_alignment_distance as osa


@given(st.text(), st.text())
def test_levenshtein_generic(text1, text2):
    distance = lv(text1, text2)
    len_dif = abs(len(text1) - len(text2))
    assert len_dif <= distance, "Levenshtein Distance mismatch."


@given(st.text(), st.text())
def test_OSA_generic(text1, text2):
    distance = osa(text1, text2)
    len_dif = abs(len(text1) - len(text2))
    assert len_dif <= distance, "OSA Distance mismatch."


def test_levenshtein_specific():
    a = 'aan'
    b = 'ana'
    assert lv(a, b) == 2, 'Incorrect Levenshtein distance'
    assert lv(a, a) == 0, 'Levenshtein Distance found but there should be none'


def test_OSA_specific():
    a = 'aan'
    b = 'ana'
    assert osa(a, b) == 1, 'Incorrect OSA distance'
    assert osa(a, a) == 0, 'OSA Distance found but there should be none'
