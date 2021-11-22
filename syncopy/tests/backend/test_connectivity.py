# -*- coding: utf-8 -*-

import numpy as np
import matplotlib.pyplot as ppl
from syncopy.connectivity import ST_compRoutines as stCR
from syncopy.connectivity import AV_compRoutines as avCR
from syncopy.connectivity.wilson_sf import wilson_sf, regularize_csd


def test_coherence():

    '''
    Tests the normalization cF to 
    arrive at the coherence given
    a trial averaged csd
    '''

    nSamples = 1001
    fs = 1000
    tvec = np.arange(nSamples) / fs    
    harm_freq = 40
    phase_shifts = np.array([0, np.pi / 2, np.pi])

    nTrials = 50

    # shape is (1, nFreq, nChannel, nChannel)
    nFreq = nSamples // 2 + 1
    nChannel = len(phase_shifts)
    avCSD = np.zeros((1, nFreq, nChannel, nChannel), dtype=np.complex64)
    
    for i in range(nTrials):
    
        # 1 phase phase shifted harmonics + white noise + constant, SNR = 1
        trl_dat = [10 + np.cos(harm_freq * 2 * np. pi * tvec + ps)
                   for ps in phase_shifts] 
        trl_dat = np.array(trl_dat).T
        trl_dat = np.array(trl_dat) + np.random.randn(nSamples, len(phase_shifts))

        # process every trial individually
        CSD, freqs = stCR.cross_spectra_cF(trl_dat, fs,
                                           polyremoval=1,
                                           taper='hann',
                                           norm=False, # this is important!
                                           fullOutput=True)

        assert avCSD.shape == CSD.shape
        avCSD += CSD

    # this is the result of the 
    avCSD /= nTrials
    
    # perform the normalisation on the trial averaged csd's
    Cij = avCR.normalize_csd_cF(avCSD)

    # output has shape (1, nFreq, nChannels, nChannels)
    assert Cij.shape == avCSD.shape

    # coherence between channel 0 and 1
    coh = Cij[0, :, 0, 1]

    fig, ax = ppl.subplots(figsize=(6,4), num=None)
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel('coherence')
    ax.set_ylim((-.02,1.05))
    ax.set_title('Trial average coherence,  SNR=1')

    assert ax.plot(freqs, coh, lw=1.5, alpha=0.8, c='cornflowerblue')

    # we test for the highest peak sitting at
    # the vicinity (± 5Hz) of one the harmonic
    peak_val = np.max(coh)
    peak_idx = np.argmax(coh)
    peak_freq = freqs[peak_idx]
    print(peak_freq, peak_val)
    assert harm_freq - 5 < peak_freq < harm_freq + 5

    # we test that the peak value
    # is at least 0.9 and max 1
    assert 0.9 < peak_val < 1

    # trial averaging should suppress the noise
    # we test that away from the harmonic the coherence is low
    level = 0.4
    assert np.all(coh[:peak_idx - 2] < level)
    assert np.all(coh[peak_idx + 2:] < level)

    
def test_csd():

    '''
    Tests multi-tapered single trial cross spectral
    densities
    '''

    nSamples = 1001
    fs = 1000
    tvec = np.arange(nSamples) / fs    
    harm_freq = 40
    phase_shifts = np.array([0, np.pi / 2, np.pi])

    # 1 phase phase shifted harmonics + white noise + constant, SNR = 1
    data = [10 + np.cos(harm_freq * 2 * np. pi * tvec + ps)
            for ps in phase_shifts] 
    data = np.array(data).T
    data = np.array(data) + np.random.randn(nSamples, len(phase_shifts))

    bw = 5 #Hz
    NW = nSamples * bw / (2 * fs)
    Kmax = int(2 * NW - 1) # multiple tapers for single trial coherence
    CSD, freqs = stCR.cross_spectra_cF(data, fs,
                                       polyremoval=1,
                                       taper='dpss',
                                       taper_opt={'Kmax' : Kmax, 'NW' : NW},
                                       norm=True,
                                       fullOutput=True)

    # output has shape (1, nFreq, nChannels, nChannels)
    assert CSD.shape == (1, len(freqs), data.shape[1], data.shape[1])

    # single trial coherence between channel 0 and 1
    coh = np.abs(CSD[0, :, 0, 1])

    fig, ax = ppl.subplots(figsize=(6,4), num=None)
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel('coherence')
    ax.set_ylim((-.02,1.05))
    ax.set_title(f'MTM coherence, {Kmax} tapers, SNR=1')

    assert ax.plot(freqs, coh, lw=1.5, alpha=0.8, c='cornflowerblue')

    # we test for the highest peak sitting at
    # the vicinity (± 5Hz) of one the harmonic
    peak_val = np.max(coh)
    peak_idx = np.argmax(coh)
    peak_freq = freqs[peak_idx]
    print(peak_freq, peak_val)
    assert harm_freq - 5 < peak_freq < harm_freq + 5

    # we test that the peak value
    # is at least 0.9 and max 1
    assert 0.9 < peak_val < 1


def test_cross_cov():

    nSamples = 1001
    fs = 1000        
    tvec = np.arange(nSamples) / fs
    
    cosine = np.cos(2 * np.pi * 30 * tvec)
    sine = np.sin(2 * np.pi * 30 * tvec)
    data = np.c_[cosine, sine]

    # output shape is (nLags x 1 x nChannels x nChannels)
    CC, lags = stCR.cross_covariance_cF(data, samplerate=fs, norm=True, fullOutput=True)

    # test for result is returned in the [0, np.ceil(nSamples / 2)] lag interval
    nLags = int(np.ceil(nSamples / 2))
    
    # output has shape (nLags, 1, nChannels, nChannels)
    assert CC.shape == (nLags, 1, data.shape[1], data.shape[1])
    
    # cross-correlation (normalized cross-covariance) between
    # cosine and sine analytically equals minus sine    
    assert np.all(CC[:, 0, 0, 1] + sine[:nLags] < 1e-5)


def test_wilson():

    '''
    Test Wilson's spectral matrix factorization.

    As the routine has relative error-checking
    inbuild, we just need to check for convergence.
    '''

    # --- create test data ---
    fs = 1000
    nChannels = 10
    nSamples = 1000
    f1, f2 = [30 , 40] # 30Hz and 60Hz
    data = np.zeros((nSamples, nChannels))
    for i in range(nChannels):
        # more phase diffusion in the 60Hz band    
        p1 = phase_evo(f1 * 2 * np.pi, eps=0.1, fs=fs, N=nSamples)
        p2 = phase_evo(f2 * 2 * np.pi, eps=0.35, fs=fs, N=nSamples)
        
        data[:, i] = np.cos(p1) + 2 * np.sin(p2) + .5 * np.random.randn(nSamples)
        
    # --- get the (single trial) CSD ---
    
    bw = 5 # 5Hz smoothing
    NW = bw * nSamples / (2 * fs)
    Kmax = int(2 * NW - 1) # optimal number of tapers

    CSD, freqs = stCR.cross_spectra_cF(data, fs,
                                       taper='dpss',
                                       taper_opt={'Kmax' : Kmax, 'NW' : NW},
                                       norm=False,
                                       fullOutput=True)
    # strip off singleton time axis
    CSD = CSD[0]

    # get CSD condition number, which is way too large!
    CN = np.linalg.cond(CSD).max()
    assert CN > 1e6

    # --- regularize CSD ---
    
    CSDreg, fac = regularize_csd(CSD, cond_max=1e6, nSteps=25)
    CNreg = np.linalg.cond(CSDreg).max()
    assert CNreg < 1e6
    # check that 'small' regularization factor is enough
    assert fac < 1e-5 
    
    # --- factorize CSD with Wilson's algorithm ---
    
    H, Sigma, conv = wilson_sf(CSDreg, rtol=1e-9)

    # converged - \Psi \Psi^* \approx CSD,
    # with relative error <= rtol?
    assert conv

    # reconstitute
    CSDfac = H @ Sigma @ H.conj().transpose(0, 2, 1)
    
    fig, ax = ppl.subplots(figsize=(6, 4))
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel(r'$|CSD_{ij}(f)|$')
    chan = nChannels // 2
    # show (real) auto-spectra 
    assert ax.plot(freqs, np.abs(CSD[:, chan, chan]),
                   '-o', label='original CSD', ms=3)
    assert ax.plot(freqs, np.abs(CSDreg[:, chan, chan]),
                   '-o', label='regularized CSD', ms=3)
    assert ax.plot(freqs, np.abs(CSDfac[:, chan, chan]),
                   '-o', label='factorized CSD', ms=3)
    ax.set_xlim((f1 - 5, f2 + 5))

    
# --- Helper routines ---
          
# noisy phase evolution -> phase diffusion
def phase_evo(omega0, eps, fs=1000, N=1000):
    wn = np.random.randn(N) 
    delta_ts = np.ones(N) * 1 / fs
    phase = np.cumsum(omega0 * delta_ts + eps * wn)
    return phase
