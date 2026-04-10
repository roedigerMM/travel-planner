import time

import requests

from .travel_data_provider import TravelDataProvider


class AmadeusClient(TravelDataProvider):
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
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Amadeus credentials are not configured.")

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

    @staticmethod
    def format_error(exc: Exception) -> str:
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                payload = exc.response.json()
                errors = payload.get("errors") or []
                if errors:
                    first = errors[0]
                    code = first.get("code")
                    title = first.get("title")
                    detail = first.get("detail")
                    parts = [part for part in (code, title, detail) if part]
                    if parts:
                        return " | ".join(str(part) for part in parts)
            except ValueError:
                pass
        return str(exc)

    def search_locations(self, keyword: str, subtypes=None, limit: int = 5) -> list[dict]:
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

    def search_destinations(
        self,
        origin_iata: str,
        travel_month: str | None = None,
        duration_days: int | None = None,
        max_price: float | None = None,
        currency_code: str | None = None,
        non_stop: bool | None = None,
        origin_sky_id: str | None = None,
        origin_entity_id: str | None = None,
    ) -> list[dict]:
        params = {"origin": origin_iata}
        if travel_month:
            params["departureDate"] = f"{travel_month}-01"
        if max_price is not None:
            params["maxPrice"] = max_price
        if currency_code:
            params["currency"] = currency_code
        if non_stop is not None:
            params["nonStop"] = str(non_stop).lower()

        url = f"{self.base_url}/v1/shopping/flight-destinations"
        resp = requests.get(url, headers=self._auth_headers(), params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        destinations = []
        for item in payload.get("data", []):
            price = item.get("price") or {}
            departure_value = item.get("departureDate") or item.get("departureDates")
            if isinstance(departure_value, list):
                departure_date = departure_value[0] if departure_value else None
            else:
                departure_date = departure_value

            destination_iata = item.get("destination")
            if not destination_iata:
                continue

            destinations.append(
                {
                    "destination_iata": destination_iata,
                    "price": price.get("total"),
                    "currency_code": price.get("currency") or currency_code,
                    "departure_date": departure_date,
                    "raw_json": item,
                }
            )

        return destinations
