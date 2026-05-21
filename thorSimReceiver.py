#!/usr/bin/env python3

import zmq
import json
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# CONFIG
# ============================================================

META_ADDR = "tcp://localhost:5556"

IQ_ADDR = "tcp://localhost:5555"

# ============================================================
# ZMQ CONTEXT
# ============================================================

ctx = zmq.Context()

# ============================================================
# METADATA SUBSCRIBER
# ============================================================

meta_sock = ctx.socket(zmq.SUB)

meta_sock.connect(META_ADDR)

meta_sock.setsockopt_string(
    zmq.SUBSCRIBE,
    ""
)

# ============================================================
# IQ SUBSCRIBER
# ============================================================

iq_sock = ctx.socket(zmq.SUB)

iq_sock.connect(IQ_ADDR)

iq_sock.setsockopt(
    zmq.SUBSCRIBE,
    b""
)

# ============================================================
# POLLER
# ============================================================

poller = zmq.Poller()

poller.register(meta_sock, zmq.POLLIN)
poller.register(iq_sock, zmq.POLLIN)

# ============================================================
# MATPLOTLIB
# ============================================================

plt.ion()

fig, ax = plt.subplots()

line, = ax.plot(np.zeros(1024))

ax.set_ylim(-100, 100)

ax.set_title("FFT")

ax.set_xlabel("Bin")

ax.set_ylabel("Power (dB)")

# ============================================================
# MAIN LOOP
# ============================================================

print("\nWaiting data...\n")

while True:

    events = dict(poller.poll())

    # ========================================================
    # METADATA
    # ========================================================

    if meta_sock in events:

        topic, payload = meta_sock.recv_multipart()

        metadata = json.loads(payload.decode())

        print("\n================================")
        print("METADATA RECEIVED")
        print("================================")

        print("Topic:", topic.decode())

        print(json.dumps(
            metadata,
            indent=4
        ))

    # ========================================================
    # IQ DATA
    # ========================================================

    if iq_sock in events:

        raw = iq_sock.recv()

        iq = np.frombuffer(
            raw,
            dtype=np.complex64
        )

        if len(iq) == 0:
            continue

        # ====================================================
        # FFT
        # ====================================================

        fft = np.fft.fftshift(
            np.fft.fft(iq[:1024])
        )

        power = 20 * np.log10(
            np.abs(fft) + 1e-12
        )

        line.set_ydata(power)

        fig.canvas.draw()

        fig.canvas.flush_events()