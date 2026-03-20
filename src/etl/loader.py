import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.models import Base, SteamApp, RawGameData
from src.etl.extractors import SteamWebAPI, SteamSpyAPI
from dotenv import load_dotenv

load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database Connection
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB", "steam_market")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

from sqlalchemy import text, func

def init_db():
    """Creates the database tables if they don't exist."""
    logger.info("Initializing Database Tables...")
    Base.metadata.create_all(engine)
    logger.info("Database Initialized.")

def clear_app_list():
    """Wipes the app list and raw data to allow for a fresh re-initialization."""
    session = SessionLocal()
    try:
        logger.warning("TRUNCATING steam_apps and raw_game_data tables...")
        session.execute(text("TRUNCATE TABLE steam_apps CASCADE;"))
        session.execute(text("TRUNCATE TABLE raw_game_data CASCADE;"))
        session.execute(text("TRUNCATE TABLE game_analytics CASCADE;"))
        session.commit()
        logger.info("Database wiped successfully.")
    except Exception as e:
        logger.error(f"Failed to wipe database: {e}")
        session.rollback()
    finally:
        session.close()

def apply_transformations():
    """Reads and applies the SQL transformation Logic."""
    try:
        logger.info("Applying SQL Transformations...")
        with open('src/db/transformations.sql', 'r') as f:
            sql_script = f.read()
            
        # SQLAlchemy text() treats % as a parameter placeholder. 
        # We need to escape it to %% for it to be treated as a literal.
        sql_script = sql_script.replace('%', '%%')
            
        with engine.connect() as connection:
            connection.execute(text(sql_script))
            connection.commit()
            
        logger.info("Transformations applied successfully.")
    except Exception as e:
        logger.error(f"Failed to apply transformations: {e}")



def update_app_list():
    """Fetches the full app list from Steam (including DLC, etc.) and updates the DB."""
    api = SteamWebAPI(api_key=os.getenv("STEAM_API_KEY"))
    apps = api.get_app_list()
    
    if not apps:
        logger.warning("No apps found or API failure.")
        return

    logger.info(f"Fetched {len(apps)} apps from Steam. updating database...")
    
    session = SessionLocal()
    try:
        # Optimization: Bulk insert/ignore is complex in pure ORM, 
        # for now we strictly check existence or use merge.
        # Given 100k+ apps, a slower robust method is safer for first run.
        
        # Pull existing IDs into a set for fast lookup
        existing_ids = {id[0] for id in session.query(SteamApp.appid).all()}
        
        new_objects = []
        for app in apps:
            appid = app.get('appid')
            name = app.get('name')
            if appid and appid not in existing_ids:
                new_objects.append(SteamApp(appid=appid, name=name))
        
        if new_objects:
            logger.info(f"Adding {len(new_objects)} new apps to the database.")
            # Insert in chunks to avoid memory issues
            CHUNK_SIZE = 5000
            for i in range(0, len(new_objects), CHUNK_SIZE):
                session.bulk_save_objects(new_objects[i:i+CHUNK_SIZE])
                session.commit()
                logger.info(f"Committed chunk {i} - {i+CHUNK_SIZE}")
        else:
            logger.info("No new apps to add.")
            
    except Exception as e:
        logger.error(f"Error updating app list: {e}")
        session.rollback()
    finally:
        session.close()

def run_extraction_batch(limit=100):
    """
    Main Loop:
    1. Finds apps that haven't been fetched yet.
    2. Calls Store API and SteamSpy API.
    3. Saves Raw JSON.
    """
    session = SessionLocal()
    steam_api = SteamWebAPI(api_key=os.getenv("STEAM_API_KEY"))
    spy_api = SteamSpyAPI()
    
    try:
        while True:
            # If limit is 0, we treat it as "Run until done"
            # However, we still fetch in batches to avoid memory issues.
            batch_size = limit if limit > 0 else 100
            
            # Get pending apps
            apps_to_fetch = session.query(SteamApp).filter(SteamApp.is_fetched == False).limit(batch_size).all()
            
            if not apps_to_fetch:
                logger.info("No pending apps to fetch. Batch complete.")
                break

            logger.info(f"Starting batch extraction for {len(apps_to_fetch)} apps...")

            for app in apps_to_fetch:
                logger.info(f"Processing AppID: {app.appid} - {app.name}")
                
                # 1. Fetch Store Data
                store_data = steam_api.get_store_details(app.appid)
                
                # 2. Fetch SteamSpy Data
                spy_data = spy_api.get_app_details(app.appid)
                
                # 3. Save Raw Data
                # Upsert logic for RawGameData
                raw_entry = session.query(RawGameData).get(app.appid)
                if not raw_entry:
                    raw_entry = RawGameData(appid=app.appid)
                
                raw_entry.steam_store_data = store_data
                raw_entry.steamspy_data = spy_data
                session.add(raw_entry)
                
                # 4. Mark as fetched
                app.is_fetched = True
                
                # Commit per item is safer for long running processes to avoid losing progress
                session.commit()
            
            # If a strict limit was set (not 0), we stop after one batch
            if limit > 0:
                break
            
    except Exception as e:
        logger.error(f"Fatal error in batch extraction: {e}")
    finally:
        session.close()

def refresh_existing_data():
    """
    Daily Refresh Loop:
    Iterates over EXISTING fetched apps and updates them using SteamSpy (Fast API).
    This ensures we capture CCU and Price changes daily without hitting Steam Store limits.
    """
    session = SessionLocal()
    spy_api = SteamSpyAPI()
    
    try:
        logger.info("Starting Daily Refresh (SteamSpy Only)...")
        # Get all fetched apps
        # In a real large DB, we might want to chunk this or use a cursor.
        # For simplicity in this logic, we'll iterate efficiently.
        # We assume we want to refresh ALL of them.
        
        apps = session.query(RawGameData).yield_per(100) # Use server-side cursor
        
        count = 0
        for raw_entry in apps:
            count += 1
            if count % 100 == 0:
                logger.info(f"Refreshed {count} apps...")
            
            # Fetch updated SteamSpy Data (Price, CCU, Tags)
            new_spy_data = spy_api.get_app_details(raw_entry.appid)
            
            if new_spy_data:
                raw_entry.steamspy_data = new_spy_data
                # We do NOT request steam_store_data to save quota
                
                # Update timestamp to reflect fresh data
                raw_entry.fetched_at = func.now()
                
                session.commit()
                
    except Exception as e:
        logger.error(f"Error during daily refresh: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    init_db()
    apply_transformations()
    update_app_list()
