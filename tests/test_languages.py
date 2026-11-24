"""Tests of the BFS language data behind the language map (fig12): the table covers all cantons, the shares are
consistent, and the coefficient group of every region (regions.language) is the language spoken by the majority of
its population (BFS structural survey). Regions without a group (Ticino) have a majority language without a group.

Pytest fixtures are provided from within the test runner.
"""
SHARE_ATOL = 1e-9


def test_all_cantons_once(language_shares):
    assert len(language_shares) == 26
    assert language_shares["canton"].is_unique


def test_shares_are_counts_over_total(language_shares, languages):
    for key in languages["majority_of"]:
        share = language_shares[key] / language_shares["total"]
        assert (abs(language_shares[f"share_{key}"] - share) < SHARE_ATOL).all()
        assert language_shares[f"share_{key}"].between(0, 1).all()


def test_majority_is_largest_share(language_shares, languages):
    shares = language_shares[[f"share_{k}" for k in languages["majority_of"]]]
    assert (language_shares["majority"] == shares.idxmax(axis=1).str.removeprefix("share_")).all()
    assert (language_shares["majority_share"] > 0.5).all()


def test_region_group_matches_majority_language(language_shares, languages, region_languages):
    """Merged regions: majority of the summed counts of their cantons."""
    keys = languages["majority_of"]
    counts = language_shares.groupby("region")[keys].sum()
    majority = counts.idxmax(axis=1)
    group_language = languages["group_language"]
    assert set(majority.index) == set(region_languages)
    for region, group in region_languages.items():
        if group is None:
            assert majority[region] not in group_language.values(), region
        else:
            assert majority[region] == group_language[group], region
