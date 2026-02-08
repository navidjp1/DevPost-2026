# Heart Rate Monitor - GUI Version

A simple, user-friendly graphical interface for real-time heart rate monitoring using your webcam.

## Features

✨ **Real-time Video Feed** - See yourself with face and ROI detection overlay
📊 **Live Heart Rate Display** - Large, easy-to-read BPM counter with color coding
📈 **Trend Graph** - Visual representation of your heart rate over time
📉 **Statistics** - Average, min, max, and standard deviation
🎯 **Buffer & Confidence Indicators** - Know when readings are stable

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Launch the GUI

```bash
python launch_gui.py
```

Or directly:

```bash
python heart_rate_gui.py
```

## How to Use

1. **Click "Start"** - The application will access your webcam
2. **Position yourself** - Keep your face centered and visible
3. **Stay still** - Minimize movement for best results
4. **Wait** - Allow ~10 seconds for the buffer to fill and readings to stabilize
5. **Monitor** - Watch your heart rate in real-time!

### Controls

- **▶ Start** - Begin heart rate monitoring
- **⬛ Stop** - Stop monitoring and release webcam
- **↻ Reset** - Clear all data and start fresh

## Understanding the Display

### Video Feed
- **Blue Box** - Detected face
- **Green Box** - Forehead ROI (region used for measurement)
- Overlaid text shows current status

### Heart Rate Display
- **Green** - Normal range (60-100 BPM)
- **Orange** - Elevated (100-120 BPM)  
- **Red** - High or low (<60 or >120 BPM)

### Statistics Panel
- **Average** - Mean heart rate over session
- **Minimum** - Lowest detected BPM
- **Maximum** - Highest detected BPM
- **Std Dev** - Variability in measurements
- **Buffer** - Data collection progress (needs 100% for accurate readings)
- **Confidence** - Measurement reliability (higher is better)

### Trend Graph
- Real-time visualization of heart rate changes
- Shows last 100 measurements
- Green line with data points

## Tips for Best Results

### Lighting
- ✅ Well-lit room with even lighting on your face
- ✅ Natural or warm white light
- ❌ Avoid harsh shadows or backlighting
- ❌ Don't sit with a window behind you

### Positioning
- ✅ Face centered in frame
- ✅ 1-2 feet from camera
- ✅ Look at camera
- ❌ Don't turn your head away
- ❌ Avoid extreme angles

### During Measurement
- ✅ Sit still and relaxed
- ✅ Breathe normally
- ✅ Wait for buffer to fill (100%)
- ❌ Don't talk or move excessively
- ❌ Don't touch your face

### Environment
- ✅ Stable environment
- ✅ Comfortable temperature
- ❌ Avoid after exercise (wait 10 minutes)
- ❌ Don't use in moving vehicle

## Troubleshooting

### "Could not open webcam"
- Check webcam is connected
- Close other apps using the webcam
- Try running as administrator (Windows)
- Check webcam permissions in system settings

### No face detected
- Improve lighting
- Move closer to camera
- Ensure face is fully visible
- Remove obstructions (hats, hands)

### Unstable readings
- Reduce movement
- Improve lighting
- Wait longer for buffer to fill
- Ensure forehead is clearly visible

### Heart rate seems incorrect
- Wait for 100% buffer fill
- Check confidence indicator
- Ensure you're not moving
- Verify lighting is good
- Try resetting and starting again

## Technical Details

### How It Works
The application uses **photoplethysmography (PPG)**:

1. **Face Detection** - OpenCV Haar Cascade identifies your face
2. **ROI Extraction** - Forehead region is selected (best signal)
3. **Color Analysis** - Green channel is extracted (most sensitive to blood flow)
4. **Signal Processing** - Data is filtered and analyzed using FFT
5. **Heart Rate Calculation** - Dominant frequency is converted to BPM

### Performance Requirements
- **Camera**: Any webcam (640x480 minimum)
- **CPU**: Modern processor (last 5 years)
- **RAM**: 2GB minimum
- **OS**: Windows, macOS, or Linux with Tkinter support

## Keyboard Shortcuts

While the GUI is focused:
- **Spacebar** - Start/Stop (when button is enabled)
- **R** - Reset (when stopped)
- **Q** or ESC - Quit application

## Privacy & Data

- ✅ All processing is done **locally** on your computer
- ✅ **No data** is sent to the internet
- ✅ **No recordings** are saved
- ✅ Video feed is only used for real-time processing
- ✅ When you click "Stop", all video processing ends immediately

## Known Limitations

- Not a medical device - for educational/entertainment use only
- Accuracy depends on environmental conditions
- Requires stable lighting and positioning
- May not work well with very dark skin tones in poor lighting
- Makeup may affect readings
- Requires visible forehead region

## Comparison with Other Methods

| Method | Accuracy | Convenience | Requirements |
|--------|----------|-------------|--------------|
| This App | Moderate | High | Webcam, good lighting |
| Chest Strap | Very High | Low | Special hardware |
| Smartwatch | High | High | Wearable device |
| Pulse Oximeter | Very High | Moderate | Finger device |
| Manual Count | High | Low | Timer, practice |

## Advanced Usage

### Custom Settings

Edit `heart_rate_gui.py` to customize:

```python
# Buffer size (larger = more stable, slower to respond)
self.detector = HeartRateDetector(buffer_size=450, fps=fps)

# Video resolution
self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
```

### Logging Data

To save heart rate data, modify the `update_frame()` method:

```python
if hr > 0:
    with open('hr_log.csv', 'a') as f:
        f.write(f"{timestamp},{hr}\n")
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the main README.md for technical details
3. Ensure all dependencies are properly installed

## Version

**Version 1.0** - Initial GUI release
- Real-time video display
- Live heart rate monitoring
- Statistical analysis
- Trend graphing

## License

Educational use only. Not for medical purposes.

---

**Remember**: This is not a medical device. For health concerns, consult a healthcare professional.
