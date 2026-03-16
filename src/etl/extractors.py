import requests
import logging
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)

class BaseExtractor:
    def __init__(self):
        self.session = requests.Session()
        # Handle 429 (Too Many Requests) and server errors automatically
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504, 429])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

class SteamWebAPI(BaseExtractor):
    BASE_URL = "http://api.steampowered.com"
    STORE_URL = "https://store.steampowered.com/api/appdetails"

    def __init__(self, api_key=None):
        super().__init__()
        self.api_key = api_key

    def get_app_list(self):
        url = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
        params = {'key': self.api_key, 'include_games': 1} # truncated for brevity
        all_apps = []
        last_appid = None
        more_results = True
        
        while more_results:
            if last_appid: params['last_appid'] = last_appid
            response = self.session.get(url, params=params)
            data = response.json().get('response', {})
            apps = data.get('apps', [])
            if not apps: break
            all_apps.extend(apps)
            last_appid = data.get('last_appid')
            more_results = data.get('have_more_results', False)
        return all_apps

    @sleep_and_retry
    @limits(calls=150, period=300) 
    def get_store_details(self, app_id):
        params = {'appids': app_id, 'cc': 'us', 'l': 'english'}
        response = self.session.get(self.STORE_URL, params=params)
        data = response.json()
        return data[str(app_id)]['data'] if data.get(str(app_id), {}).get('success') else None
    

    class SteamSpyAPI(BaseExtractor):
    BASE_URL = "https://steamspy.com/api.php"

    @sleep_and_retry
    @limits(calls=3, period=1) 
    def get_app_details(self, app_id):
        params = {'request': 'appdetails', 'appid': app_id}
        try:
            response = self.session.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch SteamSpy details for {app_id}: {e}")
            return None