from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any

from .validation import validate_reading


class GatewayServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], log_file: Path):
        super().__init__(server_address, GatewayRequestHandler)
        self.log_file = log_file


class GatewayRequestHandler(BaseHTTPRequestHandler):
    server: GatewayServer

    def do_POST(self) -> None:
        if self.path != "/readings":
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "Not found. POST sensor readings to /readings."},
            )
            return

        body = self._read_json_body()

        if isinstance(body, JsonBodyError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": body.message})
            return

        reading, errors = validate_reading(body)

        if errors:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Validation failed.", "details": errors},
            )
            return

        assert reading is not None

        try:
            self._append_reading(reading)
        except OSError:
            self.log_error("Unable to append reading to %s", self.server.log_file)
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Unable to write reading to local log file."},
            )
            return

        print(json.dumps(reading, separators=(",", ":")), flush=True)
        self._send_json(
            HTTPStatus.CREATED,
            {
                "status": "logged",
                "device_id": reading["device_id"],
                "timestamp": reading["timestamp"],
            },
        )

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)

    def _read_json_body(self) -> Any | "JsonBodyError":
        content_type = self.headers.get("Content-Type", "")

        if "application/json" not in content_type.lower():
            return JsonBodyError("Content-Type must be application/json.")

        content_length_header = self.headers.get("Content-Length")

        if content_length_header is None:
            return JsonBodyError("Content-Length header is required.")

        try:
            content_length = int(content_length_header)
        except ValueError:
            return JsonBodyError("Content-Length header must be an integer.")

        if content_length <= 0:
            return JsonBodyError("Request body must not be empty.")

        raw_body = self.rfile.read(content_length)

        try:
            return json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonBodyError("Request body must be valid JSON.")

    def _append_reading(self, reading: dict[str, Any]) -> None:
        self.server.log_file.parent.mkdir(parents=True, exist_ok=True)

        with self.server.log_file.open("a", encoding="utf-8") as log:
            log.write(json.dumps(reading, separators=(",", ":")) + "\n")

    def _send_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        response = json.dumps(body, separators=(",", ":")).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class JsonBodyError:
    def __init__(self, message: str):
        self.message = message


def main() -> None:
    parser = argparse.ArgumentParser(description="Konoha-gotchi local Raspberry Pi gateway")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument(
        "--log-file",
        default="readings.jsonl",
        type=Path,
        help="Local JSONL file for accepted readings",
    )
    args = parser.parse_args()

    server = GatewayServer((args.host, args.port), args.log_file)
    print(
        f"Konoha gateway listening on http://{args.host}:{args.port}/readings "
        f"and logging to {args.log_file}",
        flush=True,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Konoha gateway.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
