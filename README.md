# konoha-gateway

Raspberry Pi local receiver v1 for the Konoha-gotchi class prototype.

This gateway accepts ESP32-style JSON sensor readings, validates the dashboard
ingestion fields, prints valid readings to the console, and appends them to a
local JSONL log file. It does not upload to Supabase, call Gemini, or include
ESP32 firmware.

## Run On Raspberry Pi

Python 3.10 or newer is recommended. No external packages are required.

```bash
cd konoha-gateway
test ! -e pi-smoke-readings.jsonl || \
  mv pi-smoke-readings.jsonl "pi-smoke-readings.jsonl.$(date +%Y%m%d-%H%M%S).bak"
python3 -m konoha_gateway.server \
  --host 0.0.0.0 \
  --port 8080 \
  --log-file pi-smoke-readings.jsonl
```

The server accepts readings at:

```text
POST http://<raspberry-pi-ip>:8080/readings
```

## Sample Reading

From another terminal or device on the same network:

```bash
PI_IP="192.168.1.50"  # Replace with the Raspberry Pi's IP address.
HTTP_STATUS=$(
  curl -sS -o konoha-gateway-response.json -w "%{http_code}" \
  -X POST "http://${PI_IP}:8080/readings" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "konoha-esp32-01",
    "timestamp": "2026-06-29T12:00:00Z",
    "soil_moisture_raw": 1840,
    "soil_moisture_percent": 47.5,
    "temperature_c": 24.8,
    "humidity_percent": 58.2,
    "light_lux": 725.0,
    "sensor_status": "ok",
    "battery_or_power_status": "usb",
    "notes": "local gateway smoke test"
  }'
)
test "$HTTP_STATUS" = "201" && echo "PASS: HTTP 201" || \
  echo "FAIL: HTTP $HTTP_STATUS"
cat konoha-gateway-response.json
```

Expected success response:

```json
{"status":"logged","device_id":"konoha-esp32-01","timestamp":"2026-06-29T12:00:00Z"}
```

Back on the Raspberry Pi, confirm that the fresh smoke-test log contains exactly
one entry:

```bash
test "$(wc -l < pi-smoke-readings.jsonl)" -eq 1 && \
  echo "PASS: exactly one JSONL entry" || \
  echo "FAIL: expected exactly one JSONL entry"
sed -n '1p' pi-smoke-readings.jsonl
```

## Validation Contract

Required fields:

- `device_id`: non-empty string
- `timestamp`: ISO timestamp with `Z` or a numeric timezone offset
- `soil_moisture_raw`: integer
- `soil_moisture_percent`: number from 0 to 100
- `temperature_c`: number
- `humidity_percent`: number from 0 to 100
- `light_lux`: number greater than or equal to 0
- `sensor_status`: one of `ok`, `warning`, `error`, `offline`

Optional fields:

- `battery_or_power_status`: string when provided
- `notes`: string when provided

## Test

```bash
python3 -m unittest discover
```
