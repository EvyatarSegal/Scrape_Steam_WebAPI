import requests
import time
import logging
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class BaseExtractor:
    def __init__(self):
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504, 429])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

class SteamWebAPI(BaseExtractor):
    """
    Interacts with official Steam Web API.
    Docs: https://partner.steamgames.com/doc/webapi/ISteamApps
    """
    BASE_URL = "https://api.steampowered.com"
    STORE_URL = "https://store.steampowered.com/api/appdetails"

    def __init__(self, api_key=None):
        super().__init__()
        self.api_key = api_key

    def get_app_list(self):
        """Fetches the full list of AppIDs using pagination (IStoreService)."""
        url = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
        params = {'key': self.api_key, 'include_games': 1} # truncated for brevity
        all_apps = []
        last_appid = None
        more_results = True
        
        try:
            while more_results:
                if last_appid:
                    params['last_appid'] = last_appid
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json().get('response', {})
                
                apps = data.get('apps', [])
                if not apps:
                    break
                    
                all_apps.extend(apps)
                
                last_appid = data.get('last_appid')
                more_results = data.get('have_more_results', False)
                
                logger.info(f"Fetched batch. Total so far: {len(all_apps)}")
                
            logger.info(f"Total apps fetched: {len(all_apps)}")
            return all_apps

        except Exception as e:
            logger.error(f"Failed to fetch App List: {e}")
            return []

    def get_full_app_list_v2(self):
        """
        Fetches the COMPLETELY UNFILTERED list of all AppIDs.
        This includes DLC, Videos, Tools, and items not listed on the store.
        Warning: This is a large, non-paginated JSON response (~220,000+ items).
        """
        url = f"{self.BASE_URL}/ISteamApps/GetAppList/v2/"
        try:
            logger.info("Fetching full unfiltered app list (v2)...")
            response = self.session.get(url)
            response.raise_for_status()
            apps = response.json().get('applist', {}).get('apps', [])
            logger.info(f"Total unfiltered apps fetched: {len(apps)}")
            return apps
        except Exception as e:
            logger.error(f"Failed to fetch unfiltered App List: {e}")
            return []

    @sleep_and_retry
    @limits(calls=150, period=300) # Conservative: 150 calls per 5 mins (Steam Store is strict)
    def get_store_details(self, app_id):
        """
        Fetches details from the Store API (public).
        Note: The Store API has strict rate limits compared to the Web API.
        """
        params = {'appids': app_id, 'cc': 'us', 'l': 'english'}
        try:
            response = self.session.get(self.STORE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if data and str(app_id) in data and data[str(app_id)]['success']:
                return data[str(app_id)]['data']
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch Store details for {app_id}: {e}")
            return None

class SteamSpyAPI(BaseExtractor):
    """
    Interacts with SteamSpy API.
    Docs: https://steamspy.com/api.php
    Rate Limit: 4 requests per second.
    """
    BASE_URL = "https://steamspy.com/api.php"

    @sleep_and_retry
    @limits(calls=3, period=1) # Conservative: 3 calls per second
    def get_app_details(self, app_id):
        params = {'request': 'appdetails', 'appid': app_id}
        try:
            response = self.session.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch SteamSpy details for {app_id}: {e}")
            return None
