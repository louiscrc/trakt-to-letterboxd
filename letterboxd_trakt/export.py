import datetime
from pathlib import Path
import pandas as pd

from trakt import core
from trakt.users import User

from . import console
from .config import Account


def convert_trakt_datetime_str(rated_at: str) -> datetime.datetime:
    """Convert Trakt datetime string to datetime object"""
    return datetime.datetime.strptime(rated_at, "%Y-%m-%dT%H:%M:%S.%fZ")


def get_output_path(filename: str) -> Path:
    """Get output path for CSV files"""
    output_dir = Path("/csv") if Path("/csv").exists() else Path("./csv")
    output_dir.mkdir(exist_ok=True)
    return output_dir / filename


def get_all_ratings() -> pd.DataFrame:
    """Fetch all ratings from Trakt"""
    console.print("Fetching all Trakt ratings...", style="blue")
    
    trakt_user = User("me")
    ratings = trakt_user.get_ratings('movies')
    ratings_data = []
    
    for rating_data in ratings:
        movie_info = rating_data.get("movie", rating_data)
        
        # Parse rating date
        rated_at = rating_data.get("rated_at", "")
        rating_date = None
        if rated_at:
            try:
                rating_date = convert_trakt_datetime_str(rated_at).date()
            except Exception:
                pass
        
        ratings_data.append({
            'Title': movie_info.get("title", "Unknown Title"),
            'Year': movie_info.get("year", 0),
            'imdbID': movie_info.get("ids", {}).get("imdb", ""),
            'Rating10': rating_data.get("rating", ""),
            'RatingDate': rating_date
        })

    df = pd.DataFrame(ratings_data)
    console.print(f"Retrieved {len(df)} ratings", style="green")
    return df


def get_all_watched() -> pd.DataFrame:
    """Fetch all watched movies from Trakt with watch history dates"""
    console.print("Fetching all Trakt watched movies history...", style="blue")
    
    try: 
        # Direct call to Trakt API to fetch history with dates
        # The /users/me/history/movies endpoint returns full history with watched_at
        api = core.api()
        history_data = []
        page = 1
        while True:
            page_data = api.get(f'users/me/history/movies?page={page}&limit=100')
            if len(page_data) == 0:
                break
            history_data.extend(page_data)
            page += 1
        
        if not history_data:
            console.print("No watch history found", style="yellow")
            return pd.DataFrame(columns=['Title', 'Year', 'imdbID', 'WatchedDate'])
        
    except Exception as e:
        console.print(f"Failed to fetch watch history: {e}", style="red")
        raise
    
    # Convert to DataFrame with full history data
    watched_data = [{
        'Title': entry.get("movie", {}).get("title", "Unknown Title"),
        'Year': entry.get("movie", {}).get("year", 0),
        'imdbID': entry.get("movie", {}).get("ids", {}).get("imdb", ""),
        'WatchedDate': convert_trakt_datetime_str(entry.get("watched_at", "")).date() if entry.get("watched_at", "") else None
    } for entry in history_data]
    
    df = pd.DataFrame(watched_data)
    console.print(f"Retrieved {len(df)} watched movies", style="green")
    return df


def merge_ratings_and_watched(ratings_df: pd.DataFrame, watches_df: pd.DataFrame) -> pd.DataFrame:
    """Merge ratings and watched data by matching each watch with the closest rating"""
    console.print("Merging ratings and watched data...", style="blue")
    
    # List to store results
    merged_rows = []
    
    # Group watches and ratings by imdbID
    watches_by_movie = watches_df.groupby('imdbID')
    ratings_by_movie = ratings_df.groupby('imdbID')
    
    # Process each movie
    for imdb_id, watch_group in watches_by_movie:
        # Sort watches by date
        watches = watch_group.sort_values('WatchedDate').reset_index(drop=True)
        
        # Get ratings for this movie if they exist
        if imdb_id in ratings_by_movie.groups:
            ratings = ratings_by_movie.get_group(imdb_id).sort_values('RatingDate').reset_index(drop=True)
            # List of available ratings (index)
            available_ratings = list(ratings.index)
        else:
            ratings = pd.DataFrame()
            available_ratings = []
        
        # For each watch, find the closest rating
        for _, watch in watches.iterrows():
            watch_date = watch['WatchedDate']
            rating_value = ''
            
            # If we have available ratings and a valid watch date
            if available_ratings and pd.notna(watch_date):
                # Find the closest rating by date
                best_rating_idx = None
                min_diff = None
                
                for rating_idx in available_ratings:
                    rating_date = ratings.loc[rating_idx, 'RatingDate']
                    
                    # If the rating has a valid date
                    if pd.notna(rating_date):
                        diff = abs((watch_date - rating_date).days)
                        if min_diff is None or diff < min_diff:
                            min_diff = diff
                            best_rating_idx = rating_idx
                
                # If we found a rating, use it and remove it from the list
                if best_rating_idx is not None:
                    rating_value = ratings.loc[best_rating_idx, 'Rating10']
                    available_ratings.remove(best_rating_idx)
            
            # Add the row to results
            merged_rows.append({
                'Title': watch['Title'],
                'Year': watch['Year'],
                'imdbID': imdb_id,
                'WatchedDate': watch_date,
                'Rating10': rating_value
            })
    
    # Create final DataFrame
    merged_df = pd.DataFrame(merged_rows)
    
    # Add Rewatch column based on imdbID duplicates
    merged_df = merged_df.sort_values(['imdbID', 'WatchedDate'])
    merged_df['Rewatch'] = merged_df.groupby('imdbID').cumcount() > 0
    
    # Reorder columns in desired order
    final_df = merged_df[['Title', 'Year', 'Rating10', 'Rewatch', 'imdbID', 'WatchedDate']].copy()
    
    # Sort by watch date (most recent first)
    final_df = final_df.sort_values('WatchedDate', ascending=False, na_position='last')
    
    console.print(f"Merged {len(final_df)} entries", style="green")
    return final_df


def compare_and_get_new_entries(new_merged_df: pd.DataFrame) -> pd.DataFrame:
    """Compare le nouveau merged avec l'ancien et retourne uniquement les nouvelles entrées"""
    console.print("Comparing with previous merged data...", style="blue")
    
    old_merged_path = get_output_path("merged.csv")
    
    if not old_merged_path.exists():
        console.print("No previous merged.csv found, all entries are new", style="yellow")
        return new_merged_df
    
    try:
        old_merged_df = pd.read_csv(old_merged_path, dtype={'Rating10': str})
        
        # Remove _key column if it exists from previous run
        if '_key' in old_merged_df.columns:
            old_merged_df = old_merged_df.drop('_key', axis=1)
        
        # Create unique key for each entry (imdbID + WatchedDate + Rating10)
        # Use fillna('') to handle empty ratings consistently
        new_merged_df['_key'] = (
            new_merged_df['imdbID'].astype(str) + '_' + 
            new_merged_df['WatchedDate'].astype(str) + '_' + 
            new_merged_df['Rating10'].fillna('').astype(str)
        )

        old_merged_df['_key'] = (
            old_merged_df['imdbID'].astype(str) + '_' + 
            old_merged_df['WatchedDate'].astype(str) + '_' + 
            old_merged_df['Rating10'].fillna('').astype(str)
        )
        
        # Find new entries
        new_keys = set(new_merged_df['_key']) - set(old_merged_df['_key'])
        new_entries_df = new_merged_df[new_merged_df['_key'].isin(new_keys)].copy()
        
        console.print(f"Found {len(new_entries_df)} new entries", style="green")
        return new_entries_df.drop('_key', axis=1)
        
    except Exception as e:
        console.print(f"Error reading previous merged.csv: {e}", style="yellow")
        return new_merged_df.drop('_key', axis=1)


def export_all_trakt_data(account: Account) -> bool:
    """Export all CSV files: ratings, watched, merged, export
    Return True if export.csv is not empty, False otherwise"""
    console.print(f"Starting export for Trakt account: {account.letterboxd_username}", style="purple4")
    
    exported_files = {}
    
    try:
        # 1. Fetch all ratings
        ratings_df = get_all_ratings()
        
        # 2. Fetch all watched movies
        watches_df = get_all_watched()
        
        # 3. Merge the data
        merged_df = merge_ratings_and_watched(ratings_df, watches_df)
        
        # 4. Compare and get new entries
        export_df = compare_and_get_new_entries(merged_df)
        
        # 5. Export all CSV files
        
        # Export ratings.csv
        ratings_file = get_output_path("ratings.csv")
        ratings_df.to_csv(ratings_file, index=False, encoding='utf-8')
        
        # Export watched.csv
        watched_file = get_output_path("watched.csv")
        watches_df.to_csv(watched_file, index=False, encoding='utf-8')
        
        # Export merged.csv
        merged_file = get_output_path("merged.csv")
        merged_df.to_csv(merged_file, index=False, encoding='utf-8')
        
        # Export export.csv (new entries only)
        export_file = get_output_path("export.csv")
        export_df.to_csv(export_file, index=False, encoding='utf-8')
        
        console.print("Export completed successfully!", style="purple4")
        
        # Display summary
        console.print("Files exported:", style="green")
        console.print(f"  ratings.csv: {ratings_file}", style="green")
        console.print(f"  watched.csv: {watched_file}", style="green")
        console.print(f"  merged.csv: {merged_file}", style="green")
        console.print(f"  export.csv: {export_file}", style="green")
        
    except Exception as e:
        console.print(f"Export failed: {e}", style="red")
        raise
    
    return len(export_df) > 0