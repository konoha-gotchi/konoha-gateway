# konoha-gateway

Raspberry Pi local receiver v1 for the Konoha-gotchi class prototype.

This gateway accepts ESP32-style JSON sensor readings, validates the dashboard
ingestion fields, prints valid readings to the console, and appends them to a
local JSONL log file. It does not upload to Supabase, call Gemini, or include
ESP32 firmware.

## Connect ESP32 By USB

The ESP32 can send its combined sensor JSON to a Raspberry Pi over the same USB
data cable used to program it. The serial bridge adds the trusted device ID,
the Raspberry Pi's current UTC timestamp, and an `ok` sensor status before
posting each reading to the local gateway.

This connection does not require a router or Wi-Fi. The Raspberry Pi can use
its Wi-Fi connection independently for later Vercel uploads and dashboard
access.

On the Raspberry Pi, connect the ESP32 by USB and find its stable device path:

```bash
ls -l /dev/serial/by-id/
```

Use the full `/dev/serial/by-id/...` path shown by that command. If opening the
device returns `Permission denied`, add the Raspberry Pi user to the `dialout`
group, then log out and back in:

```bash
sudo usermod -aG dialout "$USER"
```

Because the Raspberry Pi supplies each reading's timestamp, confirm that its
clock is synchronized:

```bash
timedatectl status
```

Start the local gateway in the first terminal:

```bash
cd konoha-gateway
test ! -e pi-usb-readings.jsonl || \
  mv pi-usb-readings.jsonl "pi-usb-readings.jsonl.$(date +%Y%m%d-%H%M%S).bak"
python3 -m konoha_gateway.server \
  --host 127.0.0.1 \
  --port 8080 \
  --log-file pi-usb-readings.jsonl
```

In a second terminal, start the serial bridge. Replace the example serial path
with the path reported by `ls`:

```bash
cd konoha-gateway
python3 -m konoha_gateway.serial_bridge \
  --serial-port /dev/serial/by-id/usb-REPLACE_WITH_YOUR_ESP32
```

The bridge expects the firmware's existing 115200-baud JSON output. Successful
readings produce gateway responses beginning with:

```text
Gateway response: HTTP 201
```

After at least 20 seconds, verify that the Raspberry Pi logged ten readings:

```bash
test "$(wc -l < pi-usb-readings.jsonl)" -ge 10 && \
  echo "PASS: at least ten USB readings logged" || \
  echo "FAIL: fewer than ten USB readings logged"
tail -n 3 pi-usb-readings.jsonl
```

Finally, unplug the ESP32, wait for the bridge to report a retry, and reconnect
it. The bridge should reopen the stable device path automatically and the
JSONL line count should continue increasing.

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
