"""Unit tests for config validation and export merge edge cases."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

from trakt_to_letterboxd.config import Config
from trakt_to_letterboxd.export import merge_ratings_and_watched


class ConfigTests(unittest.TestCase):
    def test_placeholder_credentials_rejected(self) -> None:
        cfg = Config(
            letterboxd_username="your_letterboxd_username",
            letterboxd_password="your_letterboxd_password",
            trakt_client_id="your_trakt_client_id",
            trakt_client_secret="your_trakt_client_secret",
        )
        self.assertFalse(cfg.has_trakt_credentials())
        self.assertFalse(cfg.has_letterboxd_credentials())

    def test_real_credentials_accepted(self) -> None:
        cfg = Config(
            letterboxd_username="alice",
            letterboxd_password="secret",
            trakt_client_id="abc",
            trakt_client_secret="def",
        )
        self.assertTrue(cfg.has_trakt_credentials())
        self.assertTrue(cfg.has_letterboxd_credentials())

    def test_save_roundtrip_uses_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yml"
            cfg = Config(
                letterboxd_username="alice",
                letterboxd_password="secret",
                trakt_client_id="abc",
                trakt_client_secret="def",
            )
            cfg.save(path)
            loaded = Config.load(path)
            assert loaded is not None
            self.assertEqual(loaded.letterboxd_username, "alice")
            self.assertEqual(loaded._path, path)

            loaded.letterboxd_username = "bob"
            loaded.save()
            again = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(again["letterboxd_username"], "bob")

    def test_missing_config_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.yml"
            self.assertIsNone(Config.load(path))


class ExportMergeTests(unittest.TestCase):
    def test_empty_watches_returns_typed_frame(self) -> None:
        ratings = pd.DataFrame(
            columns=["Title", "Year", "imdbID", "Rating10", "RatingDate"]
        )
        watches = pd.DataFrame(columns=["Title", "Year", "imdbID", "WatchedDate"])
        merged = merge_ratings_and_watched(ratings, watches)
        self.assertTrue(merged.empty)
        self.assertEqual(
            list(merged.columns),
            ["Title", "Year", "Rating10", "Rewatch", "imdbID", "WatchedDate"],
        )

    def test_merge_pairs_closest_rating(self) -> None:
        ratings = pd.DataFrame(
            [
                {
                    "Title": "Film",
                    "Year": 2020,
                    "imdbID": "tt1",
                    "Rating10": 8,
                    "RatingDate": pd.Timestamp("2020-01-10").date(),
                }
            ]
        )
        watches = pd.DataFrame(
            [
                {
                    "Title": "Film",
                    "Year": 2020,
                    "imdbID": "tt1",
                    "WatchedDate": pd.Timestamp("2020-01-11").date(),
                }
            ]
        )
        merged = merge_ratings_and_watched(ratings, watches)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged.iloc[0]["Rating10"], 8)
        self.assertFalse(bool(merged.iloc[0]["Rewatch"]))


if __name__ == "__main__":
    unittest.main()
