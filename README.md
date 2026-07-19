# trakt-to-letterboxd

Sync Trakt movie watches to Letterboxd via the `ttl` CLI.

- Pull new watches from Trakt into `export.csv` (accumulates)
- Upload `export.csv` to Letterboxd, then clear it on success
- Manual Cloudflare Turnstile in Chrome when Letterboxd requires it

## Install

Requires [pipx](https://pipx.pypa.io/) and Google Chrome.

```bash
pipx install trakt-to-letterboxd
```

From GitHub (latest main, or before a PyPI release exists):

```bash
pipx install git+https://github.com/louiscrc/trakt-to-letterboxd.git
```

This installs the `ttl` command globally. Check with `ttl --help`.

## Setup

```bash
ttl init
# Prompts for Letterboxd username/password and Trakt client ID/secret
```

Non-interactive (writes a template to edit by hand):

```bash
ttl init --non-interactive
```

Get Trakt API credentials at https://trakt.tv/oauth/applications/new (redirect URI: `urn:ietf:wg:oauth:2.0:oob`).

On first Trakt sync you'll authenticate via device code.

`config.yml` stores your Letterboxd password in plaintext. Keep the data directory private and never commit that file.

## Usage

```bash
ttl --version
ttl init                      # interactive config setup
ttl init --non-interactive    # write template config only
ttl trakt                     # pull new watches from Trakt into export.csv
ttl letterboxd                # upload export.csv to Letterboxd, then clear it
ttl sync                      # trakt then letterboxd (stops if trakt fails)
ttl letterboxd --no-diary     # skip diary entries on Letterboxd import
ttl letterboxd --manual-sign-in  # fill credentials but do not auto-click Sign In
ttl trakt --dry-run           # Trakt: fetch only, no CSV writes
ttl letterboxd --dry-run      # Letterboxd: stop before Import Films (Ctrl-C to exit)
ttl trakt -v                  # verbose progress logs
ttl trakt --config /path.yml  # custom config path
```

### Letterboxd upload flow

`ttl letterboxd` opens Chrome and:

1. Navigates to **letterboxd.com** — complete Turnstile if Cloudflare shows it
2. If not logged in, opens **sign-in**, pre-fills credentials, and tries to click **Sign In** automatically. Use `--manual-sign-in` to click yourself when the automatic click fails (Cloudflare sometimes treats it as a bot).
3. Uploads `export.csv`, clicks **Import Films**, waits for **Saved N films.**

## Data directory

`ttl` stores all user data in a fixed app folder (created automatically). It does **not** use your current working directory.

| Platform | Directory |
|----------|-----------|
| macOS | `~/Library/Application Support/trakt-to-letterboxd/` |
| Linux | `~/.local/share/trakt-to-letterboxd/` (or `$XDG_DATA_HOME/trakt-to-letterboxd/`) |
| Windows | `%LOCALAPPDATA%\trakt-to-letterboxd\` |

Layout:

| Path | Description |
|------|-------------|
| `config.yml` | Credentials and Trakt OAuth state |
| `csv/export.csv` | Pending queue for Letterboxd (grows with `ttl trakt`, cleared after successful `ttl letterboxd`) |
| `csv/merged.csv` | Full Trakt merged history (ratings + watch history) |
| `csv/ratings.csv` | Trakt ratings |
| `csv/watched.csv` | Trakt watch history |
| `chrome_profile/` | Persistent Chrome session (Letterboxd login) |

CSV format: `Title,Year,Rating10,Rewatch,imdbID,WatchedDate`

`ttl init` prints the resolved paths. Override only the config file with `--config /path/to/config.yml` if needed; CSVs and the Chrome profile always stay under the data directory above.

### Automation limits

Fully unattended / headless mode is not reliable: starting Chrome headless systematically re-triggers Cloudflare. In normal (headed) mode you usually only need to complete Turnstile (and occasionally Sign In) once in a while; a warm `chrome_profile` keeps most runs automated.

### Development

Install from source:

```bash
git clone https://github.com/louiscrc/trakt-to-letterboxd.git
cd trakt-to-letterboxd
pipx install -e .
```

Optional environment overrides for Chrome (advanced):

| Variable | Purpose |
|----------|---------|
| `CHROME_BIN` | Path to the Chrome/Chromium binary |
| `CHROMEDRIVER_PATH` | Path to a local chromedriver (skips webdriver-manager) |

## License

MIT © Louis Cresci. See [LICENSE](LICENSE).
