from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
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