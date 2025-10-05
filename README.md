# Letterboxd Trakt Sync

Automatically sync your Trakt movies to Letterboxd:

- Export your ratings and watch history from Trakt
- Auto-import to Letterboxd (with Selenium)
- Detect rewatches
- Convert ratings from 0-10 to 0-5 scale
- Incremental sync (only new movies)

## 🚀 Quick Start

### 1. Configuration

Create a `config.yml` file at the root:

```yaml
accounts:
  - letterboxd_username: your_username
    letterboxd_password: your_password
    trakt_client_id: your_client_id
    trakt_client_secret: your_client_secret
    internal: null
```

To get `trakt_client_id` and `trakt_client_secret`:
- Go to https://trakt.tv/oauth/applications/new
- Name: `letterboxd-trakt-sync`
- Redirect URI: `urn:ietf:wg:oauth:2.0:oob`
- Permissions: `/scrobble`

### 2. First Run

With docker-compose:
```bash
make setup
make run
```

**Without Docker (directly with Python):**
```bash
make setup_dev
make dev
```

On first run, you'll see an activation code:
```
Your user code is: ABCD1234
Navigate to https://trakt.tv/activate
```

Go to the link and enter the code to authorize access.

## 📁 Generated Files

CSV files are created in the `csv/` folder:

- `export.csv` - **New movies only** (to import to Letterboxd)
- `merged.csv` - Full history of all your movies
- `ratings.csv` - Your Trakt ratings
- `watched.csv` - Your Trakt watch history

Format: `Title,Year,Rating10,Rewatch,imdbID,WatchedDate`

## 📝 Notes

- Auto-import requires Chrome (included in Docker but headless mode only)
- Letterboxd password is required for auto-import
- Trakt tokens are automatically saved in `config.yml`
- Only new movies are imported on each run (incremental sync)