# scripts/plot_y_full_jitter_analysis.py

import numpy as np
import matplotlib.pyplot as plt
import os
import glob
import argparse
from pathlib import Path

def plot_y_full_jitter_analysis(data_dir=None, max_segments=50, save_plot=True, 
                               channel1_name="Channel1", channel2_name="Channel2"):
    """
    Plot overlapping y_full data for jitter analysis
    
    Parameters:
    - data_dir: Data directory path, auto-detect if None
    - max_segments: Maximum segments to display to avoid overcrowding
    - save_plot: Whether to save the plot
    - channel1_name: Custom name for first channel
    - channel2_name: Custom name for second channel
    """
    
    # Ensure data_dir is Path object
    if data_dir is None:
        possible_paths = [
            Path(__file__).parent.parent / "temp" / "y_full_jitter_analysis",
            Path(__file__).parent / "temp" / "y_full_jitter_analysis",
            Path.cwd() / "temp" / "y_full_jitter_analysis"
        ]
        
        for path in possible_paths:
            if path.exists():
                data_dir = path
                break
        else:
            print("Data directory not found, please specify data_dir parameter")
            return None, None
    elif isinstance(data_dir, str):
        data_dir = Path(data_dir)
    
    print(f"Using data directory: {data_dir}")
    
    # Check if directory exists
    if not data_dir.exists():
        print(f"Data directory does not exist: {data_dir}")
        return None, None
    
    # Load data - use Path objects
    adc1_file = data_dir / "rise_edge_alignment_y_full_data.npy"
    adc2_file = data_dir / "target_idx_alignment_y_full_data.npy"
    summary_file = data_dir / "summary.npz"
    
    if not adc1_file.exists() and not adc2_file.exists():
        print("No data files found")
        return None, None
    
    # Load summary info
    if summary_file.exists():
        try:
            summary = np.load(summary_file)
            ts_eff = float(summary['ts_eff'])
            success_count = int(summary['success_count'])
            adc1_count = int(summary['adc1_segment_count'])
            adc2_count = int(summary['adc2_segment_count'])
            timestamp = float(summary['timestamp'])
        except Exception as e:
            print(f"Failed to load summary file: {e}")
            ts_eff = 1e-9
            success_count = adc1_count = adc2_count = 0
    else:
        print("Summary file not found, using default parameters")
        ts_eff = 1e-9  # Default 1ns sampling interval
        success_count = adc1_count = adc2_count = 0
    
    # Create time axis
    def create_time_axis(data_length):
        return np.arange(data_length) * ts_eff * 1e6  # Convert to microseconds
    
    # Plot function
    def plot_channel_data(channel_data, channel_name, color, ax):
        if channel_data is None:
            return
        
        n_segments, n_points = channel_data.shape
        segments_to_plot = min(n_segments, max_segments)
        
        print(f"{channel_name}: {n_segments} segments, showing first {segments_to_plot}")
        
        time_axis = create_time_axis(n_points)
        
        # Plot all segments
        for i in range(segments_to_plot):
            alpha = 0.3 + 0.7 * (i / segments_to_plot)  # Gradient transparency
            ax.plot(time_axis, channel_data[i], color=color, alpha=alpha, linewidth=0.8)
        
        # Plot mean
        mean_data = np.mean(channel_data[:segments_to_plot], axis=0)
        ax.plot(time_axis, mean_data, color='black', linewidth=2, label=f'{channel_name} Mean')
        
        # Calculate and display jitter statistics
        if segments_to_plot > 1:
            std_data = np.std(channel_data[:segments_to_plot], axis=0)
            max_std = np.max(std_data)
            ax.text(0.02, 0.98, f'Max Std: {max_std:.4f}', 
                   transform=ax.transAxes, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Create figure
    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # Load and plot ADC1 data
    if adc1_file.exists():
        try:
            adc1_data = np.load(adc1_file)
            plot_channel_data(adc1_data, channel1_name, 'blue', axes[0])
            axes[0].set_ylabel('Amplitude')
            axes[0].set_title(f'{channel1_name} y_full Overlay - Jitter Analysis')
            axes[0].grid(True, alpha=0.3)
            axes[0].legend()
        except Exception as e:
            print(f"Failed to load {channel1_name} data: {e}")
            axes[0].text(0.5, 0.5, f'{channel1_name} data load failed: {e}', 
                        transform=axes[0].transAxes, ha='center', va='center', fontsize=12)
    else:
        axes[0].text(0.5, 0.5, f'No {channel1_name} data', 
                    transform=axes[0].transAxes, ha='center', va='center', fontsize=14)
    
    # Load and plot ADC2 data
    if adc2_file.exists():
        try:
            adc2_data = np.load(adc2_file)
            plot_channel_data(adc2_data, channel2_name, 'red', axes[1])
            axes[1].set_ylabel('Amplitude')
            axes[1].set_xlabel('Time (μs)')
            axes[1].set_title(f'{channel2_name} y_full Overlay - Jitter Analysis')
            axes[1].grid(True, alpha=0.3)
            axes[1].legend()
        except Exception as e:
            print(f"Failed to load {channel2_name} data: {e}")
            axes[1].text(0.5, 0.5, f'{channel2_name} data load failed: {e}', 
                        transform=axes[1].transAxes, ha='center', va='center', fontsize=12)
    else:
        axes[1].text(0.5, 0.5, f'No {channel2_name} data', 
                    transform=axes[1].transAxes, ha='center', va='center', fontsize=14)
    
    # Set overall title
    fig.suptitle(f'y_full Data Jitter Analysis - Total {success_count} Successful Segments', fontsize=16)
    
    plt.tight_layout()
    
    # Save plot
    if save_plot:
        try:
            plot_dir = data_dir / "plots"
            plot_dir.mkdir(exist_ok=True)
            plot_path = plot_dir / "y_full_jitter_analysis.png"
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            print(f"Plot saved to: {plot_path}")
        except Exception as e:
            print(f"Failed to save plot: {e}")
    
    plt.show()
    
    return fig, axes

def plot_individual_segments(data_dir=None, channel='adc1', segments_to_show=10, channel_name=None):
    """
    Plot detailed overlay view of individual segments
    
    Parameters:
    - data_dir: Data directory path
    - channel: Channel name ('adc1' or 'adc2')
    - segments_to_show: Number of segments to display (overlay)
    - channel_name: Custom name for the channel
    """
    
    # Set default channel name if not provided
    if channel_name is None:
        channel_name = channel.upper()
    
    # Ensure data_dir is Path object
    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "temp" / "y_full_jitter_analysis"
    elif isinstance(data_dir, str):
        data_dir = Path(data_dir)
    
    # Check if directory exists
    if not data_dir.exists():
        print(f"Data directory does not exist: {data_dir}")
        return
    
    data_file = data_dir / f"{channel}_y_full_data.npy"
    
    if not data_file.exists():
        print(f"No {channel} data file found")
        return
    
    try:
        data = np.load(data_file)
        n_segments, n_points = data.shape
        segments_to_show = min(segments_to_show, n_segments)
        
        # Load summary info to get sampling interval
        summary_file = data_dir / "summary.npz"
        if summary_file.exists():
            summary = np.load(summary_file)
            ts_eff = float(summary['ts_eff'])
        else:
            ts_eff = 1e-9
        
        time_axis = np.arange(n_points) * ts_eff * 1e6  # microseconds
        
        # Create figure - single plot for overlay
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Use different colors for each segment
        colors = plt.cm.viridis(np.linspace(0, 1, segments_to_show))
        
        # Plot all segments in overlay
        for i in range(segments_to_show):
            ax.plot(time_axis, data[i], color=colors[i], linewidth=1.5, 
                   label=f'Segment {i+1}', alpha=0.8)
        
        ax.set_ylabel('Amplitude')
        ax.set_xlabel('Time (μs)')
        ax.set_title(f'{channel_name} First {segments_to_show} Segments Overlay', fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=10)
        
        plt.tight_layout()
        
        # Save plot
        try:
            plot_dir = data_dir / "plots"
            plot_dir.mkdir(exist_ok=True)
            plot_path = plot_dir / f"{channel}_overlay_segments.png"
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            print(f"Overlay view saved to: {plot_path}")
        except Exception as e:
            print(f"Failed to save plot: {e}")
        
        plt.show()
        
    except Exception as e:
        print(f"Failed to plot overlay segments: {e}")

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description='Plot y_full data for jitter analysis')
    parser.add_argument('--data_dir', type=str, default=None, 
                       help='Data directory path (default: auto-detect)')
    parser.add_argument('--max_segments', type=int, default=50,
                       help='Maximum segments to display (default: 50)')
    parser.add_argument('--channel1', type=str, default="Channel1",
                       help='Custom name for first channel (default: Channel1)')
    parser.add_argument('--channel2', type=str, default="Channel2",
                       help='Custom name for second channel (default: Channel2)')
    parser.add_argument('--no_save', action='store_true',
                       help='Do not save plots (default: save plots)')
    
    args = parser.parse_args()
    
    try:
        # Plot overlay
        fig1, axes1 = plot_y_full_jitter_analysis(
            data_dir=r'D:\Work\TDR_CAL_DEMO\temp\y_full_jitter_analysis',
            max_segments=args.max_segments,
            save_plot=not args.no_save,
            channel1_name='rise_edge_alignment',
            channel2_name='target_idx_alignment'
        )
        
        # Plot detailed segments as overlay
        plot_individual_segments(
            data_dir=args.data_dir, 
            channel='rise_edge_alignment', 
            segments_to_show=10,
            channel_name='rise_edge_alignment'
        )
        plot_individual_segments(
            data_dir=args.data_dir, 
            channel='target_idx_alignment', 
            segments_to_show=10,
            channel_name='target_idx_alignment'
        )
    except Exception as e:
        print(f"Error executing plotting script: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
