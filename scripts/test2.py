import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import make_interp_spline

class HollowRotaryPlatform:
    def __init__(self):
        # Platform parameters
        self.outer_radius = 0.5  # Outer radius (m)
        self.inner_radius = 0.2  # Inner radius (m)
        self.thickness = 0.05    # Thickness (m)
        self.elastic_modulus = 200e9  # Elastic modulus (Pa)
        self.force_magnitude = 1000   # X-direction force (N)
        
        # Second page rotation angle error parameters
        self.angle_error_range = 0.1  # ±0.1 degrees angle error
        self.systematic_error = 0.05  # Systematic error component
        
    def calculate_deformation(self, angle_deg):
        """Calculate deformation at given angle"""
        angle_rad = np.radians(angle_deg)
        
        # Simplified deformation model
        max_deformation = (self.force_magnitude * self.outer_radius**3) / \
                         (3 * self.elastic_modulus * self.thickness**3)
        
        # Deformation varies with angle - maximum in force direction, minimum in perpendicular direction
        deformation = max_deformation * (1 + 0.5 * np.cos(2 * angle_rad))
        
        return deformation
    
    def calculate_position_error(self, angle_deg):
        """Calculate position error"""
        deformation = self.calculate_deformation(angle_deg)
        
        # Position error proportional to deformation
        position_error = deformation * 1e6  # Convert to micrometers
        
        return position_error
    
    def calculate_angle_error(self, angle_deg):
        """Calculate rotation angle error (0~360 degrees)"""
        # Random error component
        random_error = np.random.uniform(-self.angle_error_range, self.angle_error_range)
        
        # Systematic error that varies with angle (e.g., due to encoder imperfections)
        systematic_variation = self.systematic_error * np.sin(np.radians(angle_deg * 2))
        
        # Total angle error
        total_angle_error = random_error + systematic_variation
        
        return total_angle_error
    
    def calculate_combined_error(self, angle_deg):
        """Calculate combined position and angle error effect"""
        position_error = self.calculate_position_error(angle_deg)
        angle_error = self.calculate_angle_error(angle_deg)
        
        # Convert angle error to equivalent position error at outer radius
        angle_error_position = np.radians(angle_error) * self.outer_radius * 1e6  # μm
        
        # Combined error (vector sum)
        combined_error = np.sqrt(position_error**2 + angle_error_position**2)
        
        return combined_error, position_error, angle_error, angle_error_position

def plot_precision_analysis():
    """Plot precision variation analysis - ORIGINAL PLOTS"""
    platform = HollowRotaryPlatform()
    
    # Generate angle data (0-360 degrees)
    angles = np.linspace(0, 360, 361)
    
    # Calculate position error at each angle
    position_errors = [platform.calculate_position_error(angle) for angle in angles]
    
    # Create figure - ORIGINAL LAYOUT
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot precision variation curve - ORIGINAL
    ax1.plot(angles, position_errors, 'b-', linewidth=2, label='Position Error')
    ax1.set_xlabel('Rotation Angle (degrees)')
    ax1.set_ylabel('Position Error (μm)')
    ax1.set_title('Precision Variation of Hollow Rotary Platform under X-direction Unidirectional Force')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Add statistical information - ORIGINAL
    max_error = max(position_errors)
    min_error = min(position_errors)
    avg_error = np.mean(position_errors)
    error_range = max_error - min_error
    
    stats_text = f'Max Error: {max_error:.2f} μm\nMin Error: {min_error:.2f} μm\n' \
                f'Average Error: {avg_error:.2f} μm\nError Range: {error_range:.2f} μm'
    
    ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, 
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Plot polar chart showing error distribution - ORIGINAL
    theta = np.radians(angles)
    ax2 = plt.subplot(212, projection='polar')
    ax2.plot(theta, position_errors, 'r-', linewidth=2)
    ax2.set_theta_zero_location('E')  # 0 degrees on the right
    ax2.set_theta_direction(-1)       # Clockwise direction
    ax2.set_title('Precision Variation Polar Plot', va='bottom')
    ax2.grid(True)
    
    plt.tight_layout()
    plt.show()
    
    return angles, position_errors

def plot_angle_error_analysis():
    """NEW: Plot rotation angle error analysis (0~360 degrees)"""
    platform = HollowRotaryPlatform()
    
    # Generate angle data (0-360 degrees)
    angles = np.linspace(0, 360, 361)
    
    # Calculate errors at each angle
    position_errors = []
    angle_errors = []
    combined_errors = []
    angle_error_positions = []
    
    for angle in angles:
        combined_error, pos_error, ang_error, ang_error_pos = platform.calculate_combined_error(angle)
        position_errors.append(pos_error)
        angle_errors.append(ang_error)
        combined_errors.append(combined_error)
        angle_error_positions.append(ang_error_pos)
    
    # Create new figure for angle error analysis
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    
    # Plot 1: Angle error vs angle
    ax1.plot(angles, angle_errors, 'g-', linewidth=2, label='Angle Error')
    ax1.set_xlabel('Rotation Angle (degrees)')
    ax1.set_ylabel('Angle Error (degrees)')
    ax1.set_title('Rotation Angle Error Variation (0~360°)')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Add statistical information for angle error
    max_angle_error = max(angle_errors)
    min_angle_error = min(angle_errors)
    avg_angle_error = np.mean(angle_errors)
    std_angle_error = np.std(angle_errors)
    
    angle_stats_text = f'Max Error: {max_angle_error:.4f}°\nMin Error: {min_angle_error:.4f}°\n' \
                      f'Avg Error: {avg_angle_error:.4f}°\nStd Dev: {std_angle_error:.4f}°'
    
    ax1.text(0.02, 0.98, angle_stats_text, transform=ax1.transAxes, 
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
    
    # Plot 2: Combined error vs angle
    ax2.plot(angles, position_errors, 'b-', linewidth=2, label='Position Error')
    ax2.plot(angles, combined_errors, 'r-', linewidth=2, label='Combined Error')
    ax2.set_xlabel('Rotation Angle (degrees)')
    ax2.set_ylabel('Error (μm)')
    ax2.set_title('Position vs Combined Error')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # Plot 3: Polar plot of angle error
    theta = np.radians(angles)
    ax3 = plt.subplot(223, projection='polar')
    ax3.plot(theta, np.abs(angle_errors), 'g-', linewidth=2, label='Absolute Angle Error')
    ax3.set_theta_zero_location('E')
    ax3.set_theta_direction(-1)
    ax3.set_title('Angle Error Distribution Polar Plot', va='bottom')
    ax3.grid(True)
    ax3.legend(loc='upper right')
    
    # Plot 4: Error components comparison
    ax4.plot(angles, position_errors, 'b-', linewidth=2, label='Position Error')
    ax4.plot(angles, angle_error_positions, 'g-', linewidth=2, label='Angle Error (Position Equivalent)')
    ax4.plot(angles, combined_errors, 'r-', linewidth=2, label='Combined Error')
    ax4.set_xlabel('Rotation Angle (degrees)')
    ax4.set_ylabel('Error (μm)')
    ax4.set_title('Error Components Comparison')
    ax4.grid(True, alpha=0.3)
    ax4.legend()
    
    plt.tight_layout()
    plt.show()
    
    return angles, position_errors, angle_errors, combined_errors

def analyze_critical_positions():
    """Analyze precision at critical positions - ORIGINAL"""
    platform = HollowRotaryPlatform()
    
    critical_angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]
    
    print("Critical Angle Position Precision Analysis:")
    print("Angle(deg)\tError(μm)")
    print("-" * 25)
    
    for angle in critical_angles:
        error = platform.calculate_position_error(angle)
        print(f"{angle:3d}\t\t{error:6.2f}")

def analyze_critical_positions_with_angle_error():
    """NEW: Analyze precision at critical positions with angle error"""
    platform = HollowRotaryPlatform()
    
    critical_angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]
    
    print("\nCritical Angle Analysis with Rotation Angle Error:")
    print("Angle(deg)\tPos_Error(μm)\tAngle_Error(°)\tCombined_Error(μm)")
    print("-" * 65)
    
    for angle in critical_angles:
        combined_error, pos_error, ang_error, ang_error_pos = platform.calculate_combined_error(angle)
        print(f"{angle:3d}\t\t{pos_error:8.2f}\t\t{ang_error:8.4f}\t\t{combined_error:8.2f}")

def analyze_angle_error_statistics():
    """NEW: Analyze statistics of angle error over full rotation"""
    platform = HollowRotaryPlatform()
    
    angles = np.linspace(0, 360, 1000)
    angle_errors = [platform.calculate_angle_error(angle) for angle in angles]
    
    max_angle_error = max(angle_errors)
    min_angle_error = min(angle_errors)
    avg_angle_error = np.mean(angle_errors)
    std_angle_error = np.std(angle_errors)
    
    print("\nRotation Angle Error Statistics (0~360°):")
    print("=" * 50)
    print(f"Maximum Angle Error: {max_angle_error:.4f}°")
    print(f"Minimum Angle Error: {min_angle_error:.4f}°")
    print(f"Average Angle Error: {avg_angle_error:.4f}°")
    print(f"Standard Deviation: {std_angle_error:.4f}°")
    print(f"Peak-to-Peak Error: {max_angle_error - min_angle_error:.4f}°")

# Run analysis
if __name__ == "__main__":
    print("Hollow Rotary Platform Precision Analysis")
    print("=" * 50)
    
    # ORIGINAL ANALYSIS
    print("\n--- ORIGINAL ANALYSIS ---")
    analyze_critical_positions()
    
    # Plot original precision variation curve
    print("\nGenerating original precision analysis plots...")
    angles, errors = plot_precision_analysis()
    
    # Output original statistical information
    print(f"\nOriginal Precision Statistics:")
    print(f"Maximum Error: {max(errors):.2f} μm")
    print(f"Minimum Error: {min(errors):.2f} μm")
    print(f"Peak-to-Peak Error: {max(errors)-min(errors):.2f} μm")
    
    # NEW ANALYSIS WITH ANGLE ERROR
    print("\n" + "="*70)
    print("ROTATION ANGLE ERROR ANALYSIS (0~360°)")
    print("="*70)
    
    # Analyze critical positions with angle error
    analyze_critical_positions_with_angle_error()
    
    # Analyze angle error statistics
    analyze_angle_error_statistics()
    
    # Plot angle error analysis
    print("\nGenerating rotation angle error analysis plots...")
    angles, pos_errors, ang_errors, combined_errors = plot_angle_error_analysis()
    
    # Output combined statistical information
    print(f"\nCombined Error Statistics:")
    print(f"Maximum Position Error: {max(pos_errors):.2f} μm")
    print(f"Maximum Combined Error: {max(combined_errors):.2f} μm")
    print(f"Peak-to-Peak Position Error: {max(pos_errors)-min(pos_errors):.2f} μm")
    print(f"Peak-to-Peak Combined Error: {max(combined_errors)-min(combined_errors):.2f} μm")
    print(f"Angle Error Contribution: {max(combined_errors)-max(pos_errors):.2f} μm")
