#!/usr/bin/env python3

"""
THOR-like ZMQ Receiver + DigitalRF Recorder

Este script:

- recibe IQ complejo por ZMQ
- recibe metadata por ZMQ
- guarda IQ en DigitalRF
- imprime metadata recibida

Compatible con el transmisor THOR-like.
"""

import os
import time
import json
import queue
import threading

import zmq
import numpy as np
import digital_rf


# ============================================================
# CONFIG
# ============================================================

IQ_ADDRESS = "tcp://localhost:5555"

META_ADDRESS = "tcp://localhost:5556"

OUTPUT_DIR = "./digitalrf_data"

CHANNEL_NAME = "ch0"

UUID_STR = "thor-simulator"


# ============================================================
# GLOBALS
# ============================================================

metadata_latest = {}

running = True


# ============================================================
# METADATA RECEIVER
# ============================================================

def metadata_receiver():

    global metadata_latest
    global running

    context = zmq.Context()

    socket = context.socket(zmq.SUB)

    socket.connect(META_ADDRESS)

    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    while running:

        try:

            metadata = socket.recv_json()

            metadata_latest = metadata

            print("\n[META RECEIVED]")
            print(json.dumps(metadata, indent=2))

        except Exception as e:

            print("Metadata RX error:", e)

            time.sleep(1)

    socket.close()
    context.term()


# ============================================================
# IQ RECEIVER + DIGITALRF WRITER
# ============================================================

def iq_receiver():

    global running

    # --------------------------------------------------------
    # ZMQ
    # --------------------------------------------------------

    context = zmq.Context()

    socket = context.socket(zmq.SUB)

    socket.connect(IQ_ADDRESS)

    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    # --------------------------------------------------------
    # DIGITAL RF CONFIG
    # --------------------------------------------------------

    sample_rate = 1_000_000

    samples_per_file = 1_000_000

    files_per_directory = 100

    dtype = np.complex64

    start_index = int(time.time() * sample_rate)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    channel_dir = os.path.join(
        OUTPUT_DIR,
        CHANNEL_NAME
    )

    os.makedirs(channel_dir, exist_ok=True)

    writer = digital_rf.DigitalRFWriter(

        channel_dir,

        dtype=dtype,

        subdir_cadence_secs=3600,

        file_cadence_millisecs=1000,

        start_global_index=start_index,

        sample_rate_numerator=sample_rate,

        sample_rate_denominator=1,

        uuid_str=UUID_STR,

        compression_level=0,

        checksum=False,

        is_complex=True,

        num_subchannels=1,
    )

    print("\n[DIGITAL RF]")
    print("Writing to:", channel_dir)

    total_samples = 0

    # --------------------------------------------------------
    # RECEIVE LOOP
    # --------------------------------------------------------

    while running:

        try:

            # recibir bytes IQ
            msg = socket.recv()

            # convertir a complex64
            iq = np.frombuffer(
                msg,
                dtype=np.complex64
            )

            # escribir
            writer.rf_write(iq)

            total_samples += len(iq)

            print(
                f"\rSamples written: {total_samples}",
                end=""
            )

        except Exception as e:

            print("\nIQ RX error:", e)

            time.sleep(1)

    writer.close()

    socket.close()

    context.term()


# ============================================================
# MAIN
# ============================================================

def main():

    global running

    print("\n===================================")
    print("THOR ZMQ RECEIVER")
    print("===================================")

    print("IQ:", IQ_ADDRESS)
    print("META:", META_ADDRESS)

    meta_thread = threading.Thread(
        target=metadata_receiver
    )

    iq_thread = threading.Thread(
        target=iq_receiver
    )

    meta_thread.start()

    iq_thread.start()

    try:

        while True:

            time.sleep(1)

    except KeyboardInterrupt:

        print("\nStopping...")

        running = False

        meta_thread.join()

        iq_thread.join()

        print("Done.")


if __name__ == "__main__":

    main()