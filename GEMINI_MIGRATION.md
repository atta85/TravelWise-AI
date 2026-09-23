# TravelWise AI — Gemini Migration

## AI Research Engine Update

TravelWise AI originally used Groq Compound as its AI-powered web research and travel-planning engine.

Groq officially decommissioned the `groq/compound` and `groq/compound-mini` model IDs on 21 September 2026. Requests to those model IDs are no longer supported.

TravelWise AI has therefore been migrated to:

**Google Gemini 2.5 Flash + Google Search grounding**

The rest of the TravelWise AI architecture remains unchanged.

---

## What Changed

### Previous AI layer

- Groq Compound
- Groq Python SDK
- Groq Web Search
- Groq Visit Website

### Current AI layer

- Google Gemini 2.5 Flash
- Google `google-genai` Python SDK
- Google Search grounding

Gemini uses Google Search grounding to obtain current web information when appropriate and synthesize that information into the TravelWise travel brief.

---

## What Remained Unchanged

The following components of TravelWise AI were retained:

- Streamlit user interface
- Multi-stop trip input
- Starting city and destination
- Intermediate stops
- Return/end city
- Travel dates and times
- Traveler composition
- Children and elderly traveler information
- Accessibility-support information
- Private-vehicle routing
- OpenStreetMap data
- OSRM route optimization
- Open-Meteo geocoding
- Open-Meteo weather forecasts
- Folium interactive route map
- Weather-risk calculation
- Travel research prompt structure
- Day-by-day itinerary generation
- Attraction research
- Hotel/stay research
- Local issue research
- Family and accessibility guidance
- Booking and verification checklist
- Streamlit Community Cloud deployment

The migration therefore changes the AI research provider rather than redesigning the TravelWise application.

---

## Streamlit Secret

The Gemini API key must be stored as a Streamlit Secret.

In Streamlit Community Cloud:

1. Open the TravelWise AI application.
2. Open the application settings.
3. Open **Secrets**.
4. Add:

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
