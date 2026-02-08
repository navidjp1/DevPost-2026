#!/usr/bin/env env python3
"""
Heart Rate Detection from Video
Uses photoplethysmography (PPG) to detect heart rate from facial video.
"""

import cv2
import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq
import matplotlib.pyplot as plt
from collections import deque
import time


class HeartRateDetector:
    def __init__(self, buffer_size=300, fps=30):
        """
        Initialize the heart rate detector.
        
        Args:
            buffer_size: Number of frames to keep in buffer for analysis
            fps: Expected frames per second of the video
        """
        self.buffer_size = buffer_size
        self.fps = fps
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Buffer for storing green channel values
        self.green_values = deque(maxlen=buffer_size)
        self.timestamps = deque(maxlen=buffer_size)
        
        # Heart rate tracking
        self.current_hr = 0
        self.hr_history = deque(maxlen=50)
        
    def extract_forehead_roi(self, frame, face):
        """
        Extract the forehead region of interest from detected face.
        The forehead typically gives the best PPG signal.
        
        Args:
            frame: Input frame
            face: Detected face coordinates (x, y, w, h)
            
        Returns:
            ROI image or None
        """
        x, y, w, h = face
        
        # Define forehead region (upper 1/3 of face, centered)
        forehead_y = y + int(h * 0.1)
        forehead_height = int(h * 0.25)
        forehead_x = x + int(w * 0.25)
        forehead_width = int(w * 0.5)
        
        # Extract ROI
        roi = frame[forehead_y:forehead_y + forehead_height,
                   forehead_x:forehead_x + forehead_width]
        
        return roi, (forehead_x, forehead_y, forehead_width, forehead_height)
    
    def extract_green_channel_mean(self, roi):
        """
        Extract mean value of green channel from ROI.
        Green channel is most sensitive to blood volume changes.
        
        Args:
            roi: Region of interest image
            
        Returns:
            Mean green channel value
        """
        if roi is None or roi.size == 0:
            return None
        
        # Extract green channel (index 1 in BGR)
        green_channel = roi[:, :, 1]
        
        # Return mean value
        return np.mean(green_channel)
    
    def apply_bandpass_filter(self, signal_data, fs, lowcut=0.8, highcut=3.0):
        """
        Apply bandpass filter to isolate heart rate frequencies.
        Typical heart rate range: 48-180 BPM (0.8-3.0 Hz)
        
        Args:
            signal_data: Input signal
            fs: Sampling frequency
            lowcut: Low cutoff frequency (Hz)
            highcut: High cutoff frequency (Hz)
            
        Returns:
            Filtered signal
        """
        nyquist = 0.5 * fs
        low = lowcut / nyquist
        high = highcut / nyquist
        
        # Design butterworth bandpass filter
        b, a = signal.butter(4, [low, high], btype='band')
        
        # Apply filter
        filtered = signal.filtfilt(b, a, signal_data)
        
        return filtered
    
    def calculate_heart_rate_fft(self, signal_data, fs):
        """
        Calculate heart rate using FFT (Fourier Transform).
        
        Args:
            signal_data: Filtered PPG signal
            fs: Sampling frequency
            
        Returns:
            Heart rate in BPM
        """
        # Detrend the signal
        detrended = signal.detrend(signal_data)
        
        # Apply hamming window to reduce spectral leakage
        windowed = detrended * np.hamming(len(detrended))
        
        # Compute FFT
        N = len(windowed)
        fft_values = fft(windowed)
        fft_freqs = fftfreq(N, 1/fs)
        
        # Only look at positive frequencies in the heart rate range
        mask = (fft_freqs >= 0.8) & (fft_freqs <= 3.0)
        
        masked_fft = np.abs(fft_values[mask])
        masked_freqs = fft_freqs[mask]
        
        # Find peak frequency
        if len(masked_fft) > 0:
            peak_idx = np.argmax(masked_fft)
            peak_freq = masked_freqs[peak_idx]
            
            # Convert to BPM
            hr = peak_freq * 60
            return hr
        
        return 0
    
    def process_frame(self, frame, timestamp):
        """
        Process a single frame to extract heart rate information.
        
        Args:
            frame: Input video frame
            timestamp: Frame timestamp
            
        Returns:
            Annotated frame, current heart rate
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
        )
        
        annotated_frame = frame.copy()
        
        if len(faces) > 0:
            # Use the largest face
            face = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = face
            
            # Draw face rectangle
            cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            
            # Extract forehead ROI
            roi, roi_coords = self.extract_forehead_roi(frame, face)
            fx, fy, fw, fh = roi_coords
            
            # Draw ROI rectangle
            cv2.rectangle(annotated_frame, (fx, fy), 
                         (fx+fw, fy+fh), (0, 255, 0), 2)
            
            # Extract green channel mean
            green_mean = self.extract_green_channel_mean(roi)
            
            if green_mean is not None:
                self.green_values.append(green_mean)
                self.timestamps.append(timestamp)
                
                # Calculate heart rate if we have enough data
                if len(self.green_values) >= self.buffer_size:
                    try:
                        signal_data = np.array(self.green_values)
                        
                        # Normalize signal
                        signal_data = (signal_data - np.mean(signal_data)) / np.std(signal_data)
                        
                        # Apply bandpass filter
                        filtered_signal = self.apply_bandpass_filter(
                            signal_data, self.fps
                        )
                        
                        # Calculate heart rate
                        hr = self.calculate_heart_rate_fft(filtered_signal, self.fps)
                        
                        # Validate heart rate (reasonable range)
                        if 40 < hr < 200:
                            self.current_hr = hr
                            self.hr_history.append(hr)
                    except Exception as e:
                        print(f"Error calculating heart rate: {e}")
        
        # Display heart rate on frame
        if self.current_hr > 0:
            avg_hr = np.mean(list(self.hr_history)) if self.hr_history else self.current_hr
            cv2.putText(annotated_frame, f"HR: {avg_hr:.1f} BPM", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       1, (0, 255, 0), 2)
            
            # Show confidence indicator
            confidence = min(len(self.hr_history) / 50.0, 1.0)
            cv2.putText(annotated_frame, f"Confidence: {confidence:.0%}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.6, (0, 255, 0), 2)
        else:
            cv2.putText(annotated_frame, "Detecting...", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       1, (0, 0, 255), 2)
        
        return annotated_frame, self.current_hr
    
    def process_video(self, video_path, output_path=None, show_live=True):
        """
        Process a video file to extract heart rate.
        
        Args:
            video_path: Path to input video
            output_path: Path to save output video (optional)
            show_live: Whether to display video while processing
            
        Returns:
            List of heart rate measurements with timestamps
        """
        cap = cv2.VideoCapture(video_path)
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps > 0 else 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Video FPS: {self.fps}")
        print(f"Resolution: {width}x{height}")
        print(f"Total frames: {total_frames}")
        
        # Setup video writer if output path specified
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, self.fps, (width, height))
        
        hr_measurements = []
        frame_count = 0
        start_time = time.time()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Calculate timestamp
            timestamp = frame_count / self.fps
            
            # Process frame
            annotated_frame, hr = self.process_frame(frame, timestamp)
            
            if hr > 0:
                hr_measurements.append((timestamp, hr))
            
            # Write to output video
            if output_path:
                out.write(annotated_frame)
            
            # Display
            if show_live:
                cv2.imshow('Heart Rate Detection', annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            frame_count += 1
            
            # Progress update
            if frame_count % 30 == 0:
                progress = (frame_count / total_frames) * 100
                print(f"Progress: {progress:.1f}% - Current HR: {hr:.1f} BPM")
        
        # Cleanup
        cap.release()
        if output_path:
            out.release()
        if show_live:
            cv2.destroyAllWindows()
        
        processing_time = time.time() - start_time
        print(f"\nProcessing complete in {processing_time:.1f} seconds")
        
        # Calculate final statistics
        if hr_measurements:
            hrs = [hr for _, hr in hr_measurements]
            print(f"\nHeart Rate Statistics:")
            print(f"  Mean: {np.mean(hrs):.1f} BPM")
            print(f"  Median: {np.median(hrs):.1f} BPM")
            print(f"  Std Dev: {np.std(hrs):.1f} BPM")
            print(f"  Min: {np.min(hrs):.1f} BPM")
            print(f"  Max: {np.max(hrs):.1f} BPM")
        
        return hr_measurements
    
    def plot_results(self, hr_measurements, save_path=None):
        """
        Plot heart rate over time.
        
        Args:
            hr_measurements: List of (timestamp, hr) tuples
            save_path: Path to save plot (optional)
        """
        if not hr_measurements:
            print("No measurements to plot")
            return
        
        timestamps, hrs = zip(*hr_measurements)
        
        plt.figure(figsize=(12, 6))
        
        # Plot raw measurements
        plt.subplot(2, 1, 1)
        plt.plot(timestamps, hrs, 'b-', alpha=0.5, label='Raw')
        
        # Plot smoothed (moving average)
        if len(hrs) > 10:
            window = 10
            smoothed = np.convolve(hrs, np.ones(window)/window, mode='valid')
            smooth_t = timestamps[window-1:]
            plt.plot(smooth_t, smoothed, 'r-', linewidth=2, label='Smoothed')
        
        plt.xlabel('Time (seconds)')
        plt.ylabel('Heart Rate (BPM)')
        plt.title('Heart Rate Over Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Histogram
        plt.subplot(2, 1, 2)
        plt.hist(hrs, bins=30, edgecolor='black', alpha=0.7)
        plt.xlabel('Heart Rate (BPM)')
        plt.ylabel('Frequency')
        plt.title('Heart Rate Distribution')
        plt.axvline(np.mean(hrs), color='r', linestyle='--', 
                   label=f'Mean: {np.mean(hrs):.1f} BPM')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")
        
        plt.show()


def main():
    """Main function to run the heart rate detector."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python heart_rate_detector.py <video_path> [output_video_path]")
        print("\nExample: python heart_rate_detector.py input.mp4 output.mp4")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Create detector
    detector = HeartRateDetector(buffer_size=300, fps=30)
    
    # Process video
    print(f"Processing video: {video_path}")
    hr_measurements = detector.process_video(
        video_path, 
        output_path=output_path,
        show_live=True
    )
    
    # Plot results
    if hr_measurements:
        plot_path = video_path.rsplit('.', 1)[0] + '_hr_plot.png'
        detector.plot_results(hr_measurements, save_path=plot_path)


if __name__ == "__main__":
    main()
