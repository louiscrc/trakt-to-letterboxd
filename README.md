# Letterboxd Trakt Sync

Export your Trakt movies to CSV and import them to Letterboxd.

- Pull new watches from Trakt into `export.csv` (accumulates)
- Upload `export.csv` to Letterboxd, then clear it on success
- Manual Cloudflare Turnstile in Chrome for Letterboxd login

## Setup

```bash
cp config.template.yml config.yml
# Fill in letterboxd_username, letterboxd_password, trakt_client_id, trakt_client_secret

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p csv
```

Get Trakt API credentials at https://trakt.tv/oauth/applications/new (redirect URI: `urn:ietf:wg:oauth:2.0:oob`).

On first Trakt sync you'll authenticate via device code.

## Usage

```bash
python ttl ...            
-t, --trakt               # pull new watches from Trakt into csv/export.csv (accumulates)
-l, --letterboxd          # upload csv/export.csv to Letterboxd, then clear it
--no-diary                # skip diary entries on Letterboxd import (only with -l/--letterboxd)
--dry-run                 # Trakt: fetch only, no CSV writes. Letterboxd: stop before Import Films (Ctrl-C to exit)
-v, --verbose             # show detailed progress logs
```

### Letterboxd upload flow

`python ttl -l` opens Chrome and:

1. Navigates to **letterboxd.com** — if displayed, *you need to complete Cloudflare Turnstile in the browser*
2. If not logged-in, opens **sign-in** with credentials pre-filled, *you need to click Sign-In in the browser*
3. Uploads `csv/export.csv`, clicks **Import Films**, waits for **Saved N films.**

Requires Google Chrome installed locally.

## Generated files

| File | Description |
|------|-------------|
| `csv/export.csv` | Pending queue for Letterboxd (grows with `-t`, cleared after successful `-l`) |
| `csv/merged.csv` | Full merged history |
| `csv/ratings.csv` | Trakt ratings |
| `csv/watched.csv` | Trakt watch history |

Format: `Title,Year,Rating10,Rewatch,imdbID,WatchedDate`

## Comment about full-auto mode

Fully automated mode isn't possible, despite using the exact same chrome_profile, starting the browser headless mode systematically re-triggers the Cloudflare challenge.
But in headfull mode, you only need to complete the Cloudflare challenge and manual "log-in" click once on a while, the rest of the time the process is 100% automated even if the browser is opened.