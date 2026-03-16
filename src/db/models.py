from sqlalchemy import Column, Integer, String, DateTime, Boolean
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