import unittest

import pandas as pd

from Pick_assignment_26 import (
    assign_keepers_from_df,
    get_draft_for_season,
    original_draft_picks,
)


class FakeLeague:
    def __init__(self, drafts):
        self._drafts = drafts

    def get_all_drafts(self):
        return self._drafts


class KeeperAssignmentTests(unittest.TestCase):
    def test_get_draft_for_exact_season(self):
        league = FakeLeague(
            [
                {"season": "2025", "draft_id": "old", "created": 1},
                {"season": "2026", "draft_id": "newer", "created": 3},
                {"season": "2026", "draft_id": "older", "created": 2},
            ]
        )

        self.assertEqual(
            get_draft_for_season(league, 2026)["draft_id"],
            "newer",
        )

    def test_get_draft_does_not_fall_back_to_wrong_year(self):
        league = FakeLeague([{"season": "2025", "draft_id": "old"}])

        with self.assertRaisesRegex(ValueError, "No Sleeper draft found for 2026"):
            get_draft_for_season(league, 2026)

    def test_original_picks_use_actual_league_size(self):
        draft_positions = {"a": 1, "b": 2, "c": 3, "d": 4}

        picks = original_draft_picks(
            draft_positions,
            list(draft_positions),
            num_rounds=8,
        )

        self.assertEqual(picks["a"], [1, 5, 9, 13, 17, 21, 28, 29])
        self.assertEqual(picks["d"], [4, 8, 12, 16, 20, 24, 25, 32])

    def test_assignments_are_returned_in_keeper_selection_order(self):
        managers = pd.DataFrame(
            [
                {
                    "display_name": "Manager A",
                    "Draft_order": 1,
                    "Current_picks": [1, 5, 9],
                    "Original_picks": [1, 5, 9],
                    "Keepers": ["late", "early"],
                    "Keeper_rounds_2026": [2, 1],
                },
                {
                    "display_name": "Manager B",
                    "Draft_order": 2,
                    "Current_picks": [2, 6, 10],
                    "Original_picks": [2, 6, 10],
                    "Keepers": [],
                    "Keeper_rounds_2026": [],
                },
                {
                    "display_name": "Manager C",
                    "Draft_order": 3,
                    "Current_picks": [3, 7, 11],
                    "Original_picks": [3, 7, 11],
                    "Keepers": [],
                    "Keeper_rounds_2026": [],
                },
                {
                    "display_name": "Manager D",
                    "Draft_order": 4,
                    "Current_picks": [4, 8, 12],
                    "Original_picks": [4, 8, 12],
                    "Keepers": [],
                    "Keeper_rounds_2026": [],
                },
            ]
        )

        assignments = assign_keepers_from_df(
            managers,
            rounds_col="Keeper_rounds_2026",
        )

        self.assertEqual(assignments["Manager A"], [("late", 5), ("early", 1)])


if __name__ == "__main__":
    unittest.main()
