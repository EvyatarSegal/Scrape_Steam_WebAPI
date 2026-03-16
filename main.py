import argparse
import logging
import time
from src.etl.loader import init_db, update_app_list, run_extraction_batch, apply_transformations, refresh_existing_data

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Steam Market Analysis ETL CLI")
    parser.add_argument('--task', type=str, required=False, 
                        choices=['init', 'fetch_list', 'fetch_data', 'full_run'],
                        help="Task to perform")
    parser.add_argument('--limit', type=int, default=50, help="Limit for batch (0 = fetch ALL, infinite loop)")
    parser.add_argument('--loop', action='store_true', help="Run continuously every 24h")

    args = parser.parse_args()
    
    # Scheduler Mode
    if args.loop:
        logger.info("--- Starting Scheduler Mode (24h Interval) ---")
        while True:
            try:
                logger.info(">>> Starting Daily ETL Run")
                init_db()
                apply_transformations()
                update_app_list()
                # 2. Fetch NEW Data (for newly added apps)
                run_extraction_batch(limit=args.limit)
                
                # Refresh Analytics Table
                from src.etl.loader import engine
                from sqlalchemy import text
                with engine.connect() as conn:
                    conn.execute(text("CALL refresh_analytics();"))
                    conn.commit()
                
                logger.info(">>> Batch Run Complete. Sleeping for 24h...")
                
                logger.info(">>> Daily ETL Run Complete. Sleeping for 24h...")
            except Exception as e:
                logger.error(f"Scheduler Error: {e}")
            
            time.sleep(86400)

    elif args.task == 'init':
        init_db()
        apply_transformations()
    
    elif args.task == 'fetch_list':
        init_db()
        apply_transformations()
        update_app_list()
    
    elif args.task == 'fetch_data':
        init_db()
        apply_transformations()
        run_extraction_batch(limit=args.limit)
        
    elif args.task == 'full_run':
        init_db()
        apply_transformations()
        update_app_list()
        run_extraction_batch(limit=args.limit)

if __name__ == "__main__":
    main()
