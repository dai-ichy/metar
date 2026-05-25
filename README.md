# ✈️ METAR Reader

A Flask web app that translates raw METAR aviation weather reports into plain English. Enter any ICAO airport code and get an instant, human-readable weather summary with temperature, wind, visibility, sky conditions, and more.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![Flask](https://img.shields.io/badge/Flask-3.0%2B-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

## Features

- **Live data** — fetches current METARs directly from [aviationweather.gov](https://aviationweather.gov)
- **Full METAR decoding** — wind (including gusts and variable direction), visibility, present weather phenomena, sky layers with cloud types (CB, TCU), temperature, dewpoint, and altimeter
- **Unit conversions** — knots → mph, Celsius → Fahrenheit, meters → miles, hPa → inHg
- **Plain-English summary** — one-line overall condition with temperature feel (freezing / cold / cool / mild / warm / hot)
- **Weather icons** — emoji icon selected by condition priority (thunderstorm > snow > rain > fog > cloud cover > clear)
- **Raw METAR toggle** — expand to see the original string at any time
- **Responsive dark UI** — works on desktop and mobile

## Requirements

- Python 3.9 or newer
- pip

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/metar-app.git
cd metar-app

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

## Running the app

```bash
python app.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

By default the app listens on all interfaces (`0.0.0.0`) on port 5000. To change this, edit the `app.run(...)` call at the bottom of `app.py`.

## Usage

1. Enter an ICAO airport code in the search box (e.g. `KJFK`, `EGLL`, `RJTT`).
2. Click **Get Weather**.
3. The decoded report appears with a summary card and detail grid.
4. Click **Show raw METAR** to see the original string.

> **ICAO vs IATA codes** — Most airports have a 4-letter ICAO code (e.g. `KLAX`). Some US airports are commonly known by their 3-letter IATA code (e.g. `LAX`); the app accepts both, but ICAO codes are preferred and more reliable.

## Project structure

```
metar-app/
├── app.py               # Flask app and METAR parser
├── requirements.txt     # Python dependencies
└── templates/
    └── index.html       # Jinja2 template with embedded CSS and JS
```

## Data source

Weather data is fetched from the [Aviation Weather Center API](https://aviationweather.gov/api/data/metar) operated by NOAA. No API key is required.

## License

MIT
