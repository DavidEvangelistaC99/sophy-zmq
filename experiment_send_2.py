#!/usr/bin/env python3

"""
THOR-like ZMQ Transmitter

Este script:
- genera IQ sintético continuamente
- transmite IQ por ZMQ
- transmite metadata tipo THOR por ZMQ

YA NO guarda DigitalRF localmente.

La escritura DigitalRF ocurrirá en el receptor.
"""

import time
import json
import threading
import zmq

from gnuradio import gr
from gnuradio import analog
from gnuradio import zeromq


# ============================================================
# CONFIGURACIÓN
# ============================================================

SAMPLE_RATE = 10_000 #1_000_000

CENTER_FREQ = 50_000_000

TONE_FREQ = 100_000

AMPLITUDE = 0.7

UUID_STR = "thor-simulator"


# ------------------------------------------------------------
# ZMQ ADDRESSES
# ------------------------------------------------------------

# IQ STREAM
IQ_ADDRESS = "tcp://*:5555"

# METADATA
META_ADDRESS = "tcp://*:5556"


# ============================================================
# THOR ZMQ TRANSMITTER
# ============================================================

class ThorZMQTransmitter:

    def __init__(self):

        self.running = False

        self.fg = None

        self.iq_thread = None

        self.meta_thread = None


    # ========================================================
    # METADATA
    # ========================================================

    def _build_metadata(self):

        metadata = dict(

            receiver=dict(

                description="Simulated UHD USRP source using GNU Radio",

                info="THOR simulator",

                antenna="RX2",

                bandwidth=SAMPLE_RATE,

                center_freq=CENTER_FREQ,

                clock_rate=SAMPLE_RATE,

                clock_source="internal",

                dc_offset=False,

                gain=30,

                id="SIMULATED_USRP",

                iq_balance=False,

                lo_export=False,

                lo_offset=0,

                lo_source="internal",

                otw_format="sc16",

                samp_rate=SAMPLE_RATE,

                stream_args="",

                subdev="A:A",

                time_source="internal",
            ),

            processing=dict(

                channelizer_filter_taps=[],

                decimation=1,

                interpolation=1,

                resampling_filter_taps=[],

                scaling=1.0,
            ),

            simulation=dict(

                signal_type="complex_sine",

                tone_frequency=TONE_FREQ,

                amplitude=AMPLITUDE,
            ),

            transport=dict(

                iq_protocol="ZMQ",

                iq_address=IQ_ADDRESS,

                metadata_address=META_ADDRESS,
            ),

            digital_rf=dict(

                uuid=UUID_STR,

                dtype="complex64",

                sample_rate=SAMPLE_RATE,

                center_frequency=CENTER_FREQ,
            )
        )

        return metadata


    # ========================================================
    # BUILD FLOWGRAPH
    # ========================================================

    def _build_flowgraph(self):

        fg = gr.top_block()

        # ----------------------------------------------------
        # SIGNAL SOURCE
        # ----------------------------------------------------

        # Genera IQ continuo como una USRP

        src = analog.sig_source_c(

            SAMPLE_RATE,

            analog.GR_SIN_WAVE,

            TONE_FREQ,

            AMPLITUDE,

            0,
        )

        # ----------------------------------------------------
        # ZMQ PUB SINK (IQ STREAM)
        # ----------------------------------------------------

        zmq_sink = zeromq.pub_sink(

            itemsize=gr.sizeof_gr_complex,

            vlen=1,

            address=IQ_ADDRESS,

            timeout=100,

            pass_tags=False,

            hwm=-1,
        )

        # ----------------------------------------------------
        # CONNECT
        # ----------------------------------------------------

        fg.connect(
            src,
            zmq_sink
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
    # METADATA THREAD
    # ========================================================

    def _run_metadata_sender(self):

        context = zmq.Context()

        socket = context.socket(zmq.PUB)

        socket.bind(META_ADDRESS)

        metadata = self._build_metadata()

        # Esperar a que los subscribers se conecten
        time.sleep(1)

        while self.running:

            socket.send_json(metadata)

            print("[META] Metadata enviada")

            # metadata ocasional
            time.sleep(5)

        socket.close()

        context.term()


    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        print("\n===================================")
        print("THOR ZMQ TRANSMITTER")
        print("===================================")

        print(f"Sample Rate : {SAMPLE_RATE}")
        print(f"Center Freq : {CENTER_FREQ}")
        print(f"Tone Freq   : {TONE_FREQ}")

        print("\nIQ STREAM:")
        print(IQ_ADDRESS)

        print("\nMETADATA STREAM:")
        print(META_ADDRESS)

        print("\nCreating flowgraph...")

        # ----------------------------------------------------
        # GNU RADIO FLOWGRAPH
        # ----------------------------------------------------

        self.fg = self._build_flowgraph()

        self.running = True

        # ----------------------------------------------------
        # IQ THREAD
        # ----------------------------------------------------

        print("\nStarting IQ transmission thread...")

        self.iq_thread = threading.Thread(
            target=self._run_flowgraph
        )

        self.iq_thread.start()

        # ----------------------------------------------------
        # METADATA THREAD
        # ----------------------------------------------------

        print("Starting metadata transmission thread...")

        self.meta_thread = threading.Thread(
            target=self._run_metadata_sender
        )

        self.meta_thread.start()

        # ----------------------------------------------------
        # MAIN LOOP
        # ----------------------------------------------------

        try:

            while True:

                time.sleep(1)

        except KeyboardInterrupt:

            print("\nStopping transmitter...")

            self.running = False

            self.iq_thread.join()

            self.meta_thread.join()

            print("Done.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    tx = ThorZMQTransmitter()

    tx.run()