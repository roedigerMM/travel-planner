DEMO_DESTINATIONS = {
    "BER": [
        {
            "destination_iata": "LIS",
            "price": "189.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-01",
            "raw_json": {"source": "demo", "origin": "BER", "destination": "LIS"},
        },
        {
            "destination_iata": "ATH",
            "price": "209.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-03",
            "raw_json": {"source": "demo", "origin": "BER", "destination": "ATH"},
        },
        {
            "destination_iata": "BCN",
            "price": "155.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-05",
            "raw_json": {"source": "demo", "origin": "BER", "destination": "BCN"},
        },
    ],
    "MUC": [
        {
            "destination_iata": "LIS",
            "price": "219.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-02",
            "raw_json": {"source": "demo", "origin": "MUC", "destination": "LIS"},
        },
        {
            "destination_iata": "NAP",
            "price": "176.00",
            "currency_code": "EUR",
            "departure_date": "2026-07-04",
            "raw_json": {"source": "demo", "origin": "MUC", "destination": "NAP"},
        },
    ],
    "BOS": [
        {
            "destination_iata": "YUL",
            "price": "142.00",
            "currency_code": "USD",
            "departure_date": "2026-07-01",
            "raw_json": {"source": "demo", "origin": "BOS", "destination": "YUL"},
        },
        {
            "destination_iata": "DUB",
            "price": "488.00",
            "currency_code": "USD",
            "departure_date": "2026-07-06",
            "raw_json": {"source": "demo", "origin": "BOS", "destination": "DUB"},
        },
    ],
}


def get_demo_destinations(origin_iata: str) -> list[dict]:
    return [dict(item) for item in DEMO_DESTINATIONS.get(origin_iata, [])]
