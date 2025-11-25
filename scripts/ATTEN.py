import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy.fft import fft, fftfreq, fftshift

class RiseTimeAnalyzer:
    def __init__(self, freq=10e6, rise_time=10e-12, amplitude=0.5, sample_rate=200e9, duration=2e-6):
        """
        Initialize signal parameters for rise time analysis
        
        Parameters:
        freq: Signal frequency (Hz)
        rise_time: Rise time (s)
        amplitude: High level amplitude (V)
        sample_rate: Sampling rate (Hz)
        duration: Signal duration (s)
        """
        self.freq = freq
        self.rise_time = rise_time
        self.amplitude = amplitude
        self.sample_rate = sample_rate
        self.duration = duration
        
        # Generate time axis
        self.t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Calculate theoretical bandwidth (BW ≈ 0.35/Tr)
        self.theoretical_bw = 0.35 / rise_time
        
    def generate_signal_with_rise_time(self):
        """Generate square wave signal with specified rise time"""
        # Generate ideal square wave
        square_wave = self.amplitude * (signal.square(2 * np.pi * self.freq * self.t, duty=0.5) + 1) / 2
        
        # Apply rise time using first-order low-pass filter approximation
        alpha = 1 / (self.rise_time * self.sample_rate)
        filtered_wave = np.zeros_like(square_wave)
        filtered_wave[0] = square_wave[0]
        
        for i in range(1, len(square_wave)):
            filtered_wave[i] = alpha * square_wave[i] + (1 - alpha) * filtered_wave[i-1]
        
        return filtered_wave
    
    def calculate_power_spectrum(self, signal_data, window='hann'):
        """Calculate power spectrum in dB"""
        n = len(signal_data)
        
        # Apply window function to reduce spectral leakage
        if window == 'hann':
            window_func = np.hanning(n)
        elif window == 'hamming':
            window_func = np.hamming(n)
        elif window == 'blackman':
            window_func = np.blackman(n)
        else:
            window_func = np.ones(n)
        
        windowed_signal = signal_data * window_func
        
        # Calculate FFT
        fft_result = fft(windowed_signal)
        
        # Calculate power spectrum in dB
        power_spectrum = np.abs(fft_result)**2 / n
        power_spectrum_db = 10 * np.log10(power_spectrum + 1e-12)  # Avoid log(0)
        
        # Calculate frequency axis
        freqs = fftfreq(n, 1/self.sample_rate)
        
        # Return only positive frequencies
        positive_freq_idx = freqs >= 0
        return freqs[positive_freq_idx], power_spectrum_db[positive_freq_idx]
    
    def analyze_power_rolloff(self, plot_results=True):
        """Analyze power rolloff characteristics"""
        print(f"Signal Parameters:")
        print(f"  Frequency: {self.freq/1e6:.1f} MHz")
        print(f"  Rise Time: {self.rise_time*1e12:.1f} ps")
        print(f"  Amplitude: {self.amplitude*1000:.1f} mV")
        print(f"  Theoretical Bandwidth: {self.theoretical_bw/1e9:.2f} GHz")
        
        # Generate signal
        signal_data = self.generate_signal_with_rise_time()
        
        # Calculate power spectrum
        freqs, power_db = self.calculate_power_spectrum(signal_data)
        
        # Limit to DC-50GHz range
        freq_mask = freqs <= 50e9
        analysis_freqs = freqs[freq_mask]
        analysis_power = power_db[freq_mask]
        
        # Find key frequency points
        fundamental_idx = np.argmin(np.abs(analysis_freqs - self.freq))
        fundamental_power = analysis_power[fundamental_idx]
        
        # Find -3dB point
        three_db_point = fundamental_power - 3
        three_db_idx = np.argmin(np.abs(analysis_power - three_db_point))
        three_db_freq = analysis_freqs[three_db_idx]
        
        # Find -6dB point
        six_db_point = fundamental_power - 6
        six_db_idx = np.argmin(np.abs(analysis_power - six_db_point))
        six_db_freq = analysis_freqs[six_db_idx]
        
        # Find -20dB point
        twenty_db_point = fundamental_power - 20
        twenty_db_idx = np.argmin(np.abs(analysis_power - twenty_db_point))
        twenty_db_freq = analysis_freqs[twenty_db_idx]
        
        if plot_results:
            self.plot_power_rolloff(analysis_freqs, analysis_power, fundamental_power,
                                  three_db_freq, six_db_freq, twenty_db_freq)
        
        return {
            'frequencies': analysis_freqs,
            'power_spectrum': analysis_power,
            'fundamental_power': fundamental_power,
            'three_db_freq': three_db_freq,
            'six_db_freq': six_db_freq,
            'twenty_db_freq': twenty_db_freq,
            'theoretical_bw': self.theoretical_bw
        }
    
    def plot_power_rolloff(self, freqs, power_db, fundamental_power,
                          three_db_freq, six_db_freq, twenty_db_freq):
        """Plot power rolloff curve"""
        plt.figure(figsize=(12, 8))
        
        # Main power rolloff curve
        plt.semilogx(freqs/1e9, power_db, 'b-', linewidth=2.5, label='Power Spectrum')
        
        # Mark key points
        plt.axvline(three_db_freq/1e9, color='r', linestyle='--', alpha=0.7, 
                   label=f'-3dB Point: {three_db_freq/1e9:.2f} GHz')
        plt.axvline(six_db_freq/1e9, color='g', linestyle='--', alpha=0.7,
                   label=f'-6dB Point: {six_db_freq/1e9:.2f} GHz')
        plt.axvline(twenty_db_freq/1e9, color='m', linestyle='--', alpha=0.7,
                   label=f'-20dB Point: {twenty_db_freq/1e9:.2f} GHz')
        
        # Mark theoretical bandwidth
        plt.axvline(self.theoretical_bw/1e9, color='orange', linestyle=':', alpha=0.7,
                   label=f'Theoretical BW (0.35/Tr): {self.theoretical_bw/1e9:.2f} GHz')
        
        # Add horizontal lines for reference
        plt.axhline(fundamental_power, color='k', linestyle=':', alpha=0.5, label='Fundamental Level')
        plt.axhline(fundamental_power - 3, color='r', linestyle=':', alpha=0.3)
        plt.axhline(fundamental_power - 6, color='g', linestyle=':', alpha=0.3)
        plt.axhline(fundamental_power - 20, color='m', linestyle=':', alpha=0.3)
        
        # Formatting
        plt.xlabel('Frequency (GHz)', fontsize=12)
        plt.ylabel('Power (dB)', fontsize=12)
        plt.title(f'Power Rolloff Curve: {self.rise_time*1e12:.1f}ps Rise Time Signal\n(DC to 50 GHz)', fontsize=14)
        plt.grid(True, which='both', alpha=0.3)
        plt.legend(fontsize=10)
        plt.xlim(0.01, 50)  # From 10MHz to 50GHz
        
        # Add text annotations
        plt.text(0.02, fundamental_power + 2, f'Fundamental: {self.freq/1e6:.1f}MHz', 
                fontsize=10, bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))
        plt.text(three_db_freq/1e9 + 1, fundamental_power - 10, f'-3dB: {three_db_freq/1e9:.2f}GHz', 
                fontsize=9, bbox=dict(boxstyle="round,pad=0.2", fc="red", alpha=0.3))
        plt.text(six_db_freq/1e9 + 1, fundamental_power - 15, f'-6dB: {six_db_freq/1e9:.2f}GHz', 
                fontsize=9, bbox=dict(boxstyle="round,pad=0.2", fc="green", alpha=0.3))
        
        plt.tight_layout()
        plt.show()

# Main analysis function
def analyze_rise_time_power_rolloff():
    """Main function to analyze power rolloff for 10ps rise time signal"""
    print("="*70)
    print("POWER ROLLOFF ANALYSIS FOR 10ps RISE TIME SIGNAL")
    print("="*70)
    
    # Create analyzer with 10ps rise time
    analyzer = RiseTimeAnalyzer(
        freq=10e6,           # 10MHz
        rise_time=10e-12,    # 10ps rise time
        amplitude=0.5,       # 500mV high level
        sample_rate=200e9,   # 200GHz sampling rate
        duration=2e-6        # 2μs duration
    )
    
    # Analyze power rolloff
    results = analyzer.analyze_power_rolloff()
    
    # Print detailed results
    print(f"\nDetailed Analysis Results:")
    print(f"Fundamental Frequency (10MHz) Power: {results['fundamental_power']:.1f} dB")
    print(f"-3dB Point: {results['three_db_freq']/1e9:.2f} GHz")
    print(f"-6dB Point: {results['six_db_freq']/1e9:.2f} GHz")
    print(f"-20dB Point: {results['twenty_db_freq']/1e9:.2f} GHz")
    print(f"Theoretical Bandwidth (0.35/Tr): {results['theoretical_bw']/1e9:.2f} GHz")
    
    # Calculate rolloff rates
    freq_range_3db = results['three_db_freq'] - 10e6
    power_drop_3db = 3
    rolloff_rate_3db = power_drop_3db / (freq_range_3db/1e9)  # dB per GHz
    
    freq_range_6db = results['six_db_freq'] - results['three_db_freq']
    power_drop_6db = 3
    rolloff_rate_6db = power_drop_6db / (freq_range_6db/1e9)  # dB per GHz
    
    print(f"\nRolloff Rates:")
    print(f"From DC to -3dB point: {rolloff_rate_3db:.2f} dB/GHz")
    print(f"From -3dB to -6dB point: {rolloff_rate_6db:.2f} dB/GHz")
    
    return results

# Function to compare different rise times
def compare_rise_times():
    """Compare power rolloff for different rise times"""
    rise_times = [5e-12, 10e-12, 20e-12, 50e-12]  # 5ps, 10ps, 20ps, 50ps
    
    plt.figure(figsize=(12, 8))
    
    for rt in rise_times:
        analyzer = RiseTimeAnalyzer(
            freq=10e6,
            rise_time=rt,
            amplitude=0.5,
            sample_rate=200e9,
            duration=2e-6
        )
        
        signal_data = analyzer.generate_signal_with_rise_time()
        freqs, power_db = analyzer.calculate_power_spectrum(signal_data)
        
        # Limit to DC-50GHz
        freq_mask = freqs <= 50e9
        analysis_freqs = freqs[freq_mask]
        analysis_power = power_db[freq_mask]
        
        # Normalize to fundamental
        fundamental_idx = np.argmin(np.abs(analysis_freqs - 10e6))
        normalized_power = analysis_power - analysis_power[fundamental_idx]
        
        plt.semilogx(analysis_freqs/1e9, normalized_power, linewidth=2, 
                    label=f'{rt*1e12:.0f}ps Rise Time')
    
    plt.xlabel('Frequency (GHz)', fontsize=12)
    plt.ylabel('Normalized Power (dB)', fontsize=12)
    plt.title('Power Rolloff Comparison for Different Rise Times\n(DC to 50 GHz)', fontsize=14)
    plt.grid(True, which='both', alpha=0.3)
    plt.legend(fontsize=10)
    plt.xlim(0.01, 50)
    
    # Add -3dB reference line
    plt.axhline(-3, color='k', linestyle='--', alpha=0.5, label='-3dB Reference')
    
    plt.tight_layout()
    plt.show()

# Function to analyze time domain characteristics
def analyze_time_domain():
    """Analyze time domain characteristics of the rise time"""
    analyzer = RiseTimeAnalyzer(
        freq=10e6,
        rise_time=10e-12,
        amplitude=0.5,
        sample_rate=200e9,
        duration=2e-6
    )
    
    signal_data = analyzer.generate_signal_with_rise_time()
    
    # Find a rising edge
    rising_edge_start = np.argmax(signal_data > 0.1 * analyzer.amplitude)
    # Extract 200ps around the rising edge
    points_200ps = int(200e-12 * analyzer.sample_rate)
    edge_start = max(0, rising_edge_start - points_200ps//4)
    edge_end = min(len(signal_data), rising_edge_start + 3*points_200ps//4)
    
    edge_time = analyzer.t[edge_start:edge_end] * 1e12  # Convert to ps
    edge_signal = signal_data[edge_start:edge_end] * 1000  # Convert to mV
    
    plt.figure(figsize=(10, 6))
    plt.plot(edge_time, edge_signal, 'b-', linewidth=2.5, label='Signal')
    
    # Mark 10%-90% points for rise time measurement
    v10 = 0.1 * analyzer.amplitude * 1000
    v90 = 0.9 * analyzer.amplitude * 1000
    
    idx_10 = np.argmax(edge_signal > v10)
    idx_90 = np.argmax(edge_signal > v90)
    
    rise_time_measured = (edge_time[idx_90] - edge_time[idx_10])
    
    plt.axhline(v10, color='r', linestyle='--', alpha=0.7, label=f'10% Level ({v10:.1f}mV)')
    plt.axhline(v90, color='g', linestyle='--', alpha=0.7, label=f'90% Level ({v90:.1f}mV)')
    plt.axvline(edge_time[idx_10], color='r', linestyle=':', alpha=0.5)
    plt.axvline(edge_time[idx_90], color='g', linestyle=':', alpha=0.5)
    
    plt.xlabel('Time (ps)', fontsize=12)
    plt.ylabel('Amplitude (mV)', fontsize=12)
    plt.title(f'Rising Edge Detail: {analyzer.rise_time*1e12:.1f}ps Rise Time\n(Measured: {rise_time_measured:.1f}ps)', fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=10)
    
    plt.tight_layout()
    plt.show()
    
    print(f"Specified Rise Time: {analyzer.rise_time*1e12:.1f} ps")
    print(f"Measured Rise Time (10%-90%): {rise_time_measured:.1f} ps")

# Run the main analysis
if __name__ == "__main__":
    # Main power rolloff analysis
    results = analyze_rise_time_power_rolloff()
    
    # Uncomment to run additional analyses
    print("\n" + "="*70)
    print("ADDITIONAL ANALYSES")
    print("="*70)
    
    # Compare different rise times
    compare_rise_times()
    
    # Analyze time domain characteristics
    analyze_time_domain()
