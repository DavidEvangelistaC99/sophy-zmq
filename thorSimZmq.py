#!/usr/bin/env python3

import os
import time
import numpy as np
from fractions import Fraction

from gnuradio import gr
from gnuradio import analog

import digital_rf
from gr_digital_rf import digital_rf_channel_sink
from gnuradio import zeromq

import threading
import zmq

# ============================================================
# CONFIG
# ============================================================

DATA_DIR = "SIN@2026-01-21T00-00-01"
CHANNEL_NAME = "ch0"

SAMPLE_RATE = 10_000_000
CENTER_FREQ = 50_000_000

TONE_FREQ = 100_000
AMPLITUDE = 0.7

UUID_STR = "thor-simulator"
RUN_TIME_SECONDS = 60


# ============================================================
# FLOWGRAPH
# ============================================================

class ThorSimulator(gr.top_block):

    def metadata_loop(self):

        while self.running:

            try:
                meta = dict(self.metadata)
                meta["heartbeat"] = time.time()
                self.meta_socket.send_json(meta)
                time.sleep(1)

            except zmq.ZMQError:
                break

    def __init__(self):

        gr.top_block.__init__(self, "THOR + ZMQ Simulator")

        # -----------------------------
        # SIGNAL SOURCE
        # -----------------------------
        self.src = analog.sig_source_c(
            SAMPLE_RATE,
            analog.GR_SIN_WAVE,
            TONE_FREQ,
            AMPLITUDE,
            0,
        )

        self.running = True

        sr_frac = Fraction(SAMPLE_RATE)

        # IMPORTANTE: timestamp estable por corrida
        start_time = int(time.time())
        start_sample = start_time * SAMPLE_RATE

        # ========================================================
        # METADATA (SCHAIN COMPATIBLE STRUCTURE)
        # ========================================================

        metadata = {
            "receiver": {
                "description": "Simulated UHD USRP source using GNU Radio",
                "info": "THOR simulator",
                "antenna": "RX2",
                "bandwidth": SAMPLE_RATE,
                "center_freq": CENTER_FREQ,
                "clock_rate": SAMPLE_RATE,
                "gain": 30,
                "id": "SIMULATED_USRP",
                "samp_rate": SAMPLE_RATE,
            },
            "processing": {
                "decimation": 1,
                "interpolation": 1,
                "scaling": 1.0,
            },
            "simulation": {
                "signal_type": "complex_sine",
                "tone_frequency": TONE_FREQ,
                "amplitude": AMPLITUDE,
            }
        }

        # ========================================================
        # CHANNEL DIRECTORY (IMPORTANT STRUCTURE)
        # ========================================================

        run_folder = "rawdata"


        channel_dir = os.path.join(DATA_DIR, run_folder, CHANNEL_NAME)

        os.makedirs(channel_dir, exist_ok=True)

        # ========================================================
        # DIGITAL RF SINK (DISK)
        # ========================================================

        self.drf = digital_rf_channel_sink(

            channel_dir=channel_dir,

            dtype=np.complex64,

            subdir_cadence_secs=3600,      # evita fragmentación extrema
            file_cadence_millisecs=1000,

            sample_rate_numerator=sr_frac.numerator,
            sample_rate_denominator=sr_frac.denominator,

            start=start_sample,

            ignore_tags=False,
            is_complex=True,
            num_subchannels=1,

            uuid_str=UUID_STR,
            center_frequencies=CENTER_FREQ,

            metadata=metadata,

            is_continuous=True,
            compression_level=0,
            checksum=False,
            marching_periods=True,

            stop_on_skipped=False,
            stop_on_time_tag=False,

            debug=True,
        )

        # ========================================================
        # ZMQ SINK (STREAMING)
        # ========================================================

        self.zmq = zeromq.pub_sink(
            itemsize=gr.sizeof_gr_complex,
            vlen=1,
            address="tcp://*:5555",
            timeout=100,
            pass_tags=False,
            hwm=10,
        )

        # ========================================================
        # CONNECTION (FANOUT)
        # ========================================================

        self.connect(self.src, self.drf)
        self.connect(self.src, self.zmq)

        # ========================================================
        # ZMQ METADATA (SEND ONCE)
        # ========================================================

        self.context = zmq.Context()
        self.meta_socket = self.context.socket(zmq.PUB)
        self.meta_socket.bind("tcp://*:5556")

        # IMPORTANT: allow subscribers to connect
        # time.sleep(2)

        # self.meta_socket.send_json(metadata)
        # print("[META] Metadata enviada una sola vez")

        self.metadata = metadata
        self.meta_thread = threading.Thread(
            target=self.metadata_loop,
            daemon=True
        )

        self.meta_thread.start()
        print("[META] Metadata loop started")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    os.makedirs(DATA_DIR, exist_ok=True)

    fg = ThorSimulator()

    print("\n====================================")
    print("THOR SIMULATOR (DRF + ZMQ)")
    print("====================================")
    print(f"Sample Rate : {SAMPLE_RATE}")
    print(f"Center Freq : {CENTER_FREQ}")
    print(f"Tone Freq   : {TONE_FREQ}")

    fg.start()

    try:
        time.sleep(RUN_TIME_SECONDS)

    finally:
        print("\nStopping flowgraph...")
        fg.running = False
        fg.stop()
        fg.wait()
        fg.meta_socket.close()
        fg.context.term()
        print("Done.")