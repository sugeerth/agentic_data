"""Unit tests for the shared city-name matcher and behavior that depends on it.

These exercise pure logic only (no LLM, no network) and lock in the matching
semantics that flight/hotel/activity/weather/budget tools all rely on.
"""

from tools.city_match import match_city
from tools.flight_tools import _get_region, _get_airport
from tools.budget_tools import _get_city_costs
from tools.weather_tools import _get_coords
from tools.activity_tools import _get_city_activities


TABLE = {"tokyo": "JP", "new york": "US", "los angeles": "US"}


class TestMatchCity:
    def test_exact_key_matches(self):
        assert match_city("tokyo", TABLE) == "JP"

    def test_case_insensitive(self):
        assert match_city("TOKYO", TABLE) == "JP"

    def test_surrounding_text_matches_key_as_substring(self):
        # Key is a substring of the query -> match (e.g. "tokyo, japan").
        assert match_city("Tokyo, Japan", TABLE) == "JP"

    def test_query_substring_of_key_matches(self):
        # Query is a substring of the key -> match (multi-word key).
        assert match_city("new", TABLE) == "US"

    def test_whitespace_is_stripped(self):
        assert match_city("  tokyo  ", TABLE) == "JP"

    def test_no_match_returns_none(self):
        assert match_city("reykjavik", TABLE) is None

    def test_first_insertion_order_match_wins(self):
        # When several keys match the query, the first in insertion order wins.
        # Both "san" and "san francisco" are substrings of "san francisco".
        ordered = {"san": 1, "san francisco": 2}
        assert match_city("san francisco", ordered) == 1


class TestToolHelpersUseMatcher:
    def test_get_region_known_city(self):
        assert _get_region("Tokyo") == "asia"

    def test_get_region_unknown_defaults_north_america(self):
        assert _get_region("Atlantis") == "north_america"

    def test_get_airport_known_city(self):
        assert _get_airport("Paris") == "CDG"

    def test_get_airport_unknown_falls_back_to_prefix(self):
        # Unknown city -> first three letters upper-cased.
        assert _get_airport("Zzyzx") == "ZZY"

    def test_city_costs_known(self):
        costs = _get_city_costs("Tokyo")
        assert costs is not None and costs["currency"] == "JPY"

    def test_city_costs_unknown_returns_none(self):
        assert _get_city_costs("Reykjavik") is None

    def test_coords_known(self):
        coords = _get_coords("paris")
        assert coords == (48.8566, 2.3522)

    def test_activities_unknown_returns_empty_list(self):
        assert _get_city_activities("Reykjavik") == []
