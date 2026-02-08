#!/usr/bin/env python3
"""
Real-time Heart Rate Detection from Webcam
"""

import cv2
import numpy as np
from heart_rate_detector import HeartRateDetector
import time


def main():
    """Run real-time heart rate detection from webcam."""
    
    print("Starting webcam heart rate detection...")
    print("Press 'q' to quit")
    print("\nTips for best results:")
    print("  - Keep your face centered and still")
    print("  - Ensure good lighting on your forehead")
    print("  - Wait ~10 seconds for accurate readings")
    print("  - Avoid moving or talking during measurement\n")
    
    # Initialize webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    # Set webcam properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    # Get actual FPS
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    
    print(f"Webcam FPS: {fps}")
    
    # Create detector
    detector = HeartRateDetector(buffer_size=300, fps=fps)
    
    frame_count = 0
    start_time = time.time()
    
    # Create window
    cv2.namedWindow('Heart Rate Detection', cv2.WINDOW_NORMAL)
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print("Error: Could not read frame")
                break
            
            # Flip frame for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Calculate timestamp
            timestamp = time.time() - start_time
            
            # Process frame
            annotated_frame, hr = detector.process_frame(frame, timestamp)
            
            # Add instructions overlay
            cv2.putText(annotated_frame, "Keep still and face camera", 
                       (10, annotated_frame.shape[0] - 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(annotated_frame, "Press 'q' to quit", 
                       (10, annotated_frame.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Show buffer fill status
            buffer_fill = len(detector.green_values) / detector.buffer_size
            bar_width = 200
            bar_height = 20
            bar_x = annotated_frame.shape[1] - bar_width - 10
            bar_y = 10
            
            # Draw buffer bar background
            cv2.rectangle(annotated_frame, (bar_x, bar_y), 
                         (bar_x + bar_width, bar_y + bar_height), 
                         (100, 100, 100), -1)
            
            # Draw buffer bar fill
            fill_width = int(bar_width * buffer_fill)
            color = (0, 255, 0) if buffer_fill >= 1.0 else (0, 165, 255)
            cv2.rectangle(annotated_frame, (bar_x, bar_y), 
                         (bar_x + fill_width, bar_y + bar_height), 
                         color, -1)
            
            # Draw buffer bar border
            cv2.rectangle(annotated_frame, (bar_x, bar_y), 
                         (bar_x + bar_width, bar_y + bar_height), 
                         (255, 255, 255), 2)
            
            # Buffer status text
            cv2.putText(annotated_frame, f"Buffer: {buffer_fill:.0%}", 
                       (bar_x, bar_y + bar_height + 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Display frame
            cv2.imshow('Heart Rate Detection', annotated_frame)
            
            # Check for quit
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):  # Reset
                detector.green_values.clear()
                detector.timestamps.clear()
                detector.hr_history.clear()
                detector.current_hr = 0
                print("Reset detector")
            
            frame_count += 1
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    finally:
        # Cleanup
        cap.release()
        cv2.destroyAllWindows()
        
        # Print final statistics
        if detector.hr_history:
            hrs = list(detector.hr_history)
            print("\n" + "="*50)
            print("Final Heart Rate Statistics:")
            print("="*50)
            print(f"  Mean:   {np.mean(hrs):.1f} BPM")
            print(f"  Median: {np.median(hrs):.1f} BPM")
            print(f"  Std:    {np.std(hrs):.1f} BPM")
            print(f"  Range:  {np.min(hrs):.1f} - {np.max(hrs):.1f} BPM")
            print("="*50)


if __name__ == "__main__":
    main()
