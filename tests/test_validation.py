import unittest

from konoha_gateway.validation import validate_reading


VALID_READING = {
    "device_id": "konoha-esp32-01",
    "timestamp": "2026-06-29T12:00:00Z",
    "soil_moisture_raw": 1840,
    "soil_moisture_percent": 47.5,
    "temperature_c": 24.8,
    "humidity_percent": 58.2,
    "light_lux": 725.0,
    "sensor_status": "ok",
    "battery_or_power_status": "usb",
    "notes": "local gateway smoke test",
}


class ValidateReadingTest(unittest.TestCase):
    def test_accepts_valid_reading(self):
        reading, errors = validate_reading(VALID_READING)

        self.assertEqual(errors, [])
        self.assertEqual(reading, VALID_READING)

    def test_allows_optional_fields_to_be_absent(self):
        payload = dict(VALID_READING)
        payload.pop("battery_or_power_status")
        payload.pop("notes")

        reading, errors = validate_reading(payload)

        self.assertEqual(errors, [])
        self.assertNotIn("battery_or_power_status", reading)
        self.assertNotIn("notes", reading)

    def test_rejects_missing_required_field(self):
        payload = dict(VALID_READING)
        payload.pop("device_id")

        reading, errors = validate_reading(payload)

        self.assertIsNone(reading)
        self.assertIn({"field": "device_id", "message": "Field is required."}, errors)

    def test_rejects_invalid_timestamp(self):
        payload = dict(VALID_READING, timestamp="2026-06-29 12:00:00")

        reading, errors = validate_reading(payload)

        self.assertIsNone(reading)
        self.assertEqual(errors[0]["field"], "timestamp")

    def test_rejects_out_of_range_percentages(self):
        payload = dict(VALID_READING, soil_moisture_percent=101)

        reading, errors = validate_reading(payload)

        self.assertIsNone(reading)
        self.assertEqual(errors[0]["field"], "soil_moisture_percent")

    def test_rejects_invalid_sensor_status(self):
        payload = dict(VALID_READING, sensor_status="unknown")

        reading, errors = validate_reading(payload)

        self.assertIsNone(reading)
        self.assertEqual(errors[0]["field"], "sensor_status")

    def test_rejects_boolean_numbers(self):
        payload = dict(VALID_READING, soil_moisture_raw=True)

        reading, errors = validate_reading(payload)

        self.assertIsNone(reading)
        self.assertEqual(errors[0]["field"], "soil_moisture_raw")


if __name__ == "__main__":
    unittest.main()
