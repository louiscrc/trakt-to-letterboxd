import datetime
from pathlib import Path
import pandas as pd

from trakt import core
from trakt.users import User

from . import console
from .log import log_nav
from .paths import csv_path


def convert_trakt_datetime_str(rated_at: str) -> datetime.datetime:
    """Convert Trakt datetime string to datetime object"""
    return datetime.datetime.strptime(rated_at, "%Y-%m-%dT%H:%M:%S.%fZ")


def get_output_path(filename: str) -> Path:
    """Get output path for CSV files in the app data directory."""
    return csv_path(filename)


def get_all_ratings() -> pd.DataFrame:
    """Fetch all ratings from Trakt."""
    trakt_user = User("me")
    ratings = trakt_user.get_ratings("movies")
    ratings_data = []

    for rating_data in ratings:
        movie_info = rating_data.get("movie", rating_data)
        rated_at = rating_data.get("rated_at", "")
        rating_date = None
        if rated_at:
            try:
                rating_date = convert_trakt_datetime_str(rated_at).date()
            except Exception:
                pass

        ratings_data.append(
            {
                "Title": movie_info.get("title", "Unknown Title"),
                "Year": movie_info.get("year", 0),
                "imdbID": movie_info.get("ids", {}).get("imdb", ""),
                "Rating10": rating_data.get("rating", ""),
                "RatingDate": rating_date,
            }
        )

    return pd.DataFrame(ratings_data)


def get_all_watched() -> pd.DataFrame:
    """Fetch all watched movies from Trakt with watch history dates."""
    try:
        api = core.api()
        history_data = []
        page = 1
        while True:
            page_data = api.get(f"users/me/history/movies?page={page}&limit=100")
            if len(page_data) == 0:
                break
            history_data.extend(page_data)
            page += 1

        if not history_data:
            return pd.DataFrame(columns=["Title", "Year", "imdbID", "WatchedDate"])

    except Exception as e:
        console.print(f"Failed to fetch watch history: {e}", style="red")
        raise

    watched_data = [
        {
            "Title": entry.get("movie", {}).get("title", "Unknown Title"),
            "Year": entry.get("movie", {}).get("year", 0),
            "imdbID": entry.get("movie", {}).get("ids", {}).get("imdb", ""),
            "WatchedDate": (
                convert_trakt_datetime_str(entry.get("watched_at", "")).date()
                if entry.get("watched_at", "")
                else None
            ),
        }
        for entry in history_data
    ]
    return pd.DataFrame(watched_data)


def merge_ratings_and_watched(ratings_df: pd.DataFrame, watches_df: pd.DataFrame) -> pd.DataFrame:
    """Merge ratings and watched data by matching each watch with the closest rating."""
    columns = ["Title", "Year", "Rating10", "Rewatch", "imdbID", "WatchedDate"]
    if watches_df.empty:
        return pd.DataFrame(columns=columns)

    merged_rows = []
    watches_by_movie = watches_df.groupby("imdbID")
    ratings_by_movie = ratings_df.groupby("imdbID") if not ratings_df.empty else None

    for imdb_id, watch_group in watches_by_movie:
        watches = watch_group.sort_values("WatchedDate").reset_index(drop=True)

        if ratings_by_movie is not None and imdb_id in ratings_by_movie.groups:
            ratings = ratings_by_movie.get_group(imdb_id).sort_values("RatingDate").reset_index(drop=True)
            available_ratings = list(ratings.index)
        else:
            ratings = pd.DataFrame()
            available_ratings = []

        for _, watch in watches.iterrows():
            watch_date = watch["WatchedDate"]
            rating_value = ""

            if available_ratings and pd.notna(watch_date):
                best_rating_idx = None
                min_diff = None

                for rating_idx in available_ratings:
                    rating_date = ratings.loc[rating_idx, "RatingDate"]
                    if pd.notna(rating_date):
                        diff = abs((watch_date - rating_date).days)
                        if min_diff is None or diff < min_diff:
                            min_diff = diff
                            best_rating_idx = rating_idx

                if best_rating_idx is not None:
                    rating_value = ratings.loc[best_rating_idx, "Rating10"]
                    available_ratings.remove(best_rating_idx)

            merged_rows.append(
                {
                    "Title": watch["Title"],
                    "Year": watch["Year"],
                    "imdbID": imdb_id,
                    "WatchedDate": watch_date,
                    "Rating10": rating_value,
                }
            )

    if not merged_rows:
        return pd.DataFrame(columns=columns)

    merged_df = pd.DataFrame(merged_rows)
    merged_df = merged_df.sort_values(["imdbID", "WatchedDate"])
    merged_df["Rewatch"] = merged_df.groupby("imdbID").cumcount() > 0
    final_df = merged_df[columns].copy()
    return final_df.sort_values("WatchedDate", ascending=False, na_position="last")


def _entry_key(df: pd.DataFrame) -> pd.Series:
    return (
        df["imdbID"].astype(str)
        + "_"
        + df["WatchedDate"].astype(str)
        + "_"
        + df["Rating10"].fillna("").astype(str)
    )


def compare_and_get_new_entries(new_merged_df: pd.DataFrame) -> pd.DataFrame:
    """Return entries in new_merged_df that are not in the previous merged.csv."""
    old_merged_path = get_output_path("merged.csv")

    if new_merged_df.empty:
        return new_merged_df

    if not old_merged_path.exists():
        return new_merged_df

    try:
        old_merged_df = pd.read_csv(old_merged_path, dtype={"Rating10": str})
        if "_key" in old_merged_df.columns:
            old_merged_df = old_merged_df.drop("_key", axis=1)

        new_merged_df = new_merged_df.copy()
        new_merged_df["_key"] = _entry_key(new_merged_df)
        old_merged_df["_key"] = _entry_key(old_merged_df)

        new_keys = set(new_merged_df["_key"]) - set(old_merged_df["_key"])
        new_entries_df = new_merged_df[new_merged_df["_key"].isin(new_keys)].copy()
        return new_entries_df.drop("_key", axis=1)

    except Exception as e:
        console.print(f"Could not read merged.csv: {e}", style="yellow")
        return new_merged_df.drop("_key", axis=1) if "_key" in new_merged_df.columns else new_merged_df


def append_to_export_csv(new_entries_df: pd.DataFrame, *, dry_run: bool = False) -> tuple[pd.DataFrame, int]:
    """Add new entries to export.csv without removing existing pending rows."""
    export_file = get_output_path("export.csv")

    if new_entries_df.empty:
        if export_file.exists():
            return pd.read_csv(export_file, dtype={"Rating10": str}), 0
        return new_entries_df, 0

    if export_file.exists():
        try:
            existing_df = pd.read_csv(export_file, dtype={"Rating10": str})
        except Exception as e:
            console.print(f"Could not read existing export.csv: {e}", style="yellow")
            existing_df = pd.DataFrame()
    else:
        existing_df = pd.DataFrame()

    if existing_df.empty:
        combined_df = new_entries_df.copy()
        added = len(new_entries_df)
    else:
        combined_df = pd.concat([existing_df, new_entries_df], ignore_index=True)
        combined_df["_key"] = _entry_key(combined_df)
        combined_df = combined_df.drop_duplicates(subset=["_key"], keep="first")
        combined_df = combined_df.drop("_key", axis=1)
        added = len(combined_df) - len(existing_df)

    if not dry_run:
        combined_df.to_csv(export_file, index=False, encoding="utf-8")
    return combined_df, added


def export_all_trakt_data(*, dry_run: bool = False) -> None:
    if dry_run:
        console.print("  Dry run — no CSV files will be written.", style="yellow")

    log_nav("Fetching ratings and watch history…")

    ratings_df = get_all_ratings()
    watches_df = get_all_watched()
    merged_df = merge_ratings_and_watched(ratings_df, watches_df)
    new_entries_df = compare_and_get_new_entries(merged_df)

    if not dry_run:
        ratings_df.to_csv(get_output_path("ratings.csv"), index=False, encoding="utf-8")
        watches_df.to_csv(get_output_path("watched.csv"), index=False, encoding="utf-8")
        merged_df.to_csv(get_output_path("merged.csv"), index=False, encoding="utf-8")

    export_df, added = append_to_export_csv(new_entries_df, dry_run=dry_run)
    suffix = " (dry run)" if dry_run else ""
    console.print(
        f"  Done{suffix} — {len(merged_df)} watches, {added} new in export.csv ({len(export_df)} pending)",
        style="green",
    )