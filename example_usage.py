#!/usr/bin/env python3
"""
Example usage of the Heart Rate Detector
"""

from heart_rate_detector import HeartRateDetector
import numpy as np


def example_basic_usage():
    """Basic usage example - process a video file."""
    
    print("="*60)
    print("Example 1: Basic Video Processing")
    print("="*60)
    
    # Create detector with default settings
    detector = HeartRateDetector(buffer_size=300, fps=30)
    
    # Process video
    # Replace 'input.mp4' with your video file path
    hr_measurements = detector.process_video(
        video_path='input.mp4',
        output_path='output.mp4',  # Optional: save annotated video
        show_live=True  # Show video while processing
    )
    
    # Plot results
    detector.plot_results(hr_measurements, save_path='heart_rate_plot.png')
    
    print("\nProcessing complete!")


def example_custom_settings():
    """Example with custom settings."""
    
    print("\n" + "="*60)
    print("Example 2: Custom Settings")
    print("="*60)
    
    # Create detector with custom buffer size and FPS
    # Larger buffer = more stable but slower to respond
    # Smaller buffer = faster response but less stable
    detector = HeartRateDetector(
        buffer_size=450,  # 15 seconds at 30fps
        fps=30
    )
    
    hr_measurements = detector.process_video(
        video_path='input.mp4',
        show_live=False  # Don't show video (faster processing)
    )
    
    if hr_measurements:
        # Calculate statistics
        hrs = [hr for _, hr in hr_measurements]
        
        print(f"\nDetailed Statistics:")
        print(f"  Number of measurements: {len(hrs)}")
        print(f"  Mean HR: {np.mean(hrs):.1f} BPM")
        print(f"  Median HR: {np.median(hrs):.1f} BPM")
        print(f"  Std Dev: {np.std(hrs):.1f} BPM")
        print(f"  Min HR: {np.min(hrs):.1f} BPM")
        print(f"  Max HR: {np.max(hrs):.1f} BPM")
        print(f"  Heart Rate Variability (std): {np.std(hrs):.1f} BPM")


def example_analyze_multiple_videos():
    """Example: Analyze multiple videos and compare results."""
    
    print("\n" + "="*60)
    print("Example 3: Batch Processing Multiple Videos")
    print("="*60)
    
    video_files = [
        'video1.mp4',
        'video2.mp4',
        'video3.mp4'
    ]
    
    results = {}
    
    for video_file in video_files:
        print(f"\nProcessing {video_file}...")
        
        detector = HeartRateDetector(buffer_size=300, fps=30)
        
        try:
            hr_measurements = detector.process_video(
                video_path=video_file,
                show_live=False
            )
            
            if hr_measurements:
                hrs = [hr for _, hr in hr_measurements]
                results[video_file] = {
                    'mean': np.mean(hrs),
                    'std': np.std(hrs),
                    'min': np.min(hrs),
                    'max': np.max(hrs)
                }
        except Exception as e:
            print(f"Error processing {video_file}: {e}")
    
    # Print comparison
    print("\n" + "="*60)
    print("Comparison Results:")
    print("="*60)
    print(f"{'Video':<20} {'Mean HR':<15} {'Std Dev':<15}")
    print("-"*60)
    
    for video, stats in results.items():
        print(f"{video:<20} {stats['mean']:>7.1f} BPM   {stats['std']:>7.1f} BPM")


def example_frame_by_frame():
    """Example: Process video frame by frame with custom logic."""
    
    print("\n" + "="*60)
    print("Example 4: Frame-by-Frame Processing")
    print("="*60)
    
    import cv2
    
    detector = HeartRateDetector(buffer_size=300, fps=30)
    cap = cv2.VideoCapture('input.mp4')
    
    frame_count = 0
    hr_values = []
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        timestamp = frame_count / 30.0  # Assuming 30 fps
        
        # Process frame
        annotated_frame, hr = detector.process_frame(frame, timestamp)
        
        if hr > 0:
            hr_values.append(hr)
            
            # Custom logic: Alert if heart rate is abnormal
            if hr > 120:
                print(f"⚠️  Warning: High heart rate detected at {timestamp:.1f}s: {hr:.1f} BPM")
            elif hr < 50:
                print(f"⚠️  Warning: Low heart rate detected at {timestamp:.1f}s: {hr:.1f} BPM")
        
        # You can do custom processing here
        # For example: save specific frames, trigger alerts, etc.
        
        frame_count += 1
    
    cap.release()
    
    if hr_values:
        print(f"\nAverage heart rate: {np.mean(hr_values):.1f} BPM")


def main():
    """Run all examples."""
    
    print("\n" + "="*70)
    print(" Heart Rate Detector - Usage Examples")
    print("="*70)
    print("\nNOTE: These examples assume you have video files named:")
    print("  - input.mp4")
    print("  - video1.mp4, video2.mp4, video3.mp4 (for batch example)")
    print("\nReplace these with your actual video file paths.")
    print("="*70)
    
    # Uncomment the example you want to run:
    
    # example_basic_usage()
    # example_custom_settings()
    # example_analyze_multiple_videos()
    # example_frame_by_frame()
    
    print("\nTo run an example, uncomment it in the main() function.")


if __name__ == "__main__":
    main()
