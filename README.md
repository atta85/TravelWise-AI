# TravelWise AI — Hackathon MVP

TravelWise AI is a Streamlit travel-planning prototype that combines:

- Open-Meteo geocoding and weather data
- OpenStreetMap/OSRM road routing and stop-order optimization
- Groq Compound for real-time web research
- Streamlit for the user interface and deployment

## 1. What you need

Free accounts/services:

1. GitHub
2. Groq API key
3. Streamlit Community Cloud

Open-Meteo and the public OSRM demo endpoint do not require an API key for this prototype.

## 2. Local setup on Windows

Install Python 3.11 or 3.12.

Open Command Prompt in this folder:

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create:

```text
.streamlit\secrets.toml
```

Put:

```toml
GROQ_API_KEY = "YOUR_KEY"
```

Then run:

```text
streamlit run app.py
```

Your browser should open the local app.

## 3. GitHub

Create a new repository, for example:

```text
travelwise-ai-hackathon
```

Upload:

- app.py
- requirements.txt
- README.md
- .gitignore

DO NOT upload:

- .streamlit/secrets.toml

## 4. Streamlit deployment

Go to Streamlit Community Cloud, connect GitHub, choose the repository and `app.py`,
then deploy.

In the app's Streamlit settings, add the secret:

```toml
GROQ_API_KEY = "YOUR_KEY"
```

Redeploy/re-run the app.

## 5. Important MVP limitations

- Public OSRM routing is a demonstration/public service; it is not guaranteed for production scale.
- Open-Meteo forecast data is near-term. Re-check forecasts before travel.
- Public transport is researched rather than connected to live ticketing.
- Hotels are researched from public web information; this app does not make reservations.
- Prices, ratings, availability, opening hours and local conditions must be verified.
- The "weather-aware" route score is a planning heuristic, not a road-weather sensor.
- Do not collect unnecessary personal or sensitive information.

## 6. Suggested hackathon demo

Use a realistic trip with:
- 2 adults
- 1 child
- 2 intermediate stops
- private vehicle
- departure within the next 7–10 days

Demo in this order:

1. Enter trip
2. Generate plan
3. Show optimized stop order
4. Show map
5. Show weather
6. Show live-researched sights/hotels
7. Show family/accessibility recommendations
8. Explain the architecture and future roadmap

## 7. Future upgrades

- Real hotel/flight booking APIs
- Google/Mapbox or another commercial map provider for production
- Public transport APIs
- Live traffic
- User accounts and saved trips
- PDF itinerary export
- Emergency contacts
- Offline itinerary
- Multi-language support
- Cost estimator
- Carbon/emissions estimator
- Accessibility scoring
- Route alternatives with explicit weather-risk comparison
