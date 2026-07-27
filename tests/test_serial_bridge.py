from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import MagicMock, patch

from konoha_gateway.serial_bridge import (
    complete_reading,
    parse_sensor_line,
    post_gateway_reading,
)


SENSOR_READING = {
    "soil_moisture_raw": 2500,
    "soil_moisture_percent": 67.4,
    "temperature_c": 24.8,
    "humidity_percent": 58.2,
    "light_lux": 725.0,
}


class ParseSensorLineTest(unittest.TestCase):
    def test_parses_sensor_json_object(self):
        raw_line = json.dumps(SENSOR_READING).encode("utf-8") + b"\n"

        self.assertEqual(parse_sensor_line(raw_line), SENSOR_READING)

    def test_ignores_non_json_diagnostic_line(self):
        self.assertIsNone(
            parse_sensor_line(b"sht31_status=error reason=read_failed\n")
        )

    def test_ignores_json_that_is_not_an_object(self):
        self.assertIsNone(parse_sensor_line(b"[1,2,3]\n"))


class CompleteReadingTest(unittest.TestCase):
    def test_adds_trusted_gateway_fields(self):
        sensor_reading = dict(
            SENSOR_READING,
            device_id="untrusted-device",
            timestamp="2000-01-01T00:00:00Z",
            sensor_status="error",
        )
        measured_at = datetime(
            2026,
            7,
            28,
            12,
            34,
            56,
            789000,
            tzinfo=timezone(timedelta(hours=9)),
        )

        reading = complete_reading(sensor_reading, "konoha-esp32-01", measured_at)

        self.assertEqual(reading["device_id"], "konoha-esp32-01")
        self.assertEqual(reading["timestamp"], "2026-07-28T03:34:56.789Z")
        self.assertEqual(reading["sensor_status"], "ok")
        self.assertEqual(reading["temperature_c"], 24.8)


class PostGatewayReadingTest(unittest.TestCase):
    @patch("konoha_gateway.serial_bridge.urllib_request.urlopen")
    def test_posts_compact_json_to_gateway(self, urlopen):
        response = MagicMock()
        response.status = 201
        response.read.return_value = b'{"status":"logged"}'
        urlopen.return_value.__enter__.return_value = response

        status, response_body = post_gateway_reading(
            SENSOR_READING,
            "http://127.0.0.1:8080/readings",
        )

        self.assertEqual(status, 201)
        self.assertEqual(response_body, '{"status":"logged"}')
        http_request = urlopen.call_args.args[0]
        self.assertEqual(http_request.full_url, "http://127.0.0.1:8080/readings")
        self.assertEqual(http_request.method, "POST")
        self.assertEqual(http_request.headers["Content-type"], "application/json")
        self.assertEqual(json.loads(http_request.data), SENSOR_READING)


if __name__ == "__main__":
    unittest.main()
