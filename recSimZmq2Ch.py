#!/usr/bin/env python3

import zmq
import numpy as np

# =========================================
# CONFIG
# =========================================

ADDRESS = "tcp://localhost:5555"

BLOCK_SIZE = 500

# =========================================
# ZMQ SUBSCRIBER
# =========================================

context = zmq.Context()

socket = context.socket(zmq.SUB)

socket.connect(ADDRESS)

socket.setsockopt(zmq.SUBSCRIBE, b"")

# =========================================
# BUFFER
# =========================================

buffer = np.array([], dtype=np.complex64)

print("Receiving IQ continuously...")

# =========================================
# MAIN LOOP
# =========================================

while True:

    # -------------------------------------
    # RECEIVE ZMQ DATA
    # -------------------------------------

    msg = socket.recv()

    iq = np.frombuffer(msg, dtype=np.complex64)

    # -------------------------------------
    # APPEND TO BUFFER
    # -------------------------------------

    buffer = np.concatenate((buffer, iq))

    # -------------------------------------
    # PROCESS COMPLETE BLOCKS
    # -------------------------------------

    while len(buffer) >= BLOCK_SIZE:

        # EXACT BLOCK
        iq_block = buffer[:BLOCK_SIZE]

        # REMOVE USED SAMPLES
        buffer = buffer[BLOCK_SIZE:]

        # ---------------------------------
        # PROCESS BLOCK
        # ---------------------------------

        print("\nNEW BLOCK")
        print(f"Samples: {len(iq_block)}")

        for i, sample in enumerate(iq_block[:10]):

            print(
                f"{i:03d} | "
                f"I={sample.real:.5f} "
                f"Q={sample.imag:.5f}"
            )