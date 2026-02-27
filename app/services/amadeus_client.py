import time
import requests


class AmadeusClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_expires_at = 0

    def _get_access_token(self) -> str:
        now = int(time.time())
        if self._token and now < self._token_expires_at:
            return self._token

        url = f"{self.base_url}/v1/security/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        resp = requests.post(url, headers=headers, data=data, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        self._token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 0))
        self._token_expires_at = now + max(0, expires_in - 30)
        return self._token

    def _auth_headers(self) -> dict:
        token = self._get_access_token()
        return {"Authorization": f"Bearer {token}"}

    # NEW: airport & city search
    def search_locations(self, keyword: str, subtypes=None, limit: int = 5) -> list[dict]:
        """
        Call Airport & City Search API to suggest airports/cities for autocomplete.

        subtypes: list like ["AIRPORT","CITY"]
        """
        if subtypes is None:
            subtypes = ["AIRPORT", "CITY"]

        params = {
            "keyword": keyword,
            "subType": ",".join(subtypes),
            "page[limit]": limit,
        }
        url = f"{self.base_url}/v1/reference-data/locations"
        headers = self._auth_headers()

        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        # The spec shows data[].subType, data[].iataCode, data[].name, etc. [web:117][web:112]
        items = []
        for item in payload.get("data", []):
            items.append(
                {
                    "sub_type": item.get("subType"),
                    "name": item.get("name"),
                    "iata": item.get("iataCode"),
                    "city_name": (item.get("address") or {}).get("cityName"),
                    "city_code": (item.get("address") or {}).get("cityCode"),
                    "country_code": (item.get("address") or {}).get("countryCode"),
                }
            )
        return items
