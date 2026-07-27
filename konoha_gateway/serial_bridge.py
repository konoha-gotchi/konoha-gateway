from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import termios
import time
from typing import Any, BinaryIO
from urllib import error as urllib_error
from urllib import request as urllib_request


DEFAULT_DEVICE_ID = "konoha-esp32-01"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:8080/readings"
RECONNECT_DELAY_SECONDS = 2


def parse_sensor_line(raw_line: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(raw_line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    return value if isinstance(value, dict) else None


def complete_reading(
    sensor_reading: dict[str, Any],
    device_id: str,
    measured_at: datetime,
) -> dict[str, Any]:
    reading = dict(sensor_reading)
    reading.update(
        {
            "device_id": device_id,
            "timestamp": measured_at.astimezone(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "sensor_status": "ok",
        }
    )
    return reading


def post_gateway_reading(
    reading: dict[str, Any],
    gateway_url: str,
) -> tuple[int, str]:
    body = json.dumps(reading, separators=(",", ":")).encode("utf-8")
    http_request = urllib_request.Request(
        gateway_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib_request.urlopen(http_request, timeout=5) as response:
        return response.status, response.read().decode("utf-8")


def open_serial_port(serial_port: Path) -> BinaryIO:
    descriptor = os.open(serial_port, os.O_RDONLY | os.O_NOCTTY)

    try:
        attributes = termios.tcgetattr(descriptor)
        attributes[0] = 0
        attributes[1] = 0
        attributes[2] = (
            attributes[2]
            & ~(termios.CSIZE | termios.PARENB | termios.CSTOPB)
            | termios.CS8
            | termios.CLOCAL
            | termios.CREAD
        )
        attributes[3] = 0
        attributes[4] = termios.B115200
        attributes[5] = termios.B115200
        attributes[6][termios.VMIN] = 1
        attributes[6][termios.VTIME] = 0
        termios.tcsetattr(descriptor, termios.TCSANOW, attributes)
        return os.fdopen(descriptor, "rb", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


def run_bridge(serial_port: Path, device_id: str, gateway_url: str) -> None:
    while True:
        try:
            with open_serial_port(serial_port) as serial_stream:
                print(f"Reading ESP32 sensor data from {serial_port} at 115200 baud.", flush=True)

                while True:
                    raw_line = serial_stream.readline()
                    if not raw_line:
                        raise OSError("Serial device disconnected.")

                    sensor_reading = parse_sensor_line(raw_line)
                    if sensor_reading is None:
                        diagnostic = raw_line.decode("utf-8", errors="replace").strip()
                        if diagnostic:
                            print(f"Ignoring non-JSON serial line: {diagnostic}", flush=True)
                        continue

                    reading = complete_reading(
                        sensor_reading,
                        device_id,
                        datetime.now(timezone.utc),
                    )

                    try:
                        status, response_body = post_gateway_reading(reading, gateway_url)
                    except (OSError, urllib_error.URLError) as error:
                        print(f"Unable to post reading to gateway: {error}", flush=True)
                        continue

                    print(
                        f"Gateway response: HTTP {status} {response_body}",
                        flush=True,
                    )
        except OSError as error:
            print(
                f"Unable to read {serial_port}: {error}. "
                f"Retrying in {RECONNECT_DELAY_SECONDS} seconds.",
                flush=True,
            )
            time.sleep(RECONNECT_DELAY_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bridge ESP32 USB serial readings to the local Konoha gateway"
    )
    parser.add_argument(
        "--serial-port",
        required=True,
        type=Path,
        help="Stable ESP32 serial device path, preferably under /dev/serial/by-id",
    )
    parser.add_argument(
        "--device-id",
        default=DEFAULT_DEVICE_ID,
        help="Device ID added to each sensor reading",
    )
    parser.add_argument(
        "--gateway-url",
        default=DEFAULT_GATEWAY_URL,
        help="Local gateway readings endpoint",
    )
    args = parser.parse_args()

    try:
        run_bridge(args.serial_port, args.device_id, args.gateway_url)
    except KeyboardInterrupt:
        print("\nShutting down ESP32 serial bridge.", flush=True)


if __name__ == "__main__":
    main()
