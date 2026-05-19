#!/usr/bin/env python3

import zmq
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# CONFIG
# ============================================================

IQ_ADDRESS = "tcp://localhost:5555"
SAMPLE_TYPE = np.complex64

FFT_SIZE = 4096
PLOT_DECIMATION = 1


# ============================================================
# SETUP PLOTS
# ============================================================

plt.ion()

fig, (ax_time, ax_fft) = plt.subplots(2, 1, figsize=(10, 6))

# time domain
line_time, = ax_time.plot([], [])
ax_time.set_title("IQ Time Domain")
ax_time.set_ylim(-1, 1)
ax_time.set_xlim(0, 1024)

# freq domain
line_fft, = ax_fft.plot([], [])
ax_fft.set_title("FFT Spectrum")
ax_fft.set_xlim(-0.5, 0.5)


# ============================================================
# MAIN
# ============================================================

def main():

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(IQ_ADDRESS)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print("\n====================================")
    print("THOR RX - LIVE PLOT (TIME + FFT)")
    print("====================================")

    try:
        while True:

            msg = socket.recv()
            iq = np.frombuffer(msg, dtype=SAMPLE_TYPE)

            # ====================================================
            # TIME DOMAIN PLOT
            # ====================================================
            iq_plot = iq[::PLOT_DECIMATION]
            line_time.set_data(np.arange(len(iq_plot)), np.real(iq_plot))

            ax_time.set_xlim(0, len(iq_plot))

            # ====================================================
            # FFT
            # ====================================================
            if len(iq) >= FFT_SIZE:

                block = iq[:FFT_SIZE]

                spectrum = np.fft.fftshift(np.fft.fft(block))
                power = 20 * np.log10(np.abs(spectrum) + 1e-12)

                freq = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1/1e6))

                line_fft.set_data(freq, power)

                ax_fft.set_xlim(freq[0], freq[-1])
                ax_fft.set_ylim(np.min(power), np.max(power))

            # ====================================================
            # UPDATE PLOTS
            # ====================================================
            plt.pause(0.001)

    except KeyboardInterrupt:
        print("\nStopping plot receiver...")

    finally:
        socket.close()
        context.term()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()