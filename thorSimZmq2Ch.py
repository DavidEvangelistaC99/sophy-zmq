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

import modFreq
import threading

import matplotlib.pyplot as plt

# ============================================================
# CONFIG
# ============================================================

DATA_DIR = "/home/idi/Documents/DATA/SIN@2026-01-21T00-00-01"

SAMPLE_RATE = 2_500_000

CENTER_FREQ_CH0 = 70_312_500
CENTER_FREQ_CH1 = 70_312_500

UUID_STR = "thor-simulator"

RUN_TIME_SECONDS = 120

ENABLE_ZMQ = 1
ENABLE_DIGITAL_RF = 0

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
        "amplitude": 1.0,
        "center_freq": CENTER_FREQ_CH0,
        "iq_port": 5555,
    }
}

'''
CHANNELS = {

    "ch0": {
        "tone": 100_000,
        "amplitude": 1.0,
        "center_freq": CENTER_FREQ_CH0,
        "iq_port": 5555,
    },

    "ch1": {
        "tone": 200_000,
        "amplitude": 1.0,
        "center_freq": CENTER_FREQ_CH1,
        "iq_port": 5557,
    }
}
'''

# ============================================================
# FLOWGRAPH
# ============================================================

class ThorSimulator(gr.top_block):

    def metadata_loop(self):

        while True:

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

            time.sleep(1)

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

            # ================================================
            # PULSED SIGNAL PARAMETERS
            # ================================================

            A = 10000.0 # 5000.0
            ipp = 400.0e-6
            dc = 12.0 # 12.0
            sr_tx = 20.0e6
            sr_rx = 2.5e6
            # The central frequency will define the Chirp sweep (ascending or descending)
            fc = 0.0e6 # 0.0e6
            bw = 1.0e6 # 1.0e6
            td_ = 5.2
            window_ = 'R' # 'B'
            mode_f_ = 0
            phi_ = 0
            rep_ = 250.0

            # ================================================
            # GENERATE ONE IPP
            # ================================================

            _, full_chirp = modFreq.chirpMod(A, 
                                            ipp, 
                                            dc, 
                                            sr_rx, 
                                            sr_rx, 
                                            fc, 
                                            bw, 
                                            t_d = td_, 
                                            window = window_, 
                                            mode_f = mode_f_, 
                                            phi = phi_)

            
            # =================================================
            # NOISE POWER
            # =================================================

            #noise_power = 3.0

            # =================================================
            # COMPLEX GAUSSIAN NOISE
            # =================================================
            '''
            noise = (
                np.random.randn(len(full_chirp))
                +
                1j * np.random.randn(len(full_chirp))
            )

            noise = noise.astype(np.complex64)
            '''

            # =================================================
            # SCALE NOISE
            # =================================================

            #noise *= noise_power

            signal_power = np.mean(np.abs(full_chirp)**2)

            snr_db = 55   # prueba 30, 25, 20, 15 dB

            noise_power = signal_power / (10**(snr_db/10))

            noise = (
                np.random.randn(len(full_chirp))
                + 1j*np.random.randn(len(full_chirp))
            ).astype(np.complex64)

            noise *= np.sqrt(noise_power/2)

            #full_chirp_noisy = full_chirp + noise

            # =================================================
            # ADD NOISE TO CHIRP
            # =================================================

            full_chirp_noisy = full_chirp + noise

            # header = 9999 + 9999j
            # full_chirp[0] = header

            profile_len = len(full_chirp_noisy)
            print(f"Profile length = {profile_len} samples")

            print("len(full_chirp) =", len(full_chirp))

            pulse = np.abs(full_chirp)

            peak = np.argmax(pulse)

            print("peak =", peak)

            #plot_iq_signal( full_chirp_noisy,
            #                SAMPLE_RATE,
            #                title=ch_name
            #                )


            # =================================================
            # GENERATE MANY PROFILES WITH RANDOM DELAY
            # =================================================

            N_PROFILES = 1000

            profiles = []

            for _ in range(N_PROFILES):

                shift = np.random.randint(0, 2+1)   # 0 a 20 bins

                profile = np.zeros_like(full_chirp_noisy)

                if shift > 0:
                    profile[shift:] = full_chirp_noisy[:-shift]
                else:
                    profile[:] = full_chirp_noisy

                profiles.append(profile)

            tx_data = np.concatenate(profiles)

            # ================================================
            # GNU RADIO VECTOR SOURCE
            # ================================================

            src = blocks.vector_source_c(
                tx_data.tolist(),
                #full_chirp_noisy.tolist(),
                # full_chirp.tolist(),
                repeat=True
            )
            
            stream_to_vector = blocks.stream_to_vector(
                gr.sizeof_gr_complex,
                profile_len
            )
            

            # ================================================
            # METADATA
            # ================================================

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

            # -================================================
            # CHANNEL DIRECTORY
            # ================================================

            if ENABLE_DIGITAL_RF:

                channel_dir = os.path.join(
                    DATA_DIR,
                    "rawdata",
                    ch_name
                )

                os.makedirs(channel_dir, exist_ok=True)

            # ================================================
            # DIGITAL RF SINK
            # ================================================

            drf = None

            if ENABLE_DIGITAL_RF:

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

            # ================================================
            # ZMQ IQ STREAM
            # ================================================

            zmq_sink = zeromq.pub_sink(

                itemsize=gr.sizeof_gr_complex,
                vlen=profile_len,
                address=f"tcp://*:{cfg['iq_port']}",
                timeout=100,
                pass_tags=False,
                hwm=10,
            )

            # ================================================
            # CONNECTIONS
            # ================================================

            if ENABLE_DIGITAL_RF:
                self.connect(src, drf)

            if ENABLE_ZMQ:
                #self.connect(src, zmq_sink)
                self.connect(src, stream_to_vector)
                self.connect(stream_to_vector, zmq_sink)

            # ================================================
            # SAVE REFERENCES
            # ================================================

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
        # START METADATA THREAD
        # ====================================================

        print("\n[ZMQ] Starting metadata publisher thread...")

        self.meta_thread = threading.Thread(
            target=self.metadata_loop,
            daemon=True
        )

        self.meta_thread.start()


        # ============================================================
        # MAIN
        # ============================================================

def plot_iq_signal(iq_data, sample_rate, title="IQ Signal"):

    # ==========================================
    # TAKE SMALL WINDOW
    # ==========================================

    N = min(5000, len(iq_data))
    # N = 5000

    iq = iq_data[:N]

    t = np.arange(N) / sample_rate

    # ==========================================
    # TIME DOMAIN
    # ==========================================

    plt.figure(figsize=(12,8))

    plt.subplot(3,1,1)

    plt.plot(t, np.real(iq), label="I")
    plt.plot(t, np.imag(iq), label="Q")

    plt.title(f"{title} - Time Domain")

    plt.xlabel("Time [s]")
    plt.ylabel("Amplitude")

    plt.legend()

    # ==========================================
    # CONSTELLATION
    # ==========================================

    plt.subplot(3,1,2)

    plt.scatter(
        np.real(iq),
        np.imag(iq),
        s=1
    )

    plt.title("IQ Constellation")

    plt.xlabel("I")
    plt.ylabel("Q")

    plt.axis("equal")

    # ==========================================
    # FFT
    # ==========================================

    plt.subplot(3,1,3)

    fft_data = np.fft.fftshift(np.fft.fft(iq))

    freqs = np.fft.fftshift(
        np.fft.fftfreq(len(iq), d=1/sample_rate)
    )

    power = 20*np.log10(np.abs(fft_data) + 1e-12)

    plt.plot(freqs/1e6, power)

    plt.title("Spectrum")

    plt.xlabel("Frequency [MHz]")
    plt.ylabel("Power [dB]")

    plt.tight_layout()

    plt.show()


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
    
    '''
    print("\nMetadata ZMQ : tcp://localhost:5556")
    print("\nStarting flowgraph...\n")

    fg.start()
    '''

    
    # ============================================================
    # CONTROL SOCKET
    # ============================================================

    if ENABLE_ZMQ:

        CTRL_ADDR = "tcp://*:6000"

        ctrl_socket = fg.context.socket(zmq.REP)

        ctrl_socket.bind(CTRL_ADDR)

        print(f"\n[CTRL] Waiting RX READY on {CTRL_ADDR} ...")

        msg = ctrl_socket.recv()

        print(f"[CTRL] RX says: {msg.decode()}")

        ctrl_socket.send(b"START")

        time.sleep(1)

        print("\n[CTRL] Starting synchronized flowgraph...\n")

        fg.start()

    else:

        print("\n[CTRL] ZMQ disabled. Starting flowgraph immediately...\n")

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