# yourfm

Personal internet radio station powered by Icecast, Firebird SQL, and a custom Python-driven ices0 streamer.


<img width="1920" height="1200" alt="public" src="https://github.com/user-attachments/assets/857fb1cc-6d21-4639-aceb-3c87bcc4ba1c" />


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
- `docker-compose.yml`: Main orchestration for production services.
- `indexer.yml`: Configuration for the standalone indexer service.

## Requirements

- **Docker** and **Docker Compose**.
- A music library accessible on the host (defaults to `/var/data/music`).
- An API key for Discogs for metadata indexing.
  (Get one here: https://www.discogs.com/developers/)

## Downloading
1. git clone https://github.com/yourfm/yourfm.git
2. cd yourfm
3. git submodule update --init --recursive


## Setup & Run

1.  **Configure the environment**:
   
    - Review and update paths and change passwords in `.env` and add your Discogs API key.
        
    - Ensure your music library is available at `/var/data/music` or update the volume mapping in `docker-compose.yml`.

2.  **Start the services**:
    ```bash
    docker-compose up firebird -d
    docker-compose -f indexer.yml up -d
    ```
    Wait for the indexer to finish indexing your music before starting the Icecast server:
    ```bash
    docker-compose up icecast -d
    docker-compose up app -d
    ```
    **Note**: The `app` service will start streaming (using `ices`) and provides a web interface (via Nginx and Gunicorn) to show track information, control playback, and edit metadata.
    The web interface is available at `http://localhost:8090`.
               


3.  **Indexing your music**:
    The standalone `indexer` service (run via `indexer.yml`) is configured to run `indexmedia.py` on startup, which scans your music library and populates the database. 
    Logs are typically written to the location specified in `data/iceshake.ini`.

4.  **Accessing the stream**:
    Once running, the Icecast server is available at `http://localhost:8000`. 
    The default mount point is `/docker` (as configured in `data/ices.conf`).

## Scripts & Entry Points

- **`app` container**: Integrates Nginx as a reverse proxy for Gunicorn (web UI) and `ices` (audio streamer).
- **`indexmedia.py`**: The primary entry point for scanning the filesystem, extracting tags (using `mutagen`, `mediafile`), and saving them to Firebird.
- **`ices` (custom binary)**: Integrated within the `app` container, it's a version of ices0 compiled with Python support. It loads `index.py` to determine the playback order.
- **`index.py`**: Contains `ices_get_next()` which queries the Firebird database for the next track to play.

## Configuration & Env Vars

### `docker-compose.yml` Environment Variables:
All environment variables can be managed in a `.env` file in the project root. See `.env.dist` for a template.

- **Firebird**:
  - `FIREBIRD_USER`: default `shiva`
  - `FIREBIRD_PASSWORD`: default `shiva`
  - `FIREBIRD_DATABASE`: default `iceshake.fdb`
  - `FIREBIRD_ROOT_PASSWORD`: default `masterkey`
- **Icecast**:
  - `IC_SOURCE_PASSWORD`: Password for ices to connect.
  - `IC_ADMIN_PASSWORD`: Password for the Icecast web interface.
  - `IC_HOSTNAME`: default `localhost`
  - `IC_LOCATION`: default `Germany`
  - `IC_ADMIN_EMAIL`: default `admin@localhost`
- **Indexer**:
  - `DISCOGS_API_KEY`: API key for Discogs.
  - `MUSIC_LIBRARY`: Root of the music library (defaults to `/var/data/music`).

### `data/iceshake.ini`:
The settings in `iceshake.ini` can be overridden by environment variables defined in `.env`.
- `[Connection]`: Database connection details (overridden by `FIREBIRD_*` vars).
- `[Indexer]`: 
  - `basedir`: Root of the music library (overridden by `MUSIC_LIBRARY`).
  - `discogs`: API key for Discogs (overridden by `DISCOGS_API_KEY`).
  

## Tests

- TODO: Add information about automated tests if available. 
- Manual verification can be done by checking the Icecast admin panel (`http://localhost:8000/admin/`) or the `indexer` container logs.

## License

This project includes components under different licenses:
- `icecast-kh-docker`: See `icecast-kh-docker/LICENSE`.
- `indexer`: See `indexer/LICENSE`.
- Project Root: See `LICENSE` in the root directory.

