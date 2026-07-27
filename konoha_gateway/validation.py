from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any


SENSOR_STATUSES = {"ok", "warning", "error", "offline"}

TIMESTAMP_PATTERN = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|([+-])(\d{2}):(\d{2}))$"
)

REQUIRED_FIELDS = {
    "device_id",
    "timestamp",
    "soil_moisture_raw",
    "soil_moisture_percent",
    "temperature_c",
    "humidity_percent",
    "light_lux",
    "sensor_status",
}

OPTIONAL_FIELDS = {"battery_or_power_status", "notes"}

READING_FIELDS = (
    "device_id",
    "timestamp",
    "soil_moisture_raw",
    "soil_moisture_percent",
    "temperature_c",
    "humidity_percent",
    "light_lux",
    "sensor_status",
    "battery_or_power_status",
    "notes",
)


def validate_reading(value: Any) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    if not isinstance(value, dict):
        return None, [{"field": "body", "message": "Request body must be a JSON object."}]

    errors: list[dict[str, str]] = []
    missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in value)

    for field in missing_fields:
        errors.append({"field": field, "message": "Field is required."})

    device_id = value.get("device_id")
    timestamp = value.get("timestamp")
    soil_moisture_raw = value.get("soil_moisture_raw")
    soil_moisture_percent = value.get("soil_moisture_percent")
    temperature_c = value.get("temperature_c")
    humidity_percent = value.get("humidity_percent")
    light_lux = value.get("light_lux")
    sensor_status = value.get("sensor_status")
    battery_or_power_status = value.get("battery_or_power_status")
    notes = value.get("notes")

    if "device_id" in value and not _is_non_empty_string(device_id):
        errors.append({"field": "device_id", "message": "Must be a non-empty string."})

    if "timestamp" in value and (
        not isinstance(timestamp, str) or not _is_valid_iso_timestamp(timestamp)
    ):
        errors.append(
            {
                "field": "timestamp",
                "message": "Must be a valid ISO timestamp ending in Z or a timezone offset.",
            }
        )

    if "soil_moisture_raw" in value and not _is_integer(soil_moisture_raw):
        errors.append({"field": "soil_moisture_raw", "message": "Must be an integer."})

    if "soil_moisture_percent" in value and not _is_number_in_range(
        soil_moisture_percent, 0, 100
    ):
        errors.append(
            {"field": "soil_moisture_percent", "message": "Must be a number from 0 to 100."}
        )

    if "temperature_c" in value and not _is_finite_number(temperature_c):
        errors.append({"field": "temperature_c", "message": "Must be a finite number."})

    if "humidity_percent" in value and not _is_number_in_range(humidity_percent, 0, 100):
        errors.append(
            {"field": "humidity_percent", "message": "Must be a number from 0 to 100."}
        )

    if "light_lux" in value and not (
        _is_finite_number(light_lux) and float(light_lux) >= 0
    ):
        errors.append(
            {"field": "light_lux", "message": "Must be a number greater than or equal to 0."}
        )

    if "sensor_status" in value and (
        not isinstance(sensor_status, str) or sensor_status not in SENSOR_STATUSES
    ):
        errors.append(
            {
                "field": "sensor_status",
                "message": "Must be one of: ok, warning, error, offline.",
            }
        )

    if "battery_or_power_status" in value and not isinstance(battery_or_power_status, str):
        errors.append(
            {
                "field": "battery_or_power_status",
                "message": "Must be a string when provided.",
            }
        )

    if "notes" in value and not isinstance(notes, str):
        errors.append({"field": "notes", "message": "Must be a string when provided."})

    if errors:
        return None, errors

    reading = {field: value[field] for field in READING_FIELDS if field in value}
    return reading, []


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_number_in_range(value: Any, minimum: float, maximum: float) -> bool:
    return _is_finite_number(value) and minimum <= float(value) <= maximum


def _is_valid_iso_timestamp(value: str) -> bool:
    match = TIMESTAMP_PATTERN.fullmatch(value)

    if not match:
        return False

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False

    offset_hour = match.group(8)
    offset_minute = match.group(9)

    if offset_hour is not None and (int(offset_hour) > 23 or int(offset_minute) > 59):
        return False

    return True
