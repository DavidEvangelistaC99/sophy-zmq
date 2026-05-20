###---Frequency Modulation with SDR for the Sophy weather radar---###

import numpy as np
from scipy import signal
import matplotlib.pyplot as plt


"""
chirpMod Inputs
- A             # Amplitude (unit value)
- ipp           # IPP (seconds)  
- dc            # DC (percentage %)
- sr_tx         # Sample rate in transmission (MHz)
- sr_rx         # Sample rate in reception (MHz)
- fc            # Central frequency (Hz)
- bw            # Bandwidth (MHz)
- t_d           # Chirp delay time (us)
- window        # Window type "R", "K", "B"
                # window = "R": Rectangular window
                # window = "K": Kaiser window 70 dB
                # window = "B": Blackman window
- mode_f        # Used to work with frequency variation when sr_tx and sr_rx are different
                # mode_f = 0: Normal operation
                # mode_f = 1: Operation with frequency variation
- phi           # Phase angle (rad)

chirpMod Outputs
- chirp         # Array 
                # only the Chirp signal
- full_chirp    # Array 
                # the full Chirp signal (IPP)
"""


def chirpMod(A, ipp, dc, sr_tx, sr_rx, fc, bw, t_d = 0, window = 'R', mode_f = 0, phi = 0): 
    
    # Definition of the upper and lower frequencies
    f0_Hz = fc - bw/2.0
    f1_Hz = fc + bw/2.0

    # Calculation of Chirp time
    T_chirp = dc*(ipp)/100.0

    # Chirp rate in Hz/s
    k   = bw/T_chirp

    # Number of points for the duration of the Chirp
    n   = int(sr_tx*T_chirp)         	

    # Time array for the duration of the Chirp [0 ... Trep]
    t = np.linspace(0, T_chirp, n)

    if window == 'K':
      # Beta value for 70 dB attenuation
      beta = signal.kaiser_beta(70)
      B = A*signal.windows.kaiser(n, beta)
    else:
      if window == 'B':
        # Value 1.0 for Tukey window
        alpha = 1.0
        B = A*signal.windows.tukey(n, alpha)
      else:
        B = A

    # Instantaneous frequency f(t) = k.t+f0
    f = k*t + f0_Hz

    # Also: t = (f - f0_Hz)/k

    # Form of the Chirp signal: A.exp(j.phi(t))
    #                           A.exp(j.phi(f))

    # Work with frequency variation (mode_f parameter)
    if mode_f == 1:
      
      r = int(sr_tx/sr_rx)
 
      f = f[::r]
      f = [i for i in f for _ in range(r)]
      f = np.array(f)

    # Instantaneous phase of the Chirp signal 
    # (integral of the instantaneous frequency)
    # phi = (k*t/2 + f0_Hz)*t

    # Considering t = (f - f0_Hz)/k
    # phi_f = (f/2.0 + f0_Hz/2.0)*(f - f0_Hz)/k
    phi_f = (t**2)*k/2 + t*f0_Hz

    # Instantaneous phase in rad
    phi_rad = 2*np.pi*phi_f 

    # Chirp-only signal generated
    chirp = B*np.exp(1j*(phi_rad + phi))

    # N: Total number of samples (IPP)
    N = n*100/dc

    # N_z: Number of leftover samples (equal to 0)
    N_z = N - n

    # Chirp signal with zeros to complete the IPP
    full_chirp = np.hstack((chirp, np.zeros(int(N_z))))
    
    # Chirp signal delay
    N_d = int(N*t_d/(ipp*1.0e6))

    # Full Chirp signal (IPP) generated
    full_chirp = np.roll(full_chirp, N_d)

    return chirp, full_chirp


# Function for the double Chirp pulse (according to reference article PX1000)
def chirpModUnion_1(ipp, 
                    sr_tx, 
                    sr_rx, 
                    A_1, 
                    A_2, 
                    dc_1, 
                    dc_2, 
                    fc_1, 
                    fc_2, 
                    bw_1, 
                    bw_2, 
                    t_d_, 
                    window_1, 
                    window_2):
    
    _, full_chirp_1 = chirpMod(A_1, 
                               ipp, 
                               dc_1, 
                               sr_tx, 
                               sr_rx, 
                               fc_1, 
                               bw_1, 
                               t_d = t_d_, 
                               window = window_1, 
                               mode_f = 0)
    _, full_chirp_2 = chirpMod(A_2, 
                               ipp, 
                               dc_2, 
                               sr_tx, 
                               sr_rx, 
                               fc_2, 
                               bw_2, 
                               t_d = t_d_ + dc_1*ipp*(1e6/1e2), 
                               window = window_2, 
                               mode_f = 0)
    full_chirp = np.array(full_chirp_1) + np.array(full_chirp_2)

    return full_chirp


# Function for the double Chirp pulse (according to the current CC transmission)
def chirpModUnion_2(ipp, 
                    sr_tx, 
                    sr_rx, 
                    A_1, 
                    A_2, 
                    dc_1, 
                    dc_2, 
                    fc_1, 
                    fc_2, 
                    bw_1, 
                    bw_2, 
                    t_d_, 
                    window_1, 
                    window_2, 
                    rep_1 = 1, 
                    rep_2 = 1):
    
    _, full_chirp_1 = chirpMod(A_1, 
                               ipp, 
                               dc_1, 
                               sr_tx, 
                               sr_rx, 
                               fc_1, 
                               bw_1, 
                               t_d = t_d_, 
                               window = window_1, 
                               mode_f = 0)
    _, full_chirp_2 = chirpMod(A_2, 
                               ipp, 
                               dc_2, 
                               sr_tx, 
                               sr_rx, 
                               fc_2, 
                               bw_2, 
                               t_d = t_d_, 
                               window = window_2, 
                               mode_f = 0)

    full_chirp_1 = np.tile(full_chirp_1, int(rep_1))
    full_chirp_2 = np.tile(full_chirp_2, int(rep_2))
    full_chirp = np.concatenate((full_chirp_1, full_chirp_2))

    return full_chirp


# Example
if __name__ == "__main__":
  
  A = 1.0
  ipp = 400.0e-6
  dc = 12.0
  sr_tx = 20.0e6
  sr_rx = 2.5e6
  # The central frequency will define the Chirp sweep (ascending or descending)
  fc = 0.0e6
  bw = 1.0e6
  td_ = 5.2
  window_ = 'B'
  mode_f_ = 0
  phi_ = 0
  rep_ = 250.0

  chirp, full_chirp = chirpMod(A, 
                               ipp, 
                               dc, 
                               sr_tx, 
                               sr_rx, 
                               fc, 
                               bw, 
                               t_d = td_, 
                               window = window_, 
                               mode_f = mode_f_, 
                               phi = phi_)

  # chirpModUnion_1(ipp, sr_tx, sr_rx, A_1, A_2, dc_1, dc_2, fc_1, fc_2, bw_1, bw_2, t_d_, window_1, window_2)
  # full_chirp_1 = chirpModUnion_1(ipp, sr_tx, sr_rx, A, A, 12.0, 12.0, 0.0e6, 2.0e6, 1.0e6, 0.0e6, td_, 'B', 'R')
  
  # chirpModUnion_2(ipp, sr_tx, sr_rx, A_1, A_2, dc_1, dc_2, fc_1, fc_2, bw_1, bw_2, t_d_, window_1, window_2, rep_1, rep_2)
  # full_chirp_2 = chirpModUnion_2(ipp, sr_rx, sr_rx, A, A/2.0, dc, 1.0, fc, fc, bw, bw, td_, window_, 'R', rep_, rep_)
  
  t = [i for i in range(len(chirp))] 
  plt.plot(t, np.real(chirp)) 
  plt.plot(t, np.imag(chirp)) 
  plt.show()
