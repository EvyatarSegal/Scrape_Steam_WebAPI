import pytest
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.db.models import Base, RawGameData, GameAnalytics
from src.etl.loader import DATABASE_URL, apply_transformations

# Use the real DB for integration testing (or use a test one if configured)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

@pytest.fixture(scope="module")
def db_session():
    # Setup
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    # Teardown
    session.close()

def test_transformation_logic(db_session):
    """
    Sanity Check: Inserts raw data -> Runs SQL Transform -> Verifies Analytics Table
    """
    # 1. Clean verify table
    db_session.execute(text("TRUNCATE TABLE raw_game_data CASCADE"))
    db_session.execute(text("TRUNCATE TABLE game_analytics CASCADE"))
    db_session.commit()

    # 2. Insert Mock Data
    mock_game = RawGameData(
        appid=12345,
        steamspy_data={
            "name": "Test Game AAA",
            "developer": "Valve",
            "publisher": "Electronic Arts",
            "price": "5999",
            "owners": "1,000,000 .. 2,000,000",
            "ccu": 500,
            "positive": 1000,
            "negative": 100,
            "userscore": 85,
            "tags": {"Action": 100, "Shooter": 50}
        }
    )
    
    mock_indie = RawGameData(
        appid=67890,
        steamspy_data={
            "name": "Test Indie Gem",
            "developer": "SoloDev",
            "publisher": "SoloDev",
            "price": "999",
            "owners": "20,000 .. 50,000",
            "positive": 500,
            "negative": 10,
            "userscore": 0,
            "tags": {"Indie": 200, "Puzzle": 150}
        }
    )

    db_session.add(mock_game)
    db_session.add(mock_indie)
    db_session.commit()

    # 3. Apply Transformations
    apply_transformations()
    
    # Manually trigger the refresh procedure since apply_transformations only defines it
    db_session.execute(text("CALL refresh_analytics()"))
    db_session.commit()

    # 4. Assert Results
    aaa_result = db_session.query(GameAnalytics).filter_by(appid=12345).first()
    indie_result = db_session.query(GameAnalytics).filter_by(appid=67890).first()

    assert aaa_result is not None
    assert aaa_result.publisher_tier == "AAA", "EA should be AAA"
    assert aaa_result.price_initial == 59.99
    assert aaa_result.positive_reviews == 1000
    assert aaa_result.owners_midpoint == 1500000
    # Check tags (order might vary)
    assert set(aaa_result.tags) == {"Action", "Shooter"}
    
    assert indie_result is not None
    assert indie_result.publisher_tier == "Indie"
    assert indie_result.price_initial == 9.99
    assert set(indie_result.tags) == {"Indie", "Puzzle"}
