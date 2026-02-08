# Heart Rate Detection from Video

This Python application detects heart rate from video footage of a person's face using photoplethysmography (PPG) and computer vision techniques.

## How It Works

The application uses a non-invasive technique to measure heart rate:

1. **Face Detection**: Uses OpenCV's Haar Cascade classifier to detect faces
2. **ROI Extraction**: Focuses on the forehead region (best signal quality)
3. **PPG Signal Extraction**: Extracts the green channel from the skin, which is most sensitive to blood volume changes
4. **Signal Processing**: 
   - Applies bandpass filtering (0.8-3.0 Hz for 48-180 BPM range)
   - Uses FFT (Fast Fourier Transform) to identify the dominant frequency
5. **Heart Rate Calculation**: Converts the peak frequency to beats per minute (BPM)

## Installation

1. Install Python 3.8 or higher
2. Install required packages:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python heart_rate_detector.py input_video.mp4
```

### Save Output Video

```bash
python heart_rate_detector.py input_video.mp4 output_video.mp4
```

### Using in Your Code

```python
from heart_rate_detector import HeartRateDetector

# Create detector
detector = HeartRateDetector(buffer_size=300, fps=30)

# Process video
hr_measurements = detector.process_video(
    'path/to/video.mp4',
    output_path='path/to/output.mp4',
    show_live=True
)

# Plot results
detector.plot_results(hr_measurements, save_path='hr_plot.png')
```

## Tips for Best Results

1. **Lighting**: Ensure good, consistent lighting on the face
2. **Stability**: Keep the face relatively still and centered
3. **Duration**: Videos should be at least 10-15 seconds for accurate readings
4. **Distance**: Face should be clearly visible, not too far from camera
5. **Skin Visibility**: Forehead should be visible and unobstructed

## Output

The application provides:

- **Live Display**: Shows the video with detected face, ROI, and current heart rate
- **Output Video** (optional): Annotated video with heart rate overlay
- **Statistics**: Mean, median, min, max heart rate values
- **Plots**: Time series plot and histogram of heart rate measurements

## Technical Details

### Signal Processing Pipeline

1. **Green Channel Extraction**: Blood volume changes are most visible in green light
2. **Normalization**: Signal is normalized (z-score) to remove DC component
3. **Bandpass Filter**: 4th order Butterworth filter (0.8-3.0 Hz)
4. **Windowing**: Hamming window applied before FFT to reduce spectral leakage
5. **Peak Detection**: Identifies dominant frequency in physiological range

### Parameters

- `buffer_size`: Number of frames for analysis (default: 300, ~10 seconds at 30fps)
- `fps`: Frames per second (auto-detected from video)
- `lowcut`: Lower frequency bound (default: 0.8 Hz = 48 BPM)
- `highcut`: Upper frequency bound (default: 3.0 Hz = 180 BPM)

## Limitations

- Requires visible forehead or facial skin
- Accuracy depends on lighting conditions
- Movement can introduce noise
- Not a medical device - for educational/research purposes only
- Works best with videos 10+ seconds long

## About Eulerian Video Magnification

While this implementation doesn't use Eulerian video magnification, it's worth noting:
- **Current approach**: Directly analyzes color changes (more efficient, faster)
- **Eulerian magnification**: Would amplify subtle color/motion changes for visualization
- The current PPG-based approach is sufficient for heart rate detection
- Eulerian magnification is more useful for visualizing heartbeat rather than measuring it

## Troubleshooting

**"No face detected"**
- Ensure face is clearly visible and well-lit
- Try different angles or positions
- Check video quality

**"Heart rate seems incorrect"**
- Ensure person remains relatively still
- Check lighting conditions
- Verify video is at least 10-15 seconds
- Try adjusting buffer_size parameter

**"Detection is unstable"**
- Improve lighting conditions
- Reduce movement
- Use higher quality video
- Increase buffer_size for more stable readings

## Example Videos to Try

For testing, record a ~30 second video with:
- Good frontal lighting
- Face centered in frame
- Minimal movement
- Visible forehead

## License

This is an educational project. Not intended for medical use.

## References

- Photoplethysmography (PPG) for non-contact heart rate measurement
- OpenCV face detection using Haar Cascades
- FFT-based heart rate extraction from PPG signals
