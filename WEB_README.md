# Heart Rate Monitor - Web Interface

A beautiful, browser-based heart rate monitoring application using pure HTML, CSS, and JavaScript (no frameworks). Runs completely locally on your machine.

## Features

✨ **Modern Web Interface** - Clean, responsive design that works on any device
📹 **Live Video Stream** - Real-time video feed with face detection overlay
💓 **Real-time Heart Rate** - Large, color-coded BPM display
📊 **Live Statistics** - Average, min, max, and standard deviation
📈 **Interactive Graph** - Canvas-based heart rate trend visualization
🎯 **Progress Indicators** - Buffer fill and confidence meters
🌐 **Browser-Based** - Access from any modern web browser
🔒 **100% Local** - All processing done on your machine, no data sent anywhere

## Architecture

```
Browser (HTML/CSS/JS)  ←→  Flask Server (Python)  ←→  OpenCV + Heart Rate Detector
     │                          │                           │
  Displays UI              Routes requests             Processes video
  Receives data            Streams video              Calculates HR
  Updates graphs           Sends HR data              Detects faces
```

### Technology Stack

**Frontend (Pure Vanilla)**
- HTML5 - Structure
- CSS3 - Styling with gradients, animations, flexbox
- JavaScript - Event handling, canvas graphing, Server-Sent Events
- No frameworks or libraries required!

**Backend**
- Flask - Lightweight web server
- OpenCV - Computer vision
- NumPy/SciPy - Signal processing
- Heart Rate Detector - Custom PPG algorithm

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- opencv-python - Video processing
- numpy - Numerical operations
- scipy - Signal processing
- matplotlib - (Optional, for debugging)
- Flask - Web server

### 2. Verify Installation

```bash
python -c "import cv2, numpy, scipy, flask; print('✓ All dependencies installed')"
```

## Usage

### Quick Start

```bash
python launch_web.py
```

This will:
1. Check dependencies
2. Start the Flask server
3. Automatically open your browser to http://localhost:5000

### Manual Start

```bash
python app.py
```

Then open your browser and navigate to:
```
http://localhost:5000
```

### Using the Interface

1. **Click "▶ Start"**
   - Browser will request webcam access - click "Allow"
   - Video feed will start streaming
   - Detection begins automatically

2. **Position Yourself**
   - Center your face in the frame
   - Ensure good lighting
   - Keep forehead visible

3. **Wait for Detection**
   - Buffer indicator fills to 100% (~10 seconds)
   - Status changes from "Searching..." to "Detecting ✓"
   - Heart rate appears and updates in real-time

4. **Monitor Your Heart Rate**
   - Watch the large BPM display
   - View statistics panel for averages
   - Check the trend graph for patterns

5. **Control the Session**
   - **⬛ Stop** - Pause monitoring (keeps data)
   - **↻ Reset** - Clear all data and start fresh

## Interface Overview

### Video Section (Left)
- Live video feed from your webcam
- Blue box: Detected face
- Green box: Forehead ROI (region of interest)
- Overlaid detection information

### Heart Rate Display (Right Top)
- **Large BPM number** with color coding:
  - 🟢 Green (60-100 BPM) - Normal
  - 🟠 Orange (100-120 BPM) - Elevated
  - 🔴 Red (<60 or >120 BPM) - High/Low

### Statistics Panel
- **Average** - Mean heart rate over session
- **Minimum** - Lowest detected BPM
- **Maximum** - Highest detected BPM
- **Std Dev** - Heart rate variability

### Status Panel
- **Status Indicator** - Visual indicator with pulsing animation
  - ⚫ Gray - Stopped
  - 🟠 Orange - Searching for face
  - 🟢 Green - Actively detecting
- **Buffer** - Data collection progress (needs 100% for accuracy)
- **Confidence** - Reading reliability (higher is better)

### Trend Graph
- Real-time canvas-based line graph
- Shows last 100 heart rate measurements
- Grid lines and axis labels
- Smooth curve with data points

### Control Buttons
- **▶ Start** - Begin monitoring
- **⬛ Stop** - Pause monitoring
- **↻ Reset** - Clear all data

## How It Works

### Frontend (Browser)

**Server-Sent Events (SSE)**
```javascript
eventSource = new EventSource('/data_stream');
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateDisplay(data);
};
```
- Opens persistent connection to server
- Receives heart rate updates every 100ms
- Updates UI in real-time

**Video Streaming**
```html
<img id="videoFeed" src="/video_feed">
```
- MJPEG stream (Motion JPEG)
- Each frame sent as separate JPEG
- Automatically displays in browser

**Canvas Graphing**
```javascript
function drawGraph() {
    ctx.clearRect(0, 0, width, height);
    // Draw grid lines
    // Draw heart rate line
    // Draw data points
}
```
- Pure JavaScript canvas rendering
- No chart libraries needed
- 60 FPS smooth updates

### Backend (Flask)

**Video Generation**
```python
def generate_frames():
    while True:
        ret, frame = cap.read()
        annotated_frame, hr = detector.process_frame(frame, timestamp)
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
```

**Data Streaming**
```python
def generate_data_stream():
    while True:
        yield f"data: {json.dumps(current_data)}\n\n"
        time.sleep(0.1)
```

**Routes**
- `/` - Serve HTML page
- `/video_feed` - Stream video frames
- `/data_stream` - Stream heart rate data
- `/start` - Start detection
- `/stop` - Stop detection
- `/reset` - Reset all data

## Network & Firewall

The application runs on `0.0.0.0:5000` which means:

- **Accessible on your local network** (optional)
  - From same computer: http://localhost:5000
  - From other devices: http://YOUR_IP:5000
  
- **Not accessible from internet** (by default)
  - No port forwarding needed
  - Completely private and secure

### Firewall Configuration

**Windows**
```powershell
# If accessing from other devices on network
netsh advfirewall firewall add rule name="Heart Rate Monitor" dir=in action=allow protocol=TCP localport=5000
```

**macOS/Linux**
```bash
# Usually no configuration needed for local access
# For other devices, ensure port 5000 is allowed
```

## Browser Compatibility

✅ **Fully Supported**
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Opera 76+

✅ **Features Used**
- Server-Sent Events (SSE)
- Canvas 2D API
- Flexbox/Grid CSS
- CSS Animations
- MJPEG Streaming

❌ **Not Supported**
- Internet Explorer (deprecated)
- Very old mobile browsers

## Mobile Access

Access from phone/tablet on same WiFi network:

1. Start the server on your computer
2. Find your computer's IP address:
   ```bash
   # Windows
   ipconfig
   
   # macOS/Linux
   ifconfig
   ```
3. On mobile browser, navigate to:
   ```
   http://YOUR_COMPUTER_IP:5000
   ```

**Note**: Mobile devices need to grant camera permissions

## Performance

**System Requirements**
- CPU: Modern processor (2GHz+)
- RAM: 1GB available
- Webcam: Any resolution (640x480 minimum)
- Browser: Modern browser (last 2 years)

**Bandwidth (Local)**
- Video stream: ~1-2 MB/s
- Data stream: ~1 KB/s
- Negligible latency

## Troubleshooting

### Browser Can't Connect

**Problem**: "This site can't be reached"

**Solutions**:
- Ensure server is running (check terminal)
- Verify URL is `http://localhost:5000`
- Try `http://127.0.0.1:5000`
- Check firewall isn't blocking port 5000
- Ensure no other service is using port 5000

### Webcam Not Working

**Problem**: Black screen or "Could not open webcam"

**Solutions**:
- Close other apps using webcam (Zoom, Skype, etc.)
- Check browser camera permissions
- Try different browser
- Restart computer
- Check webcam is properly connected

### Video Lag

**Problem**: Video feed is choppy or delayed

**Solutions**:
- Close other browser tabs
- Reduce browser window size
- Check CPU usage (close unnecessary programs)
- Try wired connection if on WiFi
- Lower video resolution in app.py

### No Heart Rate Detected

**Problem**: Stuck on "Searching..."

**Solutions**:
- Improve lighting
- Move face closer to camera
- Ensure forehead is visible
- Remove hats or obstructions
- Check if face detection box appears
- Try different angle

### Incorrect Readings

**Problem**: Heart rate seems wrong

**Solutions**:
- Wait for buffer to reach 100%
- Check confidence indicator
- Reduce movement
- Improve lighting
- Reset and try again
- Verify you're not post-exercise

## Customization

### Change Port

Edit `app.py`:
```python
app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
```

### Adjust Buffer Size

Edit `app.py`:
```python
detector = HeartRateDetector(buffer_size=450, fps=fps)  # Larger = more stable
```

### Change Colors

Edit `templates/index.html` CSS section:
```css
.hr-value.normal { color: #00ff00; }  /* Normal heart rate color */
.hr-value.elevated { color: #ffaa00; }  /* Elevated color */
.hr-value.high { color: #ff4444; }  /* High/low color */
```

### Modify Graph

Edit `templates/index.html` JavaScript:
```javascript
const maxHistoryPoints = 100;  // Number of points to display
```

## Development

### Project Structure

```
heart_rate_monitor/
├── app.py                      # Flask backend server
├── heart_rate_detector.py      # Core detection algorithm
├── launch_web.py               # Launcher script
├── requirements.txt            # Python dependencies
├── templates/
│   └── index.html             # Frontend (HTML/CSS/JS)
└── static/                    # (Empty - no static files needed)
```

### Adding Features

**Example: Add logging**

In `app.py`:
```python
@app.route('/data_stream')
def data_stream():
    def generate():
        while True:
            with data_lock:
                data = current_data.copy()
            
            # Log data
            with open('hr_log.csv', 'a') as f:
                f.write(f"{data['timestamp']},{data['hr']}\n")
            
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.1)
    return Response(generate(), mimetype='text/event-stream')
```

## Security Notes

- ✅ Runs completely locally
- ✅ No external API calls
- ✅ No data collection
- ✅ No analytics or tracking
- ✅ Camera access only while "Start" is active
- ⚠️ If exposing to local network, consider adding authentication

## FAQ

**Q: Does this work offline?**
A: Yes! No internet connection needed.

**Q: Is my video recorded?**
A: No. Video is processed in real-time and immediately discarded.

**Q: Can I use this on multiple devices?**
A: Yes, access from any device on the same network.

**Q: How accurate is it?**
A: Accuracy depends on lighting and stillness. Not medical-grade.

**Q: Can I use it while exercising?**
A: Not recommended. Movement affects accuracy significantly.

**Q: Does it work with glasses?**
A: Yes, as long as forehead is visible.

**Q: Can I use external webcam?**
A: Yes. OpenCV will use the default camera.

## Credits

- **Photoplethysmography (PPG)** - Non-contact heart rate detection
- **OpenCV** - Computer vision library
- **Flask** - Lightweight web framework
- **Pure JavaScript** - No dependencies, fast and efficient

## License

Educational use only. Not for medical purposes.

---

**Remember**: This is not a medical device. For health concerns, consult a healthcare professional.
