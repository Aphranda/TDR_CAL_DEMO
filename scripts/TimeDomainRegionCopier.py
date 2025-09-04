import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

class DataRegionTransformer:
    def __init__(self):
        self.original_data = None
        self.time_data = None
        self.modified_data = None
        self.df = None
        
    def load_csv(self, file_path):
        """
        Load CSV file and process time series data
        """
        try:
            self.df = pd.read_csv(file_path)
            self.time_data = self.df['Time(us)'].values
            self.original_data = self.df['Differential_Amplitude'].values
            self.modified_data = self.original_data.copy()
            
            print(f"Successfully loaded data: {len(self.original_data)} data points")
            print(f"Time range: {self.time_data[0]:.3f} us to {self.time_data[-1]:.3f} us")
            return True
            
        except Exception as e:
            print(f"Failed to load CSV file: {e}")
            return False
    
    def find_time_indices(self, start_time_us, end_time_us):
        """
        Find corresponding indices based on time (us)
        """
        if self.time_data is None:
            raise ValueError("Time data not loaded")
        
        # Find the closest time indices
        start_idx = np.argmin(np.abs(self.time_data - start_time_us))
        end_idx = np.argmin(np.abs(self.time_data - end_time_us))
        
        print(f"Time {start_time_us} us corresponds to index: {start_idx}")
        print(f"Time {end_time_us} us corresponds to index: {end_idx}")
        
        return start_idx, end_idx
    
    def copy_region_by_time(self, source_start_time, source_end_time, 
                          target_start_time, target_end_time):
        """
        Directly copy source region to target region without any processing
        """
        if self.original_data is None:
            raise ValueError("Please load data first")
            
        # Find time corresponding indices
        source_start_idx, source_end_idx = self.find_time_indices(source_start_time, source_end_time)
        target_start_idx, target_end_idx = self.find_time_indices(target_start_time, target_end_time)
        
        source_data = self.original_data[source_start_idx:source_end_idx]
        target_data = self.original_data[target_start_idx:target_end_idx]
        
        print(f"Source region data points: {len(source_data)}")
        print(f"Target region data points: {len(target_data)}")
        
        # Direct copy without any processing
        if len(source_data) == len(target_data):
            self.modified_data[target_start_idx:target_end_idx] = source_data
        else:
            # If lengths don't match, use the shorter length
            min_length = min(len(source_data), len(target_data))
            self.modified_data[target_start_idx:target_start_idx + min_length] = source_data[:min_length]
            print(f"Warning: Region lengths don't match. Using first {min_length} data points.")
        
        return source_start_idx, source_end_idx, target_start_idx, target_end_idx
    
    def save_modified_csv(self, output_path):
        """Save modified data to CSV file (overwriting second column)"""
        if self.modified_data is not None and self.df is not None:
            # Create a copy of the original dataframe and overwrite the second column
            modified_df = self.df.copy()
            modified_df['Differential_Amplitude'] = self.modified_data
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            modified_df.to_csv(output_path, index=False)
            print(f"Modified data saved to: {output_path}")
            return output_path
        return None
    
    def plot_target_region_comparison(self, source_range, target_range, save_path=None):
        """
        Plot detailed comparison of target region before and after modification
        """
        source_start_idx, source_end_idx, target_start_idx, target_end_idx = source_range + target_range
        
        # Get the data for comparison
        source_data = self.original_data[source_start_idx:source_end_idx]
        target_original = self.original_data[target_start_idx:target_end_idx]
        target_modified = self.modified_data[target_start_idx:target_end_idx]
        target_time = self.time_data[target_start_idx:target_end_idx]
        
        # Create figure with multiple subplots
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Target Region Detailed Comparison', fontsize=16, fontweight='bold')
        
        # 1. Time domain comparison
        axes[0, 0].plot(target_time, target_original, 'b-', label='Original Target', linewidth=2)
        axes[0, 0].plot(target_time, target_modified, 'r-', label='Modified Target', linewidth=2)
        axes[0, 0].set_title('Time Domain Comparison')
        axes[0, 0].set_xlabel('Time (us)')
        axes[0, 0].set_ylabel('Differential Amplitude')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Difference plot
        difference = target_modified - target_original
        axes[0, 1].plot(target_time, difference, 'g-', label='Difference (Modified - Original)', linewidth=2)
        axes[0, 1].axhline(y=0, color='k', linestyle='--', alpha=0.5)
        axes[0, 1].set_title('Difference Between Modified and Original')
        axes[0, 1].set_xlabel('Time (us)')
        axes[0, 1].set_ylabel('Amplitude Difference')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Source vs Modified Target comparison
        min_length = min(len(source_data), len(target_modified))
        comparison_time = np.arange(min_length)
        axes[1, 0].plot(comparison_time, source_data[:min_length], 'g-', label='Source Region', linewidth=2)
        axes[1, 0].plot(comparison_time, target_modified[:min_length], 'r-', label='Modified Target', linewidth=2)
        axes[1, 0].set_title('Source Region vs Modified Target')
        axes[1, 0].set_xlabel('Data Point Index')
        axes[1, 0].set_ylabel('Differential Amplitude')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Statistical comparison
        categories = ['Original Target', 'Modified Target', 'Source Region']
        means = [np.mean(target_original), np.mean(target_modified), np.mean(source_data)]
        stds = [np.std(target_original), np.std(target_modified), np.std(source_data)]
        
        x_pos = np.arange(len(categories))
        axes[1, 1].bar(x_pos, means, yerr=stds, alpha=0.7, capsize=5)
        axes[1, 1].set_title('Statistical Comparison')
        axes[1, 1].set_ylabel('Mean Amplitude')
        axes[1, 1].set_xticks(x_pos)
        axes[1, 1].set_xticklabels(categories, rotation=45)
        axes[1, 1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Target region comparison plot saved to: {save_path}")
        
        plt.show()
        
        # Print detailed statistics
        self._print_target_statistics(source_data, target_original, target_modified)
    
    def _print_target_statistics(self, source_data, target_original, target_modified):
        """Print detailed statistics for target region"""
        print("\n" + "="*60)
        print("TARGET REGION STATISTICAL ANALYSIS")
        print("="*60)
        
        print(f"\nSource Region:")
        print(f"  Data points: {len(source_data)}")
        print(f"  Mean: {np.mean(source_data):.4f}")
        print(f"  Std: {np.std(source_data):.4f}")
        print(f"  Min: {np.min(source_data):.4f}")
        print(f"  Max: {np.max(source_data):.4f}")
        
        print(f"\nTarget Region (Original):")
        print(f"  Data points: {len(target_original)}")
        print(f"  Mean: {np.mean(target_original):.4f}")
        print(f"  Std: {np.std(target_original):.4f}")
        print(f"  Min: {np.min(target_original):.4f}")
        print(f"  Max: {np.max(target_original):.4f}")
        
        print(f"\nTarget Region (Modified):")
        print(f"  Data points: {len(target_modified)}")
        print(f"  Mean: {np.mean(target_modified):.4f}")
        print(f"  Std: {np.std(target_modified):.4f}")
        print(f"  Min: {np.min(target_modified):.4f}")
        print(f"  Max: {np.max(target_modified):.4f}")
        
        # Calculate similarity metrics
        if len(source_data) == len(target_modified):
            mse = np.mean((source_data - target_modified) ** 2)
            mae = np.mean(np.abs(source_data - target_modified))
            correlation = np.corrcoef(source_data, target_modified)[0, 1]
            
            print(f"\nSimilarity Metrics:")
            print(f"  MSE: {mse:.6f}")
            print(f"  MAE: {mae:.6f}")
            print(f"  Correlation: {correlation:.6f}")
            
            if mse < 1e-10:
                print("  ✓ Perfect copy: Data matches exactly")
            else:
                print("  ⚠ Some differences detected")
    
    def plot_saved_file(self, file_path, source_range, target_range, save_plot_path=None):
        """Plot the saved CSV file"""
        try:
            # Load the saved file
            saved_df = pd.read_csv(file_path)
            saved_time = saved_df['Time(us)'].values
            saved_amplitude = saved_df['Differential_Amplitude'].values
            
            source_start_idx, source_end_idx, target_start_idx, target_end_idx = source_range + target_range
            
            plt.figure(figsize=(16, 10))
            
            # 1. Overall data comparison
            plt.subplot(2, 1, 1)
            plt.plot(self.time_data, self.original_data, 'b-', alpha=0.7, label='Original Data', linewidth=1)
            plt.plot(saved_time, saved_amplitude, 'r-', alpha=0.8, label='Modified Data (Saved File)', linewidth=1.5)
            plt.axvspan(self.time_data[source_start_idx], self.time_data[source_end_idx], 
                       alpha=0.2, color='green', label='Source Region')
            plt.axvspan(self.time_data[target_start_idx], self.time_data[target_end_idx], 
                       alpha=0.2, color='orange', label='Target Region')
            plt.title('Comparison: Original vs Modified Data (From Saved File)')
            plt.xlabel('Time (us)')
            plt.ylabel('Differential Amplitude')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            # 2. Target region zoomed comparison
            plt.subplot(2, 1, 2)
            mask = (saved_time >= saved_time[target_start_idx] - 1) & \
                   (saved_time <= saved_time[target_end_idx] + 1)
            time_subset = saved_time[mask]
            orig_subset = self.original_data[mask]
            saved_subset = saved_amplitude[mask]
            
            plt.plot(time_subset, orig_subset, 'b-o', alpha=0.7, label='Original Target Region', markersize=3)
            plt.plot(time_subset, saved_subset, 'r-s', alpha=0.8, label='Modified Target Region', markersize=3)
            plt.axvspan(saved_time[target_start_idx], saved_time[target_end_idx], 
                       alpha=0.2, color='orange')
            plt.title('Target Region Zoomed Comparison (From Saved File)')
            plt.xlabel('Time (us)')
            plt.ylabel('Differential Amplitude')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            if save_plot_path:
                os.makedirs(os.path.dirname(save_plot_path), exist_ok=True)
                plt.savefig(save_plot_path, dpi=300, bbox_inches='tight')
                print(f"Plot saved to: {save_plot_path}")
            
            plt.show()
            
        except Exception as e:
            print(f"Error plotting saved file: {e}")

# Usage example
def main():
    # Create transformer instance
    transformer = DataRegionTransformer()
    
    # Load CSV file
    input_file = 'data\\calibration\\Calibration_SOLT_DUT_Test_20250903_201458_P1P4\\Analysis_Summary_Processed_Only\\Time_Domain\\Diff_Time_Calbe_P1P4\\DUT_Measurement_step_8_DUT_Measurement_S21_processed_diff_time_domain copy.csv'
    success = transformer.load_csv(input_file)
    
    if success:
        # Define time ranges (microseconds)
        source_start_time = 0.020   # Source region start time (us)
        source_end_time = 0.0203    # Source region end time (us)
        target_start_time = 0.0246  # Target region start time (us)
        target_end_time = 0.0249    # Target region end time (us)
        
        # Perform direct copy
        ranges = transformer.copy_region_by_time(
            source_start_time, source_end_time,
            target_start_time, target_end_time
        )
        
        # Plot target region comparison
        transformer.plot_target_region_comparison(
            (ranges[0], ranges[1]),  # Source region range
            (ranges[2], ranges[3]),  # Target region range
            save_path='scripts\\temp\\target_region_comparison.png'
        )
        
        # Save modified data (overwriting second column)
        output_file = 'scripts\\temp\\modified_time_domain_data.csv'
        saved_file_path = transformer.save_modified_csv(output_file)
        
        if saved_file_path:
            # Plot the saved file
            transformer.plot_saved_file(
                saved_file_path,
                (ranges[0], ranges[1]),  # Source region range
                (ranges[2], ranges[3]),  # Target region range
                save_plot_path='scripts\\temp\\saved_file_comparison.png'
            )

if __name__ == "__main__":
    main()
