"""
Flask web app that fetches live METAR data from aviationweather.gov and
decodes it into plain-English weather reports.
"""

from flask import Flask, render_template, request
import requests
import re

app = Flask(__name__)


def wind_direction_name(degrees):
    """Convert a wind direction in degrees to a compass direction name.

    Args:
        degrees: Integer wind direction (0–360).

    Returns:
        A string such as 'North', 'Southwest', 'East-Northeast', etc.
    """
    dirs = [
        (11, 'North'), (34, 'North-Northeast'), (56, 'Northeast'),
        (79, 'East-Northeast'), (101, 'East'), (124, 'East-Southeast'),
        (146, 'Southeast'), (169, 'South-Southeast'), (191, 'South'),
        (214, 'South-Southwest'), (236, 'Southwest'), (259, 'West-Southwest'),
        (281, 'West'), (304, 'West-Northwest'), (326, 'Northwest'),
        (349, 'North-Northwest'), (360, 'North'),
    ]
    for threshold, name in dirs:
        if degrees <= threshold:
            return name
    return 'North'


def c_to_f(c):
    """Convert Celsius to Fahrenheit, rounded to the nearest integer."""
    return round(c * 9 / 5 + 32)


def knots_to_mph(kt):
    """Convert knots to miles per hour, rounded to the nearest integer."""
    return round(kt * 1.15078)


# Human-readable labels for METAR present-weather codes (WMO Table 4678).
WEATHER_DESC = {
    'DZ': 'drizzle', 'RA': 'rain', 'SN': 'snow', 'SG': 'snow grains',
    'IC': 'ice crystals', 'PL': 'ice pellets', 'GR': 'hail',
    'GS': 'small hail', 'UP': 'unknown precipitation',
    'BR': 'mist', 'FG': 'fog', 'FU': 'smoke', 'VA': 'volcanic ash',
    'DU': 'dust', 'SA': 'sand', 'HZ': 'haze', 'PY': 'spray',
    'PO': 'dust whirls', 'SQ': 'squalls', 'FC': 'funnel cloud',
    'SS': 'sandstorm', 'DS': 'dust storm',
    'TS': 'thunderstorm', 'SH': 'showers', 'FZ': 'freezing',
    'MI': 'shallow', 'PR': 'partial', 'BC': 'patchy',
    'DR': 'drifting', 'BL': 'blowing',
}

# Sky-coverage labels and a numeric rank used to determine the "worst" layer.
SKY_COVERAGE = {
    'CLR': ('Clear', 0),
    'SKC': ('Clear', 0),
    'NSC': ('No significant clouds', 0),
    'NCD': ('No clouds detected', 0),
    'FEW': ('A few clouds', 1),
    'SCT': ('Scattered clouds', 2),
    'BKN': ('Mostly cloudy', 3),
    'OVC': ('Overcast', 4),
    'VV':  ('Sky obscured', 4),
}


def decode_weather_token(token):
    """Decode a single METAR present-weather token into plain English.

    Handles intensity prefixes (-, +, VC) and all two-letter phenomenon codes
    defined in WEATHER_DESC.

    Args:
        token: A METAR weather token such as '-RA', '+TSRA', or 'VCFG'.

    Returns:
        A human-readable string (e.g. 'light rain', 'heavy thunderstorm rain'),
        or None if no recognisable codes are found.
    """
    intensity = ''
    rest = token
    if rest.startswith('VC'):
        intensity = 'nearby '
        rest = rest[2:]
    elif rest.startswith('-'):
        intensity = 'light '
        rest = rest[1:]
    elif rest.startswith('+'):
        intensity = 'heavy '
        rest = rest[1:]

    parts = []
    i = 0
    while i < len(rest):
        matched = False
        for code in list(WEATHER_DESC.keys()):
            if rest[i:].startswith(code):
                parts.append(WEATHER_DESC[code])
                i += len(code)
                matched = True
                break
        if not matched:
            i += 1

    return (intensity + ' '.join(parts)).strip() if parts else None


# Matches valid present-weather tokens so non-weather tokens are not mistaken
# for weather phenomena during sequential parsing.
WEATHER_TOKEN_RE = re.compile(
    r'^([-+]|VC)?(MI|PR|BC|DR|BL|SH|TS|FZ)?'
    r'(DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS|TS)+'
    r'(CB|TCU)?$'
)

SKY_TOKEN_RE = re.compile(r'^(VV|CLR|SKC|NSC|NCD|FEW|SCT|BKN|OVC)(\d{3})?(CB|TCU)?$')


def parse_metar(raw):
    """Parse a raw METAR string into a structured dictionary.

    Processes each field in order — station, timestamp, wind, visibility,
    runway visual range (skipped), present weather, sky conditions,
    temperature/dewpoint, and altimeter — then derives a plain-English
    summary and an appropriate weather icon.

    Args:
        raw: The raw METAR string exactly as returned by the data source,
             e.g. 'KHIO 211553Z 27008KT 10SM FEW050 18/07 A3002'.

    Returns:
        A dict with keys: raw, station, time_utc, wind, wind_calm,
        visibility, weather (list), sky_layers (list), sky_summary,
        temperature_c, temperature_f, dewpoint_c, dewpoint_f,
        altimeter, icon, overall.
    """
    tokens = raw.split()
    result = {
        'raw': raw,
        'station': '',
        'time_utc': '',
        'wind': '',
        'wind_calm': False,
        'visibility': '',
        'weather': [],
        'sky_layers': [],
        'sky_summary': '',
        'temperature_c': None,
        'temperature_f': None,
        'dewpoint_c': None,
        'dewpoint_f': None,
        'altimeter': '',
        'icon': '🌡️',
        'overall': '',
    }

    if not tokens:
        return result

    idx = 0

    # Optional METAR/SPECI prefix
    if tokens[idx] in ('METAR', 'SPECI'):
        idx += 1

    # Station
    if idx < len(tokens):
        result['station'] = tokens[idx]
        idx += 1

    # Date/time (DDHHmmZ)
    if idx < len(tokens) and re.match(r'^\d{6}Z$', tokens[idx]):
        dt = tokens[idx]
        result['time_utc'] = f"{dt[2:4]}:{dt[4:6]} UTC (day {int(dt[:2])})"
        idx += 1

    # AUTO / COR modifier — informational only, no data to extract
    while idx < len(tokens) and tokens[idx] in ('AUTO', 'COR', 'NIL'):
        idx += 1

    # Wind (e.g. 27008KT, VRB03KT, 24015G25KT)
    if idx < len(tokens):
        m = re.match(r'^(VRB|\d{3})(\d{2,3})(G(\d{2,3}))?(KT|MPS|KMH)$', tokens[idx])
        if m:
            direction, speed_raw, _, gust_raw, unit = (
                m.group(1), int(m.group(2)), m.group(3), m.group(4), m.group(5)
            )
            factor = {'KT': knots_to_mph, 'MPS': lambda x: round(x * 2.237), 'KMH': lambda x: round(x * 0.621)}[unit]
            speed_mph = factor(speed_raw)
            gust_mph = factor(int(gust_raw)) if gust_raw else None

            if speed_raw == 0:
                result['wind'] = 'Calm — no wind'
                result['wind_calm'] = True
            elif direction == 'VRB':
                result['wind'] = f"Variable direction, {speed_mph} mph"
                if gust_mph:
                    result['wind'] += f", gusting to {gust_mph} mph"
            else:
                dir_name = wind_direction_name(int(direction))
                result['wind'] = f"{speed_mph} mph from the {dir_name}"
                if gust_mph:
                    result['wind'] += f", gusting to {gust_mph} mph"
            idx += 1

    # Variable wind range (e.g. 270V360) — direction only, already captured above
    if idx < len(tokens) and re.match(r'^\d{3}V\d{3}$', tokens[idx]):
        idx += 1

    # Visibility — handles SM fractions, CAVOK, and metric (4-digit) formats
    if idx < len(tokens):
        tok = tokens[idx]
        # Whole-number prefix before a fractional SM token (e.g. "1 1/2SM")
        if re.match(r'^\d+$', tok) and idx + 1 < len(tokens) and re.match(r'^\d+/\d+SM$', tokens[idx + 1]):
            result['visibility'] = f"{tok} {tokens[idx+1].replace('SM', '')} statute miles"
            idx += 2
        elif tok == 'CAVOK':
            result['visibility'] = '10+ miles — ceiling and visibility OK'
            idx += 1
        elif re.match(r'^\d+SM$', tok):
            miles = int(tok[:-2])
            result['visibility'] = '10+ miles' if miles >= 10 else f"{miles} statute {'mile' if miles == 1 else 'miles'}"
            idx += 1
        elif re.match(r'^\d+/\d+SM$', tok):
            result['visibility'] = tok.replace('SM', '') + ' statute miles (very low)'
            idx += 1
        elif re.match(r'^\d{4}$', tok):
            meters = int(tok)
            result['visibility'] = ('10+ km' if meters >= 9999 else f"{meters} meters ({round(meters / 1609.34, 1)} miles)")
            idx += 1

    # RVR (Runway Visual Range) — skip; useful only to pilots, not end users
    while idx < len(tokens) and re.match(r'^R\d+[LCR]?/', tokens[idx]):
        idx += 1

    # Present weather phenomena (one or more tokens)
    while idx < len(tokens) and WEATHER_TOKEN_RE.match(tokens[idx]):
        desc = decode_weather_token(tokens[idx])
        if desc:
            result['weather'].append(desc)
        idx += 1

    # Sky conditions (one layer per token, e.g. FEW018, BKN045CB)
    while idx < len(tokens):
        m = SKY_TOKEN_RE.match(tokens[idx])
        if not m:
            break
        coverage, height_code, cloud_type = m.group(1), m.group(2), m.group(3)
        label, rank = SKY_COVERAGE.get(coverage, (coverage, 0))
        layer = {'coverage': label, 'rank': rank}
        if height_code:
            layer['height_ft'] = int(height_code) * 100  # hundreds of feet
        if cloud_type == 'CB':
            layer['note'] = 'cumulonimbus (thunderstorm cloud)'
        elif cloud_type == 'TCU':
            layer['note'] = 'towering cumulus'
        result['sky_layers'].append(layer)
        idx += 1

    # Temperature / dewpoint (e.g. 18/07, M02/M05)
    if idx < len(tokens) and re.match(r'^M?\d+/M?\d*$', tokens[idx]):
        parts = tokens[idx].split('/')
        tc = int(parts[0].replace('M', '-'))
        result['temperature_c'] = tc
        result['temperature_f'] = c_to_f(tc)
        if parts[1]:
            dc = int(parts[1].replace('M', '-'))
            result['dewpoint_c'] = dc
            result['dewpoint_f'] = c_to_f(dc)
        idx += 1

    # Altimeter — A = inches of mercury (US), Q = hectopascals (international)
    if idx < len(tokens):
        m = re.match(r'^A(\d{4})$', tokens[idx])
        if m:
            result['altimeter'] = f"{int(m.group(1)) / 100:.2f} inHg"
            idx += 1
        else:
            m = re.match(r'^Q(\d{4})$', tokens[idx])
            if m:
                hpa = int(m.group(1))
                result['altimeter'] = f"{hpa} hPa ({hpa * 0.02953:.2f} inHg)"
                idx += 1

    # Derive sky summary and choose an icon based on the worst sky layer
    max_rank = max((l['rank'] for l in result['sky_layers']), default=0)
    has_thunder = any('thunderstorm' in w for w in result['weather'])
    has_rain = any(w for w in result['weather'] if any(x in w for x in ('rain', 'drizzle', 'showers')))
    has_snow = any('snow' in w for w in result['weather'])
    has_fog = any('fog' in w for w in result['weather'])

    if result['sky_layers']:
        result['sky_summary'] = '; '.join(
            f"{l['coverage']}" + (f" at {l['height_ft']:,} ft" if 'height_ft' in l else '') +
            (f" ({l['note']})" if 'note' in l else '')
            for l in result['sky_layers']
        )
    else:
        result['sky_summary'] = 'Not reported'

    # Map temperature to a qualitative feel descriptor
    tc = result['temperature_c']
    if tc is not None:
        if tc <= 0:
            temp_feel = 'freezing'
        elif tc <= 10:
            temp_feel = 'cold'
        elif tc <= 18:
            temp_feel = 'cool'
        elif tc <= 24:
            temp_feel = 'mild'
        elif tc <= 30:
            temp_feel = 'warm'
        else:
            temp_feel = 'hot'
    else:
        temp_feel = ''

    # Priority order: thunder > snow > rain > fog > cloud cover > clear
    condition_parts = []
    if has_thunder:
        condition_parts.append('thunderstorms')
        result['icon'] = '⛈️'
    elif has_snow:
        condition_parts.append('snow')
        result['icon'] = '🌨️'
    elif has_rain:
        condition_parts.append('rain')
        result['icon'] = '🌧️'
    elif has_fog:
        condition_parts.append('foggy conditions')
        result['icon'] = '🌫️'
    elif max_rank == 4:
        condition_parts.append('overcast skies')
        result['icon'] = '☁️'
    elif max_rank == 3:
        condition_parts.append('mostly cloudy skies')
        result['icon'] = '🌥️'
    elif max_rank == 2:
        condition_parts.append('partly cloudy skies')
        result['icon'] = '⛅'
    elif max_rank == 1:
        condition_parts.append('mostly clear skies with a few clouds')
        result['icon'] = '🌤️'
    else:
        condition_parts.append('clear skies')
        result['icon'] = '☀️'

    overall = condition_parts[0].capitalize()
    if temp_feel:
        overall += f' and {temp_feel} temperatures'
    if result['temperature_f'] is not None:
        overall += f' ({result["temperature_f"]}°F / {tc}°C)'
    result['overall'] = overall + '.'

    return result


@app.route('/', methods=['GET', 'POST'])
def index():
    """Render the main page and handle METAR lookup form submissions."""
    weather = None
    error = None
    airport_code = ''

    if request.method == 'POST':
        airport_code = request.form.get('airport_code', '').strip().upper()

        if not airport_code:
            error = 'Please enter an airport code.'
        elif not re.match(r'^[A-Z0-9]{3,4}$', airport_code):
            error = 'Please enter a valid ICAO airport code (3–4 letters, e.g. KHIO or JFK).'
        else:
            try:
                url = f'https://aviationweather.gov/api/data/metar?ids={airport_code}'
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                raw = resp.text.strip()
                if not raw:
                    error = f'No METAR data found for {airport_code}. Check the airport code and try again.'
                else:
                    # API may return multiple lines; take first non-empty
                    raw = next((line.strip() for line in raw.splitlines() if line.strip()), '')
                    weather = parse_metar(raw)
            except requests.exceptions.Timeout:
                error = 'The request timed out. Please try again.'
            except requests.exceptions.RequestException as e:
                error = f'Could not fetch weather data: {e}'

    return render_template('index.html', weather=weather, error=error, airport_code=airport_code)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
