from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Boolean, BigInteger, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class SteamApp(Base):
    """
    Master list of all apps on Steam.
    Source: Steam Web API (ISteamApps/GetAppList)
    """
    __tablename__ = 'steam_apps'

    appid = Column(Integer, primary_key=True)
    name = Column(String)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_fetched = Column(Boolean, default=False, index=True)

class RawGameData(Base):
    """
    Raw JSON data fetched from APIs. 
    We store the raw response to allow for re-parsing without re-fetching.
    """
    __tablename__ = 'raw_game_data'

    appid = Column(Integer, primary_key=True)
    steam_store_data = Column(JSON, nullable=True) # From store.steampowered.com
    steamspy_data = Column(JSON, nullable=True)    # From steamspy.com
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


from sqlalchemy import

class GameAnalytics(Base):
    """
    Processed flat table for analysis.
    This will be populated via SQL transformations or Python ETL.
    """
    __tablename__ = 'game_analytics'

    appid = Column(Integer, primary_key=True)
    name = Column(String)
    genre_primary = Column(String)
    developer = Column(String)
    publisher = Column(String)
    publisher_tier = Column(String) 
    
    price_initial = Column(Float)
    price_final = Column(Float)
    discount_percent = Column(Float)
    
    owners_min = Column(BigInteger)
    owners_max = Column(BigInteger)
    owners_midpoint = Column(BigInteger)
    
    positive_reviews = Column(Integer)
    negative_reviews = Column(Integer)
    tags = Column(ARRAY(String)) 
    
    release_date = Column(DateTime)
    ccu = Column(Integer) 
    peak_ccu = Column(Integer) 
    
    pc_req_min = Column(String) 
    pc_req_rec = Column(String) 
    required_age = Column(Integer)
    
    languages_count = Column(Integer)
    achievement_count = Column(Integer)
    dlc_count = Column(Integer)
    
    is_early_access = Column(Boolean)
    is_free = Column(Boolean)
    steam_deck = Column(Boolean) 
    controller_support = Column(Boolean)