# yourfm

Personal internet radio station powered by Icecast, Firebird SQL, and a custom Python-driven ices0 streamer.

## Overview

`yourfm` is a complete setup for running a private internet radio station. It uses:
- **Icecast-KH**: The streaming server.
- **Firebird SQL**: Database for managing track metadata and playlist logic.
- **Python Indexer & Streamer**: A collection of scripts to index music files and a custom-built `ices0` to stream audio to Icecast using Python-defined playlist logic.

## Project Structure

- `data/`: Configuration files and persistent database storage.
  - `iceshake.fdb`: Firebird database (created on first run).
  - `iceshake.ini`: Main application configuration.
  - `ices.conf`: Configuration for the ices0 streamer.
- `ddl/`: SQL scripts for database initialization.
- `icecast-kh-docker/`: Docker configuration for the Icecast-KH server.
- `indexer/`: Python source code for indexing and playlist management.
  - `indexmedia.py`: Script to scan and index music files.
  - `index.py`: Python module used by `ices` to fetch the next track.
  - `tools.py` / `connector.py`: Database connectivity helpers.
- `docker-compose.yml`: Orchestration for all services.

## Requirements

- **Docker** and **Docker Compose**.
- A music library located on the host (defaults to `/var/data/music`).
- (Optional) API keys for Discogs and Last.fm for enhanced metadata indexing.

## Setup & Run

1.  **Configure the environment**:
    - Copy `data/iceshake.ini.dist` to `data/iceshake.ini` and review and update paths or API keys if necessary.
    - Ensure your music library is available at `/var/data/music` or update the volume mapping in `docker-compose.yml`.

2.  **Start the services**:
    ```bash
    docker-compose up -d
    ```

3.  **Indexing your music**:
    The `indexer` service is configured to run `indexmedia.py` on startup, which scans your music library and populates the database. 
    Logs are typically written to the location specified in `data/iceshake.ini`.

4.  **Accessing the stream**:
    Once running, the Icecast server is available at `http://localhost:8000`. 
    The default mount point is `/docker` (as configured in `data/ices.conf`).

## Scripts & Entry Points

- **`indexmedia.py`**: The primary entry point for scanning the filesystem, extracting tags (using `mutagen`, `mediafile`), and saving them to Firebird.
- **`ices` (custom binary)**: Located in the indexer container, it's a version of ices0 compiled with Python support. It loads `index.py` to determine the playback order.
- **`index.py`**: Contains `ices_get_next()` which queries the Firebird database for the next track to play.

## Configuration & Env Vars

### `docker-compose.yml` Environment Variables:
- **Firebird**:
  - `FIREBIRD_USER`: default `shiva`
  - `FIREBIRD_PASSWORD`: default `shiva`
  - `FIREBIRD_DATABASE`: default `iceshake.fdb`
- **Icecast**:
  - `IC_SOURCE_PASSWORD`: Password for ices to connect.
  - `IC_ADMIN_PASSWORD`: Password for the Icecast web interface.

### `data/iceshake.ini`:
- `[Connection]`: Database connection details.
- `[Indexer]`: 
  - `basedir`: Root of the music library.
  - `dirs`: Subdirectories to scan.
  - `discogs`: API key for Discogs.
  - `LASTFM_API_KEY`: API key for Last.fm.

## Tests

- TODO: Add information about automated tests if available. 
- Manual verification can be done by checking the Icecast admin panel (`http://localhost:8000/admin/`) or the `indexer` container logs.

## License

This project includes components under different licenses:
- `icecast-kh-docker`: See `icecast-kh-docker/LICENSE`.
- `indexer`: See `indexer/LICENSE`.
- Project Root: See `LICENSE` in the root directory.
