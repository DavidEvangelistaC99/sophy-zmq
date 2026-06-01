#!/usr/bin/env python3

import numpy as np
import matplotlib.pyplot as plt
import digital_rf as drf

# ============================================================
# CONFIG
# ============================================================

DATASET_DIR = "/home/david/Documents/DATA/SIN@2026-01-21T00-00-01/rawdata"

CHANNEL = "ch0"

NUM_SAMPLES = 10000

# ============================================================
# OPEN DIGITAL RF
# ============================================================

reader = drf.DigitalRFReader(DATASET_DIR)

print("\nAvailable channels:")

channels = reader.get_channels()

for ch in channels:
    print("  ", ch)

if CHANNEL not in channels:
    raise RuntimeError(
        f"Channel '{CHANNEL}' not found"
    )

# ============================================================
# CHANNEL BOUNDS
# ============================================================

start_sample, end_sample = reader.get_bounds(CHANNEL)

print("\nBounds")

print("Start :", start_sample)
print("End   :", end_sample)

available = end_sample - start_sample

print("Samples available :", available)

N = min(NUM_SAMPLES, available)

# ============================================================
# READ DATA
# ============================================================

iq = reader.read_vector(
    start_sample,
    N,
    CHANNEL
)

print("\nRead samples:", len(iq))

# ============================================================
# TIME AXIS
# ============================================================

sample_rate = 2_500_000

t = np.arange(len(iq)) / sample_rate

# ============================================================
# TIME DOMAIN
# ============================================================

plt.plot(
    t,
    np.real(iq),
    label="I"
)

plt.plot(
    t,
    np.imag(iq),
    label="Q"
)

plt.title("DigitalRF IQ Samples")
plt.xlabel("Time [s]")
plt.ylabel("Amplitude")
plt.grid(True)
plt.legend()

plt.show()