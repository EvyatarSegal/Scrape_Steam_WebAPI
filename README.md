# Steam Market Analysis ETL

### Abstract
This project implements an automated Extract, Transform, Load (ETL) pipeline designed for the large-scale acquisition and processing of the Steam gaming market dataset using python, dcoker, and sql. The system integrates the Steam Web API, Steam Store API, and SteamSpy to compile a comprehensive repository of over 220,000 items. Key functionalities include rate-limited API orchestration, persistent raw data ingestion using JSONB, and a SQL-driven transformation layer for normalized econometric analysis. The resulting database supports research into game pricing strategies, ownership distributions, and developer tiering within the digital distribution ecosystem.

---

## Setup for all users

This project uses **Docker** to handle the software environment. This allows the database and scripts to run with minimal manual configuration.

### Prerequisites

1. **Docker Desktop**: Download and install from the [official site](https://www.docker.com/products/docker-desktop/).
2. **Steam Web API Key**: Obtain a key from the [Steam Community dev page](https://steamcommunity.com/dev/apikey). Use `localhost` as the domain name.

### Installation

1. **Download the code**: [Download this repository as a ZIP file](https://github.com/EvyatarSegal/Scrape_Steam_WebAPI/archive/refs/heads/main.zip) and extract it to a folder.
2. **Configure your API key**: 
   - Find the file named `.env.example` in the project folder.
   - Rename it to `.env`.
   - Open the file with a text editor and paste your key after `STEAM_API_KEY=`.
3. **Run the project**:
   - Open a terminal or command prompt in the project folder.
   - Run the command: `docker-compose up -d`.

**That's it!** Docker Compose will automatically start the database and the ETL process. The scraper is configured to run on startup and will begin the data collection process immediately.

> [!NOTE]
> If you've just started the container and the database takes too long to initialize, you may need to **restart the `etl` container** in Docker Desktop specifically.

> [!WARNING]
> The process of fetching all the video games Should take around *122 Hours*, or 15 days if ran 8 hours every day.

---

## Technical Architecture

The pipeline implements an Extract, Transform, Load (ETL) process containerized for local or server deployment.

### Data Flow
1. **Discovery**: The `fetch_list` task queries the Steam Web API to populate the `steam_apps` table with all AppIDs on the Steam store.
2. **Ingestion**: The `fetch_data` task retrieves JSON responses (Meaning, the metadata of every game in the `steam_apps` table) from the Steam Store and SteamSpy APIs. These are stored as raw blobs in the `raw_game_data` table.
3. **Transformation**: The `refresh_analytics()` SQL procedure parses the raw JSON. It flattens the data into the structured `game_analytics` table, handles currency normalization, and applies publisher tiering. (In simple language, this take the details and makes them readable)

### Database Design
The system uses a three-tier schema in PostgreSQL:
- **`steam_apps`**: Tracks which game IDs exist and whether their metadata has been collected.
- **`raw_game_data`**: Raw JSON responses. This allows the transformation logic to be updated without re-running API requests.
- **`game_analytics`**: The final production table, indexed for SQL queries and compatible with visualization tools like PowerBI or Tableau.

---

## Script Breakdown

### `main.py`
The entry point for the application. It uses `argparse` to provide a command-line interface for specific tasks.
- **`--task`**: Used to run `init` (database setup), `fetch_list` (discovery), `fetch_data` (metadata extraction), `full_run`, `reinit_apps`, or `transform`.
- **`reinit_apps`**: A special task that **wipes the database** and performs a fresh, unfiltered fetch (~220k+ items) using the V2 API.
- **`transform`**: Re-applies the SQL transformation logic (Views/Procedures) from `src/db/transformations.sql`. Use this if you've manually edited the SQL file.
- **`--limit`**: Controls the number of games processed in a single batch.
- **`--loop`**: Activates a 24-hour scheduler for continuous data updates.

---

## Docker CLI Reference

If you want to run specific tasks manually while the container is running, use these commands:

| Action | Command |
| :--- | :--- |
| **Get Full App List (220k)** | `docker-compose exec etl python main.py --task reinit_apps` |
| **Apply SQL Changes** | `docker-compose exec etl python main.py --task transform` |
| **Normal App Refresh (160k)** | `docker-compose exec etl python main.py --task fetch_list` |
| **Fetch 100 Games** | `docker-compose exec etl python main.py --task fetch_data --limit 100` |
| **Fetch ALL Games** | `docker-compose exec etl python main.py --task fetch_data --limit 0` |
| **View Scraper Logs** | `docker-compose logs -f etl` |
| **Access Database (PSQL)** | `docker-compose exec db psql -U admin -d steam_market` |

---

### `src/etl/extractors.py`
This module manages all outgoing API requests. It uses `urllib3` retry logic to handle network timeouts and 500-series errors. It enforces a limit of 4 requests per second for SteamSpy and manages strict throttling for the Steam Store public API.

### `src/etl/loader.py`
The orchestrator that moves data between the API extractors and the database. It handles batch saves for the initial AppID list and uses atomic commits for game metadata to prevent data loss during interruptions.

### `src/db/models.py`
Defines the database structure using SQLAlchemy. This ensures type safety and maintains the relationship between the raw data and the analytical tables.

### `src/db/transformations.sql`
Contains the SQL logic for data cleaning.
- **`etl_v_game_analytics` (View)**: Parses JSONB columns, converts currencies, and extracts nested genre information.
- **Tiering Logic**: Categorizes publishers as AAA, AA, or Indie based on market performance and publisher names.

---

## Data Dictionary (`game_analytics` table)

### Core Game Information
| Column | Type | Description |
| :--- | :--- | :--- |
| `appid` | Integer | Unique Steam ID for the game (Primary Key). |
| `name` | String | The official title of the game. |
| `genre_primary` | String | The primary genre (e.g., Action, RPG, Indie). |
| `developer` | String | The company that developed the game. |
| `publisher` | String | The company that published the game. |
| `publisher_tier` | String | Categorized as `AAA`, `AA`, or `Indie` based on market performance and name. |
| `release_date` | Timestamp | Official release date on Steam. |
| `tags` | Array | User-defined tags (e.g., "Open World", "Soulslike"). |

### Pricing & Financials
| Column | Type | Description |
| :--- | :--- | :--- |
| `price_initial` | Double | Original price before any discounts (in USD). |
| `price_final` | Double | Current selling price after discounts (in USD). |
| `discount_percent` | Double | The active discount percentage (0-100). |
| `is_free` | Boolean | `True` if the game is Free-to-Play. |

### Ownership & Engagement
| Column | Type | Description |
| :--- | :--- | :--- |
| `owners_min` | BigInt | Estimated minimum number of owners (Source: SteamSpy). |
| `owners_max` | BigInt | Estimated maximum number of owners (Source: SteamSpy). |
| `owners_midpoint` | BigInt | The average of min/max owners (used for tiering). |
| `positive_reviews` | Integer | Total number of positive user reviews. |
| `negative_reviews` | Integer | Total number of negative user reviews. |
| `ccu` | Integer | Current Concurrent Users (active players right now). |
| `peak_ccu` | Integer | Highest recorded concurrent players. |

### Technical & Features
| Column | Type | Description |
| :--- | :--- | :--- |
| `pc_req_min` | String | Minimum PC system requirements (Raw text). |
| `pc_req_rec` | String | Recommended PC system requirements (Raw text). |
| `required_age` | Integer | Age rating (e.g., 0, 13, 17, 18). |
| `languages_count` | Integer | Number of supported languages. |
| `achievement_count` | Integer | Total number of Steam accomplishments available. |
| `dlc_count` | Integer | Total number of Downloadable Content items. |
| `is_early_access` | Boolean | `True` if the game is currently in Early Access. |
| `steam_deck` | Boolean | `True` if the game is Steam Deck Verified. |
| `controller_support` | Boolean | `True` if the game has Full Controller Support. |

---

## Common Errors & Troubleshooting

| Error | Cause | Solution |
| :--- | :--- | :--- |
| **`401 Unauthorized`** | Missing or invalid `STEAM_API_KEY`. | Ensure your `.env` file has the correct key and no extra spaces. |
| **`404 Not Found`** | Occurs if the Steam API URL is broken or uses `http` instead of `https`. | This is fixed in the latest version. Ensure you use `https`. |
| **`Name or service not known`** | The scraper (`etl`) cannot find the database (`db`). | Ensure both services are running in the same Docker network. Try `docker-compose down` followed by `up -d`. |
| **`Database uninitialized`** | The database started without a password. | Ensure `POSTGRES_PASSWORD` is set in `.env` or use the default fallbacks in `docker-compose.yml`. |
| **`Connection Refused`** | Database is still booting up. | In Docker Desktop, **restart the `etl` container** manually after a few seconds. |
| **`429 Too Many Requests`** | You've hit Steam's strict rate limits. | The script handles this automatically by waiting. If it persists, try increasing the `@limits` period in `extractors.py`. |

---

## 📝 License
[MIT License](LICENSE)