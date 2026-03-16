import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logger = logging.getLogger(__name__)

class BaseExtractor:
    def __init__(self):
        self.session = requests.Session()
        # Handle 429 (Too Many Requests) and server errors automatically
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504, 429])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))