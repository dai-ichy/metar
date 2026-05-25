"""Unit tests for the METAR decoder (app.py).

Each test uses a realistic mock METAR string and asserts that the parsed
output matches the expected plain-English interpretation.
"""

import unittest
from app import decode_weather_token, parse_metar


class TestDecodeWeatherToken(unittest.TestCase):
    """Tests for decode_weather_token — isolated from the full parser."""

    def test_plain_rain(self):
        self.assertEqual(decode_weather_token('RA'), 'rain')

    def test_light_rain(self):
        self.assertEqual(decode_weather_token('-RA'), 'light rain')

    def test_heavy_thunderstorm_rain(self):
        self.assertEqual(decode_weather_token('+TSRA'), 'heavy thunderstorm rain')

    def test_nearby_fog(self):
        self.assertEqual(decode_weather_token('VCFG'), 'nearby fog')

    def test_snow(self):
        self.assertEqual(decode_weather_token('SN'), 'snow')

    def test_freezing_rain(self):
        self.assertEqual(decode_weather_token('FZRA'), 'freezing rain')

    def test_mixed_rain_snow(self):
        self.assertEqual(decode_weather_token('RASN'), 'rain snow')

    def test_light_drizzle(self):
        self.assertEqual(decode_weather_token('-DZ'), 'light drizzle')

    def test_heavy_snow(self):
        self.assertEqual(decode_weather_token('+SN'), 'heavy snow')


class TestParseMetarClearDay(unittest.TestCase):
    """KHIO: clear-ish day, light westerly wind, few clouds."""

    def setUp(self):
        self.result = parse_metar('KHIO 211553Z 27008KT 10SM FEW050 18/07 A3002')

    def test_station(self):
        self.assertEqual(self.result['station'], 'KHIO')

    def test_time(self):
        self.assertEqual(self.result['time_utc'], '15:53 UTC (day 21)')

    def test_wind(self):
        self.assertEqual(self.result['wind'], '9 mph from the West')

    def test_visibility(self):
        self.assertEqual(self.result['visibility'], '10+ miles')

    def test_sky_layer(self):
        self.assertEqual(len(self.result['sky_layers']), 1)
        self.assertEqual(self.result['sky_layers'][0]['coverage'], 'A few clouds')
        self.assertEqual(self.result['sky_layers'][0]['height_ft'], 5000)

    def test_temperature(self):
        self.assertEqual(self.result['temperature_c'], 18)
        self.assertEqual(self.result['temperature_f'], 64)

    def test_dewpoint(self):
        self.assertEqual(self.result['dewpoint_c'], 7)
        self.assertEqual(self.result['dewpoint_f'], 45)

    def test_altimeter(self):
        self.assertEqual(self.result['altimeter'], '30.02 inHg')

    def test_icon(self):
        self.assertEqual(self.result['icon'], '🌤️')


class TestParseMetarRain(unittest.TestCase):
    """KJFK: light rain, broken and overcast layers."""

    def setUp(self):
        self.result = parse_metar('KJFK 211553Z 09012KT 5SM -RA BKN025 OVC060 15/13 A2985')

    def test_weather_phenomena(self):
        self.assertEqual(self.result['weather'], ['light rain'])

    def test_wind(self):
        self.assertEqual(self.result['wind'], '14 mph from the East')

    def test_visibility(self):
        self.assertEqual(self.result['visibility'], '5 statute miles')

    def test_sky_layers(self):
        self.assertEqual(len(self.result['sky_layers']), 2)
        self.assertEqual(self.result['sky_layers'][0]['coverage'], 'Mostly cloudy')
        self.assertEqual(self.result['sky_layers'][1]['coverage'], 'Overcast')

    def test_icon(self):
        self.assertEqual(self.result['icon'], '🌧️')

    def test_overall_contains_rain(self):
        self.assertIn('rain', self.result['overall'].lower())


class TestParseMetarThunderstorm(unittest.TestCase):
    """KORD: heavy thunderstorm with rain, gusting wind, cumulonimbus cloud."""

    def setUp(self):
        self.result = parse_metar('KORD 211553Z 19018G28KT 3SM +TSRA SCT030CB OVC060 22/19 A2971')

    def test_weather_phenomena(self):
        self.assertIn('heavy thunderstorm rain', self.result['weather'])

    def test_wind_with_gust(self):
        self.assertIn('21 mph', self.result['wind'])
        self.assertIn('gusting to 32 mph', self.result['wind'])

    def test_cumulonimbus_note(self):
        cb_layer = self.result['sky_layers'][0]
        self.assertIn('cumulonimbus', cb_layer.get('note', ''))

    def test_icon(self):
        self.assertEqual(self.result['icon'], '⛈️')

    def test_overall_contains_thunderstorm(self):
        self.assertIn('thunderstorm', self.result['overall'].lower())


class TestParseMetarSnow(unittest.TestCase):
    """KDEN: snow, below-freezing temperature using M prefix."""

    def setUp(self):
        self.result = parse_metar('KDEN 211553Z 01015KT 2SM SN OVC015 M02/M05 A2995')

    def test_weather_phenomena(self):
        self.assertEqual(self.result['weather'], ['snow'])

    def test_negative_temperature(self):
        self.assertEqual(self.result['temperature_c'], -2)
        self.assertEqual(self.result['temperature_f'], 28)

    def test_negative_dewpoint(self):
        self.assertEqual(self.result['dewpoint_c'], -5)
        self.assertEqual(self.result['dewpoint_f'], 23)

    def test_icon(self):
        self.assertEqual(self.result['icon'], '🌨️')

    def test_overall_contains_snow(self):
        self.assertIn('snow', self.result['overall'].lower())


class TestParseMetarFog(unittest.TestCase):
    """KSFO: dense fog, very low visibility as fractional SM."""

    def setUp(self):
        self.result = parse_metar('KSFO 211553Z 28006KT 1/4SM FG OVC002 12/11 A3012')

    def test_weather_phenomena(self):
        self.assertEqual(self.result['weather'], ['fog'])

    def test_low_visibility(self):
        self.assertIn('1/4', self.result['visibility'])

    def test_icon(self):
        self.assertEqual(self.result['icon'], '🌫️')

    def test_overall_contains_fog(self):
        self.assertIn('fog', self.result['overall'].lower())


class TestParseMetarCalmWind(unittest.TestCase):
    """KLAX: calm wind reported as 00000KT."""

    def setUp(self):
        self.result = parse_metar('KLAX 211553Z 00000KT 10SM SKC 24/12 A2998')

    def test_calm_wind_text(self):
        self.assertEqual(self.result['wind'], 'Calm — no wind')

    def test_calm_wind_flag(self):
        self.assertTrue(self.result['wind_calm'])

    def test_clear_sky(self):
        self.assertEqual(len(self.result['sky_layers']), 1)
        self.assertEqual(self.result['sky_layers'][0]['coverage'], 'Clear')

    def test_icon(self):
        self.assertEqual(self.result['icon'], '☀️')


class TestParseMetarCavok(unittest.TestCase):
    """EGLL: European station with CAVOK and Q-format altimeter."""

    def setUp(self):
        self.result = parse_metar('EGLL 211553Z 28010KT CAVOK 21/10 Q1015')

    def test_cavok_visibility(self):
        self.assertEqual(self.result['visibility'], '10+ miles — ceiling and visibility OK')

    def test_metric_altimeter(self):
        self.assertIn('1015 hPa', self.result['altimeter'])
        self.assertIn('inHg', self.result['altimeter'])

    def test_no_weather_phenomena(self):
        self.assertEqual(self.result['weather'], [])

    def test_icon(self):
        self.assertEqual(self.result['icon'], '☀️')


if __name__ == '__main__':
    unittest.main()
