import requests

WEATHER_CODES = {
    0: "cielo sereno, soleggiato",
    1: "prevalentemente sereno",
    2: "parzialmente nuvoloso",
    3: "coperto, cielo nuvoloso",
    45: "presenza di nebbia",
    48: "nebbia con deposito di galaverna",
    51: "pioggerella leggera",
    53: "pioggerella moderata",
    55: "pioggerella fitta",
    61: "pioggia debole",
    63: "pioggia moderata",
    65: "pioggia forte",
    71: "nevicata debole",
    73: "nevicata moderata",
    75: "nevicata forte",
    80: "acquazzoni deboli",
    81: "acquazzoni moderati",
    82: "acquazzoni violenti",
    95: "temporale debole o moderato",
    96: "temporale con grandine debole",
    99: "temporale con forte grandine",
}

WEATHER_CITIES = {
    "nord": {"name": "Milano", "lat": 45.4642, "lon": 9.1900},
    "centro": {"name": "Roma", "lat": 41.8902, "lon": 12.4922},
    "sud": {"name": "Napoli", "lat": 40.8518, "lon": 14.2681},
}


def fetch_weather():
    results = {}
    for key, city in WEATHER_CITIES.items():
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={city['lat']}&longitude={city['lon']}&current_weather=true"
        )
        try:
            response = requests.get(url, timeout=5)
            data = response.json()
            current = data.get("current_weather", {})
            code = current.get("weathercode", 0)
            desc = WEATHER_CODES.get(code, "variabile")
            results[key] = {
                "citta": city["name"],
                "temperatura": current.get("temperature"),
                "vento": current.get("windspeed"),
                "condizioni": desc,
            }
        except Exception as e:
            print(f"⚠️ Errore recupero meteo per {city['name']}: {e}")
            results[key] = {"citta": city["name"], "condizioni": "dati temporaneamente non disponibili"}

    summary_text = (
        f"Nord Italia - Milano: {results['nord']['condizioni']}, temperatura {results['nord'].get('temperatura', 'N/D')}°C. "
        f"Centro Italia - Roma: {results['centro']['condizioni']}, temperatura {results['centro'].get('temperatura', 'N/D')}°C. "
        f"Sud e Isole - Napoli: {results['sud']['condizioni']}, temperatura {results['sud'].get('temperatura', 'N/D')}°C."
    )

    return {
        "title": "Meteo Italia",
        "summary": summary_text,
        "link": "https://open-meteo.com",
        "source": "meteo",
    }

