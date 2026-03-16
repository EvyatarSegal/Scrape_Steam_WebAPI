import pytest
from unittest.mock import MagicMock, patch
from src.etl.extractors import SteamWebAPI, SteamSpyAPI

@pytest.fixture
def mock_response():
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    return mock

class TestSteamWebAPI:
    @patch('src.etl.extractors.requests.Session')
    def test_get_app_list_success(self, mock_session, mock_response):
        # Setup mock
        mock_data = {
            "response": {
                "apps": [
                    {"appid": 10, "name": "Test Game 1"},
                    {"appid": 20, "name": "Test Game 2"}
                ]
            }
        }
        mock_response.json.return_value = mock_data
        mock_response.status_code = 200
        mock_session.return_value.get.return_value = mock_response

        # Test
        api = SteamWebAPI(api_key="TEST_KEY")
        apps = api.get_app_list()

        assert len(apps) == 2
        assert apps[0]['name'] == "Test Game 1"
        assert apps[1]['appid'] == 20

    @patch('src.etl.extractors.requests.Session')
    def test_get_store_details_success(self, mock_session, mock_response):
        # Setup mock
        app_id = 10
        mock_data = {
            str(app_id): {
                "success": True,
                "data": {"name": "Counter-Strike", "price_overview": {"final": 999}}
            }
        }
        mock_response.json.return_value = mock_data
        mock_session.return_value.get.return_value = mock_response

        # Test
        api = SteamWebAPI(api_key="TEST_KEY")
        data = api.get_store_details(app_id)

        assert data is not None
        assert data['name'] == "Counter-Strike"
        assert data['price_overview']['final'] == 999

class TestSteamSpyAPI:
    @patch('src.etl.extractors.requests.Session')
    def test_get_app_details_success(self, mock_session, mock_response):
        app_id = 999
        mock_data = {"appid": 999, "name": "Indie Gem", "owners": "20,000 .. 50,000"}
        
        mock_response.json.return_value = mock_data
        mock_session.return_value.get.return_value = mock_response

        api = SteamSpyAPI()
        data = api.get_app_details(app_id)

        assert data['name'] == "Indie Gem"
