# Network Error Detection Analyzer
### Project Option 2 — Data Communications

---

## Project Structure

```
/root/project/
├── error_detection.py   ← Core algorithms (Parity, Checksum, CRC-16)
├── server.py            ← Flask web server (API + dashboard)
├── analyze.py           ← CLI analyzer with chart export
├── static/
│   └── index.html       ← Interactive web dashboard
├── output/              ← Generated charts & JSON (auto-created)
└── README.md
```

---

## How to Run

### Option A — Web Dashboard (recommended)
```bash
cd /root/project
python server.py
# Open browser → http://localhost:5000
```
The dashboard calls the Python backend in real-time.
Every "Run Simulation" click runs a fresh Monte-Carlo simulation.

### Option B — Command Line
```bash
cd /root/project
python analyze.py
# Optional arguments:
python analyze.py --rates 1 30 --steps 25 --trials 1000
```
Outputs charts to `/root/project/output/` and prints a report.

---

## Error Detection Techniques

| Technique    | Overhead | Detects                     | Miss Rate |
|--------------|----------|-----------------------------|-----------|
| Parity Check | +1 bit   | Odd-count bit errors only   | ~50%      |
| Checksum     | +16 bits | Most random errors          | <0.5%     |
| CRC-16       | +16 bits | Burst errors ≤ 16 bits      | ~0%       |

---

## API Endpoints (when server.py is running)

| Method | URL            | Description                       |
|--------|----------------|-----------------------------------|
| GET    | `/`            | Interactive web dashboard         |
| POST   | `/api/simulate`| Run full Monte-Carlo simulation   |
| POST   | `/api/transmit`| Simulate one message transmission |

### POST /api/simulate
```json
{
  "min_rate": 1,
  "max_rate": 20,
  "steps": 20,
  "trials": 600
}
```

### POST /api/transmit
```json
{
  "message": "Hello Network!",
  "error_rate": 5
}
```
