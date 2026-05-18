#!/usr/bin/env python3

"""
Simulador tipo THOR usando:

GNU Radio
+
DigitalRF
+
Signal Source simulada

Arquitectura:

Signal Source
      ↓
DigitalRF Sink
      ↓
HDF5 + Metadata

Esto replica el comportamiento general de thor.py
pero SIN usar una USRP real.
"""

import os
import time
import numpy as np
from fractions import Fraction

from gnuradio import gr
from gnuradio import analog

import digital_rf
from gr_digital_rf import digital_rf_channel_sink


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

DATA_DIR = "thor_sim_data"

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

    def __init__(self):

        gr.top_block.__init__(self, "THOR Simulator")

        # ====================================================
        # SIGNAL SOURCE
        # ====================================================

        # Genera IQ complejos continuamente
        # reemplazando la USRP

        self.src = analog.sig_source_c(
            SAMPLE_RATE,
            analog.GR_SIN_WAVE,
            TONE_FREQ,
            AMPLITUDE,
            0,
        )

        # ====================================================
        # SAMPLE RATE FRACTION
        # ====================================================

        sr_frac = Fraction(SAMPLE_RATE)

        # ====================================================
        # START SAMPLE
        # ====================================================

        start_sample = int(time.time() * SAMPLE_RATE)

        # ====================================================
        # METADATA
        # ====================================================

        metadata = dict(

            # ------------------------------------------------
            # RECEIVER METADATA
            # ------------------------------------------------

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

            # ------------------------------------------------
            # PROCESSING METADATA
            # ------------------------------------------------

            processing=dict(

                channelizer_filter_taps=[],

                decimation=1,

                interpolation=1,

                resampling_filter_taps=[],

                scaling=1.0,
            ),

            # ------------------------------------------------
            # EXTRA
            # ------------------------------------------------

            simulation=dict(

                signal_type="complex_sine",

                tone_frequency=TONE_FREQ,

                amplitude=AMPLITUDE,
            )
        )

        # ====================================================
        # DIGITAL RF SINK
        # ====================================================

        self.dst = digital_rf_channel_sink(

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

        # ====================================================
        # CONNECTION
        # ====================================================

        self.connect(
            self.src,
            self.dst
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # CREAR DIRECTORIO
    # --------------------------------------------------------

    os.makedirs(DATA_DIR, exist_ok=True)

    # --------------------------------------------------------
    # CREAR FLOWGRAPH
    # --------------------------------------------------------

    fg = ThorSimulator()

    print("\n====================================")
    print("THOR SIMULATOR STARTED")
    print("====================================")

    print(f"Sample Rate : {SAMPLE_RATE}")
    print(f"Center Freq : {CENTER_FREQ}")
    print(f"Tone Freq   : {TONE_FREQ}")

    print("\nWriting DigitalRF dataset...")
    print(f"Output dir: {DATA_DIR}")

    # --------------------------------------------------------
    # START FLOWGRAPH
    # --------------------------------------------------------

    fg.start()

    try:

        time.sleep(RUN_TIME_SECONDS)

    except KeyboardInterrupt:

        pass

    finally:

        print("\nStopping flowgraph...")

        fg.stop()
        fg.wait()

        print("Done.")
