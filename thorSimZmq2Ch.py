#!/usr/bin/env python3

import os
import time
import json
import zmq
import numpy as np
from fractions import Fraction

from gnuradio import gr
from gnuradio import analog
from gnuradio import blocks
from gnuradio import zeromq

from gr_digital_rf import digital_rf_channel_sink


# ============================================================
# CONFIG
# ============================================================

DATA_DIR = "SIN@2026-01-21T00-00-01"

SAMPLE_RATE = 1_000_000

CENTER_FREQ_CH0 = 50_000_000
CENTER_FREQ_CH1 = 51_000_000

UUID_STR = "thor-simulator"

RUN_TIME_SECONDS = 60

# ============================================================
# GLOBAL SYNCHRONIZED TIMEBASE
# ============================================================

GLOBAL_START_TIME = int(time.time())

GLOBAL_START_SAMPLE = GLOBAL_START_TIME * SAMPLE_RATE

# ============================================================
# CHANNEL CONFIGURATION
# ============================================================

CHANNELS = {

    "ch0": {
        "tone": 100_000,
        "amplitude": 0.7,
        "center_freq": CENTER_FREQ_CH0,
        "iq_port": 5555,
    },

    "ch1": {
        "tone": 200_000,
        "amplitude": 0.7,
        "center_freq": CENTER_FREQ_CH1,
        "iq_port": 5557,
    }
}


# ============================================================
# FLOWGRAPH
# ============================================================

class ThorSimulator(gr.top_block):

    def __init__(self):
        

        # GNU Radio flowgraph generation
        gr.top_block.__init__(self, "THOR MULTICHANNEL")

        sr_frac = Fraction(SAMPLE_RATE)

        self.blocks = []

        # ====================================================
        # ZMQ CONTEXT
        # ====================================================

        self.context = zmq.Context()

        # ====================================================
        # METADATA PUB SOCKET
        # ====================================================

        self.meta_socket = self.context.socket(zmq.PUB)

        self.meta_socket.bind("tcp://*:5556")

        # ====================================================
        # CREATE CHANNELS
        # ====================================================

        for ch_name, cfg in CHANNELS.items():

            print(f"\n[INIT] Creating {ch_name}")

            # ------------------------------------------------
            # SIGNAL SOURCE
            # ------------------------------------------------

            #src = analog.sig_source_c(

                #SAMPLE_RATE,

                #analog.GR_SIN_WAVE,

                #cfg["tone"],

                #cfg["amplitude"],

                #0,
            #)

            # ------------------------------------------------
            # PULSED SIGNAL PARAMETERS
            # ------------------------------------------------

            IPP_SAMPLES = 2000

            PULSE_PERCENT = 0.10

            PULSE_SAMPLES = int(IPP_SAMPLES * PULSE_PERCENT)

            # ------------------------------------------------
            # GENERATE ONE IPP
            # ------------------------------------------------

            t = np.arange(PULSE_SAMPLES)

            pulse = cfg["amplitude"] * np.exp(

                1j * 2 * np.pi *

                cfg["tone"] *

                t / SAMPLE_RATE

            )

            # remainder zeros

            zeros = np.zeros(

                IPP_SAMPLES - PULSE_SAMPLES,

                dtype=np.complex64
            )

            # complete ipp

            ipp = np.concatenate([
                pulse.astype(np.complex64),
                zeros
            ])

            # ------------------------------------------------
            # GNU RADIO VECTOR SOURCE
            # ------------------------------------------------

            src = blocks.vector_source_c(

                ipp.tolist(),

                repeat=True
            )

            # ------------------------------------------------
            # METADATA
            # ------------------------------------------------

            metadata = {

                "channel": ch_name,

                "receiver": {

                    "description":
                        "Simulated UHD USRP source using GNU Radio",

                    "info":
                        "THOR multichannel simulator",

                    "antenna":
                        "RX2",

                    "bandwidth":
                        SAMPLE_RATE,

                    "center_freq":
                        cfg["center_freq"],

                    "clock_rate":
                        SAMPLE_RATE,

                    "clock_source":
                        "internal",

                    "dc_offset":
                        False,

                    "gain":
                        30,

                    "id":
                        "SIMULATED_USRP",

                    "iq_balance":
                        False,

                    "lo_export":
                        False,

                    "lo_offset":
                        0,

                    "lo_source":
                        "internal",

                    "otw_format":
                        "sc16",

                    "samp_rate":
                        SAMPLE_RATE,

                    "stream_args":
                        "",

                    "subdev":
                        "A:A",

                    "time_source":
                        "internal",
                },

                "processing": {

                    "channelizer_filter_taps": [],

                    "decimation": 1,

                    "interpolation": 1,

                    "resampling_filter_taps": [],

                    "scaling": 1.0,
                },

                "simulation": {

                    "signal_type":
                        "complex_sine",

                    "tone_frequency":
                        cfg["tone"],

                    "amplitude":
                        cfg["amplitude"],
                },

                "transport": {

                    "iq_protocol":
                        "ZMQ",

                    "iq_address":
                        f"tcp://localhost:{cfg['iq_port']}",

                    "metadata_address":
                        "tcp://localhost:5556",
                },

                "digital_rf": {

                    "uuid":
                        UUID_STR,

                    "dtype":
                        "complex64",

                    "sample_rate":
                        SAMPLE_RATE,

                    "center_frequency":
                        cfg["center_freq"],

                    "start_sample":
                        GLOBAL_START_SAMPLE,
                }
            }

            # ------------------------------------------------
            # CHANNEL DIRECTORY
            # ------------------------------------------------

            channel_dir = os.path.join(

                DATA_DIR,

                "rawdata",

                ch_name
            )

            os.makedirs(channel_dir, exist_ok=True)

            # ------------------------------------------------
            # DIGITAL RF SINK
            # ------------------------------------------------

            drf = digital_rf_channel_sink(

                channel_dir=channel_dir,

                dtype=np.complex64,

                subdir_cadence_secs=3600,

                file_cadence_millisecs=1000,

                sample_rate_numerator=sr_frac.numerator,

                sample_rate_denominator=sr_frac.denominator,

                start=GLOBAL_START_SAMPLE,

                ignore_tags=False,

                is_complex=True,

                num_subchannels=1,

                uuid_str=UUID_STR,

                center_frequencies=cfg["center_freq"],

                metadata=metadata,

                is_continuous=True,

                compression_level=0,

                checksum=False,

                marching_periods=False,

                stop_on_skipped=False,

                stop_on_time_tag=False,

                debug=True,
            )

            # ------------------------------------------------
            # ZMQ IQ STREAM
            # ------------------------------------------------

            zmq_sink = zeromq.pub_sink(

                itemsize=gr.sizeof_gr_complex,

                vlen=1,

                address=f"tcp://*:{cfg['iq_port']}",

                timeout=100,

                pass_tags=False,

                hwm=1000,
            )

            # ------------------------------------------------
            # CONNECTIONS
            # ------------------------------------------------

            self.connect(src, drf)

            self.connect(src, zmq_sink)

            # ------------------------------------------------
            # SAVE REFERENCES
            # ------------------------------------------------

            self.blocks.append({

                "name": ch_name,

                "src": src,

                "drf": drf,

                "zmq": zmq_sink,

                "metadata": metadata,
            })

        # ====================================================
        # WAIT FOR SUBSCRIBERS
        # ====================================================

        print("\n[ZMQ] Waiting subscribers...")

        time.sleep(2)

        # ====================================================
        # SEND METADATA ONCE
        # ====================================================

        print("\n[ZMQ] Sending metadata...")

        for block in self.blocks:

            topic = block["name"].encode()

            payload = json.dumps(
                block["metadata"]
            ).encode()

            self.meta_socket.send_multipart([
                topic,
                payload
            ])

            print(f"[META] Sent {block['name']}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    os.makedirs(DATA_DIR, exist_ok=True)

    fg = ThorSimulator()

    print("\n====================================")
    print("THOR MULTICHANNEL SIMULATOR")
    print("====================================")

    print(f"Sample Rate : {SAMPLE_RATE}")

    print(f"Global Start Time : {GLOBAL_START_TIME}")

    print(f"Global Start Sample : {GLOBAL_START_SAMPLE}")

    print("\nChannels:")

    for ch_name, cfg in CHANNELS.items():

        print(f"\n{ch_name}")

        print(f"  Tone       : {cfg['tone']}")

        print(f"  CenterFreq : {cfg['center_freq']}")

        print(f"  IQ ZMQ     : tcp://localhost:{cfg['iq_port']}")

    print("\nMetadata ZMQ : tcp://localhost:5556")

    print("\nStarting flowgraph...\n")

    fg.start()

    try:

        time.sleep(RUN_TIME_SECONDS)

    except KeyboardInterrupt:

        pass

    finally:

        print("\nStopping flowgraph...")

        fg.stop()

        fg.wait()

        fg.meta_socket.close()

        fg.context.term()

        print("Done.")