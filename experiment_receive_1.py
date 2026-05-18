#!/usr/bin/env python3

"""
THOR-like ZMQ Receiver

Este script:

- recibe metadata por ZMQ
- recibe IQ continuo por ZMQ
- reconstruye un dataset DigitalRF
- almacena HDF5 igual que THOR

Arquitectura:

TRANSMISOR
    IQ PUB  ------>  IQ SUB
    META PUB ----->  META SUB

RECEPTOR
    ZMQ SUB
        ↓
digital_rf_channel_sink
        ↓
DigitalRF dataset
"""

import os
import time
import threading
import zmq
import numpy as np

from fractions import Fraction

from gnuradio import gr
from gnuradio import zeromq

from gr_digital_rf import digital_rf_channel_sink


# ============================================================
# CONFIGURACIÓN
# ============================================================

TX_IP = "127.0.0.1"

IQ_ADDRESS = f"tcp://{TX_IP}:5555"

META_ADDRESS = f"tcp://{TX_IP}:5556"

DATA_DIR = "thor_zmq_recording"

CHANNEL_NAME = "ch0"


# ============================================================
# RECEIVER
# ============================================================

class ThorZMQReceiver:

    def __init__(self):

        self.running = False

        self.metadata = None

        self.fg = None

        self.rx_thread = None


    # ========================================================
    # RECEIVE METADATA
    # ========================================================

    def receive_metadata(self):

        print("\nWaiting for metadata...")

        context = zmq.Context()

        socket = context.socket(zmq.SUB)

        socket.connect(META_ADDRESS)

        socket.setsockopt_string(
            zmq.SUBSCRIBE,
            ""
        )

        metadata = socket.recv_json()

        print("\n[META RECEIVED]")

        self.metadata = metadata

        socket.close()

        context.term()


    # ========================================================
    # BUILD FLOWGRAPH
    # ========================================================

    def _build_flowgraph(self):

        fg = gr.top_block()

        # ----------------------------------------------------
        # GET PARAMETERS FROM METADATA
        # ----------------------------------------------------

        sr = self.metadata["digital_rf"]["sample_rate"]

        center_freq = self.metadata["digital_rf"]["center_frequency"]

        uuid_str = self.metadata["digital_rf"]["uuid"]

        sr_frac = Fraction(sr)

        # ----------------------------------------------------
        # START SAMPLE
        # ----------------------------------------------------

        start_sample = int(time.time() * sr)

        # ----------------------------------------------------
        # ZMQ SUB SOURCE
        # ----------------------------------------------------

        zmq_source = zeromq.sub_source(

            itemsize=gr.sizeof_gr_complex,

            vlen=1,

            address=IQ_ADDRESS,

            timeout=100,

            pass_tags=False,

            hwm=-1,
        )

        # ----------------------------------------------------
        # DIGITAL RF SINK
        # ----------------------------------------------------

        dst = digital_rf_channel_sink(

            channel_dir=os.path.join(
                DATA_DIR,
                CHANNEL_NAME
            ),

            dtype=np.complex64,

            subdir_cadence_secs=1,

            file_cadence_millisecs=1000,

            sample_rate_numerator=sr_frac.numerator,

            sample_rate_denominator=sr_frac.denominator,

            start=start_sample,

            ignore_tags=False,

            is_complex=True,

            num_subchannels=1,

            uuid_str=uuid_str,

            center_frequencies=center_freq,

            metadata=self.metadata,

            is_continuous=True,

            compression_level=0,

            checksum=False,

            marching_periods=True,

            stop_on_skipped=False,

            stop_on_time_tag=False,

            debug=True,
        )

        # ----------------------------------------------------
        # CONNECT
        # ----------------------------------------------------

        fg.connect(
            zmq_source,
            dst
        )

        return fg


    # ========================================================
    # FLOWGRAPH THREAD
    # ========================================================

    def _run_flowgraph(self):

        self.fg.start()

        while self.running:

            time.sleep(1)

        self.fg.stop()

        self.fg.wait()


    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        print("\n===================================")
        print("THOR ZMQ RECEIVER")
        print("===================================")

        # ----------------------------------------------------
        # RECEIVE METADATA FIRST
        # ----------------------------------------------------

        self.receive_metadata()

        print("\nMetadata loaded.")

        print("\nCreating flowgraph...")

        # ----------------------------------------------------
        # BUILD FLOWGRAPH
        # ----------------------------------------------------

        self.fg = self._build_flowgraph()

        self.running = True

        # ----------------------------------------------------
        # START RX THREAD
        # ----------------------------------------------------

        print("\nStarting receiver thread...")

        self.rx_thread = threading.Thread(
            target=self._run_flowgraph
        )

        self.rx_thread.start()

        # ----------------------------------------------------
        # MAIN LOOP
        # ----------------------------------------------------

        try:

            while True:

                time.sleep(1)

        except KeyboardInterrupt:

            print("\nStopping receiver...")

            self.running = False

            self.rx_thread.join()

            print("Done.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    os.makedirs(DATA_DIR, exist_ok=True)

    rx = ThorZMQReceiver()

    rx.run()