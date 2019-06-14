# -*- coding: utf-8 -*-
"""
Created on Tue Apr 17 12:06:13 2018

Author: Paul Keuren


Notes
-----
* Levenstein distances can also by calculated using the *python-levenshtein* module
"""
import numpy as np


def levenshtein_distance(s: str, t: str) -> int:
    """
    Calculate Levenshtein distance

    Parameters
    ----------
    s: str
        First string
    t: str
        Second string

    Returns
    -------
    int:
        Distance between strings

    Notes
    -----

    * [NL] Bereken de Levenshtein afstand tussen strings. Deze afstandsbepaling geeft aan hoeveel
      wijzgingen minimaal nodig zijn om van een string de andere string te gaan. Deze implementatie
      gebruikt een matrix met grootte len(s)*len(t).
    * [EN] Calculates the Levenshtein distance between strings. The Levenshtein distance computes
      the minimal number of changes (addition/removal/substitution) required to transform one string
      to the other string. This specific implementation uses a matrix with size len(s)*len(t).
    * For more information on the topic see `wikipedialevenshtein`_

    .. _wikipedialevenshtein:
        https://en.wikipedia.org/wiki/Levenshtein_distance

    """

    # m en n zijn de lengtes van s en t.
    m = len(s) + 1
    n = len(t) + 1
    # we beginnen met een lege matrix van int waarden
    d = np.zeros(shape=(m, n), dtype=int)
    # de bovenste rij in de matrix is gelijk aan het zoveelste character
    #  dit is nodig om er straks overheen te itereren.
    for i in range(1, m):
        d[i, 0] = i
    for j in range(1, n):
        d[0, j] = j
    # voor iedere waarde van 1 tot m en 1 tot n
    for i in range(1, m):
        for j in range(1, n):
            # controleer of de characters hetzelfde zijn
            if s[i - 1] == t[j - 1]:
                # dan is er geen wijziging
                substitution_cost = 0
            else:
                # anders is er wel een wijziging
                substitution_cost = 1
                # zoek de kleinste wijziging uit de volgende lijst:
            d[i, j] = min([
                d[i - 1, j] + 1,  # verwijdering
                d[i, j - 1] + 1,  # toevoeging
                d[i - 1, j - 1] + substitution_cost  # vervanging
            ])
        # de matrix is nu gevuld met alle delta's en het component rechtsonderin
        # bevat de uiteindelijke afstand van de totale strings.
    return d[len(s), len(t)]


def optimal_string_alignment_distance(s: str, t: str) -> int:
    """

    Parameters
    ----------
    s: str
        First string
    t: str
        Second string

    Returns
    -------
        OSA distance

    Notes
    -----
    * [NL] Het Optimal String Alignment (OSA) algoritme is een beperkte schatting van de Damerau-
      Levenshtein (DL) afstand. Het gebruikt geen alphabet (zoals bij DL), maar is beperkt in het
      aantal transposities wat deze kan meenemen. DL daarentegen neemt alle transposities mee,
      echter is dit vaak zeer duur en is de OSA goed genoeg.

    * [EN] The optimal string alignment (OSA) algorithm allows for a quick estimation of the
      Damerau-Levenshtein (DL) distance. It does not require an additional alphabet, but is
      therefore limited in its transposition detection/completion. This makes the algorithm cheaper
      than the DL distance, but also less accurate.
    * For more information on the topic see `wikipediadamerau`_

    .. wikipediadamerau_:
        https://en.wikipedia.org/wiki/Damerau%E2%80%93Levenshtein_distance
    """

    # m en n zijn de lengtes van s en t.
    m = len(s) + 1
    n = len(t) + 1
    # we beginnen met een lege matrix van int waarden
    d = np.zeros(shape=(m, n), dtype=int)
    # de bovenste rij in de matrix is gelijk aan het zoveelste character
    #  dit is nodig om er straks overheen te itereren.
    for i in range(1, m):
        d[i, 0] = i
    for j in range(1, n):
        d[0, j] = j
    # voor iedere waarde van 1 tot m en 1 tot n
    for i in range(1, m):
        for j in range(1, n):
            cost = 0 if s[i - 1] == t[j - 1] else 1
            # controleer of de characters hetzelfde zijn
            if s[i - 1] == t[j - 1]:
                # dan is er geen wijziging
                substitution_cost = 0
            else:
                # anders is er wel een wijziging
                substitution_cost = 1
                # zoek de kleinste wijziging uit de volgende lijst:
            d[i, j] = min([
                d[i - 1, j] + 1,  # verwijdering
                d[i, j - 1] + 1,  # toevoeging
                d[i - 1, j - 1] + substitution_cost  # vervanging
            ])
            if i > 1 and j > 1 and s[i - 1] == t[j - 2] and s[i - 2] == t[j - 1]:
                d[i, j] = min(
                    d[i, j],
                    d[i - 2, j - 2] + cost  # transposition
                )
        # de matrix is nu gevuld met alle delta's en het component rechtsonderin
        # bevat de uiteindelijke afstand van de totale strings.
    return d[len(s), len(t)]


if __name__ == '__main__':
    a = 'aap'
    a1 = 'aap1'

    s = 'books'
    t = 'back'
    u = 'rooks'
    s2 = 'bokos'

    assert levenshtein_distance(t, s) == levenshtein_distance(s, t), 'Symmetrie Fout'
    assert levenshtein_distance(t, s) == 3, 'Waarde Fout'
    assert levenshtein_distance(s, u) == 1, 'Waarde Fout'
    assert levenshtein_distance('a', 'b') == 1, 'Waarde Fout'
    assert levenshtein_distance('a', 'bc') == 2, 'Waarde Fout'

    assert optimal_string_alignment_distance(s, s2) == 1
