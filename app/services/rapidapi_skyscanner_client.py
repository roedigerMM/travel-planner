import requests

from .travel_data_provider import TravelDataProvider


class RapidApiSkyscannerClient(TravelDataProvider):
    def __init__(
        self,
        api_key: str,
        host: str,
        market: str = "DE",
        locale: str = "de-DE",
        timeout: int = 20,
    ):
        self.api_key = api_key
        self.host = host
        self.market = market
        self.locale = locale
        self.timeout = timeout
        self.base_url = f"https://{host}".rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("RapidAPI key is not configured.")
        if not self.host:
            raise RuntimeError("RapidAPI host is not configured.")
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
            "Accept": "application/json",
        }

    @staticmethod
    def _best_iata(item: dict) -> str | None:
        iata = (item.get("iataCode") or "").strip().upper()
        if iata:
            return iata

        sky_id = (item.get("skyId") or "").strip().upper()
        if len(sky_id) == 3 and sky_id.isalpha():
            return sky_id
        return None

    @staticmethod
    def format_error(exc: Exception) -> str:
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            try:
                payload = exc.response.json()
                message = payload.get("message")
                if message:
                    return str(message)
            except ValueError:
                pass
        return str(exc)

    def search_locations(self, keyword: str, subtypes=None, limit: int = 5) -> list[dict]:
        if subtypes is None:
            subtypes = ["AIRPORT", "CITY"]

        params = {
            "query": keyword,
            "market": self.market,
            "locale": self.locale,
        }
        resp = requests.get(
            f"{self.base_url}/flights/searchAirport",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()

        items = []
        for item in payload.get("places", []):
            sub_type = (item.get("placeType") or "").strip().upper()
            if sub_type not in {value.upper() for value in subtypes}:
                continue

            iata = self._best_iata(item)
            if not iata:
                continue

            items.append(
                {
                    "sub_type": sub_type,
                    "name": item.get("name"),
                    "iata": iata,
                    "city_name": item.get("cityName"),
                    "city_code": (item.get("iataCode") or "").strip().upper() or None,
                    "country_code": None,
                    "provider_sky_id": item.get("skyId"),
                    "provider_entity_id": item.get("entityId"),
                }
            )

        return items[:limit]

    def search_destinations(
        self,
        origin_iata: str,
        travel_month: str | None = None,
        duration_days: int | None = None,
        max_price: float | None = None,
        currency_code: str | None = None,
        non_stop: bool | None = None,
    ) -> list[dict]:
        raise NotImplementedError("RapidAPI destination discovery is implemented in a later step.")
