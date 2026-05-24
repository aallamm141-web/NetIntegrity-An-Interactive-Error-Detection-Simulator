```markdown
# NetIntegrity: Network Error Detection Analyzer
### Project Option 2 — Data Communications & Networking

NetIntegrity is a professional-grade simulation tool designed to analyze and visualize the efficiency of data integrity algorithms. By leveraging **Monte-Carlo simulations**, the project evaluates how different techniques (Parity, Checksum, and CRC-16) perform under varying levels of network noise.

---

##  Key Features
- **Monte-Carlo Simulation:** Runs thousands of automated trials per error rate to provide statistically significant detection data.
- **Industry Standard CRC-16:** Implements the CRC-16-ANSI polynomial division used in USB and Ethernet protocols.
- **Interactive Dashboard:** A modern, dark-themed Flask web interface for real-time "Live Transmissions."
- **Data Visualization:** Automatically generates Heatmaps, Bar Charts, and Detection Curves using Matplotlib.

---

##  Project Structure

```

/root/project/
├── error_detection.py    # Core algorithms (Parity, Checksum, CRC-16)
├── server.py             # Flask backend (REST API + Web Dashboard)
├── analyze.py            # CLI tool for batch simulation & chart export
├── static/
│   └── index.html        # Interactive Frontend (Vanilla JS + CSS3)
├── output/               # Auto-generated simulation reports & PNGs
└── README.md             # Project documentation

```

---

##  Installation & Requirements
Ensure you have **Python 3.8+** installed. You will need the following libraries:

```bash
pip install flask matplotlib numpy

```

---

##  How to Run

### Option A: Interactive Web Dashboard (Recommended)

```bash
python server.py
# Open: http://localhost:5000

```

Use the dashboard to customize error rates, steps, and trials. The "Live Transmission" tool allows you to see exactly how bits are flipped and whether the algorithms catch them.

### Option B: CLI Analyzer

```bash
python analyze.py --rates 1 30 --steps 20 --trials 1000

```

This generates a full report in the terminal and saves high-resolution charts to the `output/` folder.

---

##  Comparative Analysis

| Technique | Overhead | Detection Logic | Reliability |
| --- | --- | --- | --- |
| **Parity** | +1 bit | Detects odd-count bit flips | Weak (50%) |
| **Checksum** | +16 bits | 1's complement summation | Good (>99%) |
| **CRC-16** | +16 bits | Polynomial Division (MOD-2) | Best (99.9%) |

> **Technical Insight:** While Parity is efficient for simple serial links, **CRC-16** provides the highest mathematical guarantee for detecting burst errors, making it the standard for modern high-speed networking.

---

## 🔗 API Documentation

The backend exposes a REST API for external integration:

* `POST /api/simulate`: Executes a full simulation sweep.
* `POST /api/transmit`: Simulates a single message with manual error injection.

---

**Developed by:** Allam
**Field:** Cybersecurity & Network Engineering

```
