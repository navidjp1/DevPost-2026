#!/usr/bin/env python3
"""
Flask backend for Heart Rate Monitor web interface
Streams video and heart rate data to browser via Server-Sent Events
"""

from flask import Flask, Response, jsonify
import cv2
import json
import time
import numpy as np
import sys
import os

# Check if heart_rate_detector exists
if not os.path.exists('heart_rate_detector.py'):
    print("ERROR: heart_rate_detector.py not found!")
    print("Please ensure heart_rate_detector.py is in the same directory as app.py")
    sys.exit(1)

from heart_rate_detector import HeartRateDetector
from collections import deque
import threading

app = Flask(__name__)

# Global state
detector = None
cap = None
is_running = False
current_data = {
    'hr': 0,
    'timestamp': 0,
    'buffer_fill': 0,
    'confidence': 0,
    'status': 'stopped',
    'stats': {
        'avg': 0,
        'min': 0,
        'max': 0,
        'std': 0
    }
}
data_lock = threading.Lock()
start_time = None


def generate_frames():
    """Generator function to yield video frames."""
    global detector, cap, is_running, current_data, start_time
    
    while True:
        if not is_running or cap is None:
            time.sleep(0.1)
            continue
            
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue
        
        try:
            # Flip for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Calculate timestamp
            timestamp = time.time() - start_time
            
            # Process frame with detector
            annotated_frame, hr = detector.process_frame(frame, timestamp)
            
            # Update global data
            with data_lock:
                current_data['hr'] = float(hr) if hr > 0 else 0
                current_data['timestamp'] = timestamp
                current_data['buffer_fill'] = len(detector.green_values) / detector.buffer_size
                
                if detector.hr_history:
                    hrs = list(detector.hr_history)
                    current_data['stats']['avg'] = float(np.mean(hrs))
                    current_data['stats']['min'] = float(np.min(hrs))
                    current_data['stats']['max'] = float(np.max(hrs))
                    current_data['stats']['std'] = float(np.std(hrs))
                    current_data['confidence'] = min(len(detector.hr_history) / 50.0, 1.0)
                
                current_data['status'] = 'detecting' if hr > 0 else 'searching'
            
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            
            # Yield frame in multipart format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            print(f"Error in generate_frames: {e}")
            time.sleep(0.1)


def generate_data_stream():
    """Generator function to yield Server-Sent Events with heart rate data."""
    global current_data
    
    while True:
        try:
            with data_lock:
                data = current_data.copy()
            
            # Format as Server-Sent Event
            yield f"data: {json.dumps(data)}\n\n"
            
            time.sleep(0.1)  # 10 Hz update rate
        except Exception as e:
            print(f"Error in generate_data_stream: {e}")
            time.sleep(0.1)


# Embedded HTML (no template folder needed)
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>❤️ Heart Rate Monitor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
            color: #ffffff;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            margin-bottom: 30px;
        }

        h1 {
            font-size: 2.5em;
            color: #ff4444;
            text-shadow: 0 0 10px rgba(255, 68, 68, 0.5);
            margin-bottom: 10px;
        }

        .subtitle {
            color: #aaaaaa;
            font-size: 1.1em;
        }

        .main-content {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }

        .video-section {
            flex: 2;
            background: #2d2d2d;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        }

        .video-title {
            font-size: 1.3em;
            margin-bottom: 15px;
            color: #ffffff;
            text-align: center;
        }

        .video-container {
            position: relative;
            width: 100%;
            background: #000000;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.8);
        }

        #videoFeed {
            width: 100%;
            height: auto;
            display: block;
        }

        .data-section {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .data-panel {
            background: #2d2d2d;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        }

        .panel-title {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #ffffff;
            text-align: center;
            border-bottom: 2px solid #444444;
            padding-bottom: 10px;
        }

        .hr-display {
            background: #1a1a1a;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }

        .hr-label {
            font-size: 0.9em;
            color: #aaaaaa;
            margin-bottom: 10px;
        }

        .hr-value {
            font-size: 4em;
            font-weight: bold;
            color: #00ff00;
            text-shadow: 0 0 20px rgba(0, 255, 0, 0.5);
            transition: color 0.3s ease;
        }

        .hr-value.normal { color: #00ff00; }
        .hr-value.elevated { color: #ffaa00; }
        .hr-value.high { color: #ff4444; }

        .hr-unit {
            font-size: 1.2em;
            color: #aaaaaa;
            margin-top: 5px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }

        .stat-item {
            background: #1a1a1a;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }

        .stat-label {
            font-size: 0.85em;
            color: #aaaaaa;
            margin-bottom: 5px;
        }

        .stat-value {
            font-size: 1.4em;
            font-weight: bold;
            color: #ffffff;
        }

        .progress-bar {
            background: #1a1a1a;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
        }

        .progress-label {
            font-size: 0.9em;
            color: #aaaaaa;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }

        .progress-track {
            height: 20px;
            background: #333333;
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00aa00 0%, #00ff00 100%);
            width: 0%;
            transition: width 0.3s ease;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
        }

        .graph-container {
            background: #1a1a1a;
            border-radius: 8px;
            padding: 15px;
            height: 200px;
        }

        #hrGraph {
            width: 100%;
            height: 100%;
        }

        .controls {
            display: flex;
            gap: 15px;
            justify-content: center;
        }

        .btn {
            padding: 15px 40px;
            font-size: 1.1em;
            font-weight: bold;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .btn-start {
            background: linear-gradient(135deg, #00aa00 0%, #00ff00 100%);
            color: #000000;
        }

        .btn-start:hover:not(:disabled) {
            background: linear-gradient(135deg, #00cc00 0%, #00ff44 100%);
        }

        .btn-stop {
            background: linear-gradient(135deg, #aa0000 0%, #ff0000 100%);
            color: #ffffff;
        }

        .btn-stop:hover:not(:disabled) {
            background: linear-gradient(135deg, #cc0000 0%, #ff4444 100%);
        }

        .btn-reset {
            background: linear-gradient(135deg, #4444aa 0%, #6666ff 100%);
            color: #ffffff;
        }

        .btn-reset:hover:not(:disabled) {
            background: linear-gradient(135deg, #5555cc 0%, #7777ff 100%);
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        .status-stopped { background: #666666; animation: none; }
        .status-searching { background: #ffaa00; }
        .status-detecting { background: #00ff00; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .instructions {
            background: #2d2d2d;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
            border-left: 4px solid #ff4444;
        }

        .instructions h3 {
            color: #ff4444;
            margin-bottom: 10px;
        }

        .instructions ul {
            list-style: none;
            padding-left: 0;
        }

        .instructions li {
            padding: 5px 0;
            color: #cccccc;
        }

        .instructions li:before {
            content: "✓ ";
            color: #00ff00;
            font-weight: bold;
            margin-right: 8px;
        }

        @media (max-width: 1024px) {
            .main-content {
                flex-direction: column;
            }
        }

        @media (max-width: 640px) {
            h1 {
                font-size: 2em;
            }

            .hr-value {
                font-size: 3em;
            }

            .controls {
                flex-direction: column;
            }

            .btn {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>❤️ Heart Rate Monitor</h1>
            <p class="subtitle">Real-time heart rate detection using your webcam</p>
        </header>

        <div class="main-content">
            <!-- Video Section -->
            <div class="video-section">
                <h2 class="video-title">Live Video Feed</h2>
                <div class="video-container">
                    <img id="videoFeed" src="/video_feed" alt="Video Feed">
                </div>
            </div>

            <!-- Data Section -->
            <div class="data-section">
                <!-- Heart Rate Display -->
                <div class="data-panel">
                    <h3 class="panel-title">Heart Rate</h3>
                    <div class="hr-display">
                        <div class="hr-label">Current Heart Rate</div>
                        <div id="hrValue" class="hr-value normal">--</div>
                        <div class="hr-unit">BPM</div>
                    </div>
                </div>

                <!-- Statistics -->
                <div class="data-panel">
                    <h3 class="panel-title">Statistics</h3>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-label">Average</div>
                            <div id="statAvg" class="stat-value">--</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Minimum</div>
                            <div id="statMin" class="stat-value">--</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Maximum</div>
                            <div id="statMax" class="stat-value">--</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Std Dev</div>
                            <div id="statStd" class="stat-value">--</div>
                        </div>
                    </div>
                </div>

                <!-- Progress Indicators -->
                <div class="data-panel">
                    <h3 class="panel-title">Status</h3>
                    
                    <div class="progress-bar">
                        <div class="progress-label">
                            <span>
                                <span id="statusIndicator" class="status-indicator status-stopped"></span>
                                <span id="statusText">Stopped</span>
                            </span>
                        </div>
                    </div>

                    <div class="progress-bar">
                        <div class="progress-label">
                            <span>Buffer</span>
                            <span id="bufferPercent">0%</span>
                        </div>
                        <div class="progress-track">
                            <div id="bufferFill" class="progress-fill"></div>
                        </div>
                    </div>

                    <div class="progress-bar">
                        <div class="progress-label">
                            <span>Confidence</span>
                            <span id="confidencePercent">0%</span>
                        </div>
                        <div class="progress-track">
                            <div id="confidenceFill" class="progress-fill"></div>
                        </div>
                    </div>
                </div>

                <!-- Graph -->
                <div class="data-panel">
                    <h3 class="panel-title">Heart Rate Trend</h3>
                    <div class="graph-container">
                        <canvas id="hrGraph"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- Controls -->
        <div class="controls">
            <button id="startBtn" class="btn btn-start">▶ Start</button>
            <button id="stopBtn" class="btn btn-stop" disabled>⬛ Stop</button>
            <button id="resetBtn" class="btn btn-reset">↻ Reset</button>
        </div>

        <!-- Instructions -->
        <div class="instructions">
            <h3>Tips for Best Results</h3>
            <ul>
                <li>Keep your face centered and visible</li>
                <li>Ensure good, even lighting on your face</li>
                <li>Stay still during measurement</li>
                <li>Wait ~10 seconds for accurate readings</li>
                <li>Forehead should be clearly visible</li>
            </ul>
        </div>
    </div>

    <script>
        // State
        let eventSource = null;
        let hrHistory = [];
        const maxHistoryPoints = 100;

        // Elements
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const resetBtn = document.getElementById('resetBtn');
        const hrValue = document.getElementById('hrValue');
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const bufferFill = document.getElementById('bufferFill');
        const bufferPercent = document.getElementById('bufferPercent');
        const confidenceFill = document.getElementById('confidenceFill');
        const confidencePercent = document.getElementById('confidencePercent');
        const statAvg = document.getElementById('statAvg');
        const statMin = document.getElementById('statMin');
        const statMax = document.getElementById('statMax');
        const statStd = document.getElementById('statStd');
        const canvas = document.getElementById('hrGraph');
        const ctx = canvas.getContext('2d');

        // Set canvas size
        function resizeCanvas() {
            const container = canvas.parentElement;
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
            drawGraph();
        }
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);

        // Start detection
        startBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/start', { method: 'POST' });
                const data = await response.json();
                
                if (data.status === 'started') {
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                    connectEventSource();
                } else {
                    alert('Error: ' + (data.message || 'Could not start'));
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        });

        // Stop detection
        stopBtn.addEventListener('click', async () => {
            try {
                await fetch('/stop', { method: 'POST' });
                startBtn.disabled = false;
                stopBtn.disabled = true;
                disconnectEventSource();
                updateStatus('stopped', 'Stopped');
            } catch (error) {
                alert('Error: ' + error.message);
            }
        });

        // Reset
        resetBtn.addEventListener('click', async () => {
            try {
                await fetch('/reset', { method: 'POST' });
                startBtn.disabled = false;
                stopBtn.disabled = true;
                disconnectEventSource();
                resetDisplay();
            } catch (error) {
                alert('Error: ' + error.message);
            }
        });

        // Connect to data stream
        function connectEventSource() {
            if (eventSource) {
                eventSource.close();
            }

            eventSource = new EventSource('/data_stream');

            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDisplay(data);
            };

            eventSource.onerror = (error) => {
                console.error('EventSource error:', error);
            };
        }

        // Disconnect event source
        function disconnectEventSource() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        }

        // Update display with new data
        function updateDisplay(data) {
            // Heart rate value
            if (data.hr > 0) {
                hrValue.textContent = Math.round(data.hr);
                
                // Color coding
                if (data.hr >= 60 && data.hr <= 100) {
                    hrValue.className = 'hr-value normal';
                } else if (data.hr > 100 && data.hr <= 120) {
                    hrValue.className = 'hr-value elevated';
                } else {
                    hrValue.className = 'hr-value high';
                }

                // Add to history
                hrHistory.push(data.hr);
                if (hrHistory.length > maxHistoryPoints) {
                    hrHistory.shift();
                }
                drawGraph();
            }

            // Status
            updateStatus(data.status, 
                data.status === 'detecting' ? 'Detecting ✓' :
                data.status === 'searching' ? 'Searching...' :
                data.status === 'started' ? 'Started' :
                data.status === 'stopped' ? 'Stopped' : 
                data.status === 'reset' ? 'Reset' : 'Unknown'
            );

            // Progress bars
            const bufferPct = Math.round(data.buffer_fill * 100);
            bufferFill.style.width = bufferPct + '%';
            bufferPercent.textContent = bufferPct + '%';

            const confidencePct = Math.round(data.confidence * 100);
            confidenceFill.style.width = confidencePct + '%';
            confidencePercent.textContent = confidencePct + '%';

            // Statistics
            if (data.stats.avg > 0) {
                statAvg.textContent = data.stats.avg.toFixed(1);
                statMin.textContent = data.stats.min.toFixed(1);
                statMax.textContent = data.stats.max.toFixed(1);
                statStd.textContent = data.stats.std.toFixed(1);
            }
        }

        // Update status indicator
        function updateStatus(status, text) {
            statusText.textContent = text;
            statusIndicator.className = 'status-indicator status-' + status;
        }

        // Draw heart rate graph
        function drawGraph() {
            if (!ctx || hrHistory.length === 0) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                return;
            }

            const width = canvas.width;
            const height = canvas.height;
            const padding = 30;

            // Clear canvas
            ctx.clearRect(0, 0, width, height);

            // Calculate scale
            const minHR = Math.max(40, Math.min(...hrHistory) - 10);
            const maxHR = Math.min(200, Math.max(...hrHistory) + 10);
            const hrRange = maxHR - minHR;

            // Draw grid
            ctx.strokeStyle = '#333333';
            ctx.lineWidth = 1;

            for (let i = 0; i <= 4; i++) {
                const y = padding + (height - 2 * padding) * i / 4;
                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(width - padding, y);
                ctx.stroke();

                // Draw HR labels
                const hrValue = maxHR - (hrRange * i / 4);
                ctx.fillStyle = '#666666';
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'right';
                ctx.fillText(Math.round(hrValue), padding - 5, y + 4);
            }

            // Draw line
            if (hrHistory.length > 1) {
                ctx.strokeStyle = '#00ff00';
                ctx.lineWidth = 2;
                ctx.beginPath();

                for (let i = 0; i < hrHistory.length; i++) {
                    const x = padding + (width - 2 * padding) * i / (hrHistory.length - 1);
                    const y = height - padding - (height - 2 * padding) * (hrHistory[i] - minHR) / hrRange;

                    if (i === 0) {
                        ctx.moveTo(x, y);
                    } else {
                        ctx.lineTo(x, y);
                    }
                }

                ctx.stroke();

                // Draw points
                ctx.fillStyle = '#00ff00';
                for (let i = 0; i < hrHistory.length; i++) {
                    const x = padding + (width - 2 * padding) * i / (hrHistory.length - 1);
                    const y = height - padding - (height - 2 * padding) * (hrHistory[i] - minHR) / hrRange;
                    
                    ctx.beginPath();
                    ctx.arc(x, y, 3, 0, 2 * Math.PI);
                    ctx.fill();
                }
            }
        }

        // Reset display
        function resetDisplay() {
            hrValue.textContent = '--';
            hrValue.className = 'hr-value normal';
            statAvg.textContent = '--';
            statMin.textContent = '--';
            statMax.textContent = '--';
            statStd.textContent = '--';
            bufferFill.style.width = '0%';
            bufferPercent.textContent = '0%';
            confidenceFill.style.width = '0%';
            confidencePercent.textContent = '0%';
            updateStatus('stopped', 'Reset');
            hrHistory = [];
            drawGraph();
        }

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            disconnectEventSource();
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Serve the main HTML page."""
    return HTML_PAGE


@app.route('/video_feed')
def video_feed():
    """Video streaming route."""
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/data_stream')
def data_stream():
    """Server-Sent Events stream for heart rate data."""
    return Response(
        generate_data_stream(),
        mimetype='text/event-stream'
    )


@app.route('/start', methods=['POST'])
def start():
    """Start heart rate detection."""
    global detector, cap, is_running, start_time, current_data
    
    if is_running:
        return jsonify({'status': 'already_running'})
    
    try:
        # Initialize webcam
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            return jsonify({'status': 'error', 'message': 'Could not open webcam'})
        
        # Set webcam properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Get FPS
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0
        
        # Initialize detector
        detector = HeartRateDetector(buffer_size=300, fps=fps)
        
        is_running = True
        start_time = time.time()
        
        with data_lock:
            current_data['status'] = 'started'
        
        return jsonify({'status': 'started', 'fps': fps})
        
    except Exception as e:
        print(f"Error starting: {e}")
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/stop', methods=['POST'])
def stop():
    """Stop heart rate detection."""
    global cap, is_running, current_data
    
    is_running = False
    
    if cap:
        cap.release()
        cap = None
    
    with data_lock:
        current_data['status'] = 'stopped'
    
    return jsonify({'status': 'stopped'})


@app.route('/reset', methods=['POST'])
def reset():
    """Reset all data."""
    global detector, cap, is_running, current_data
    
    # Stop if running
    if is_running:
        is_running = False
        if cap:
            cap.release()
            cap = None
    
    # Clear detector data
    if detector:
        detector.green_values.clear()
        detector.timestamps.clear()
        detector.hr_history.clear()
        detector.current_hr = 0
    
    # Reset current data
    with data_lock:
        current_data = {
            'hr': 0,
            'timestamp': 0,
            'buffer_fill': 0,
            'confidence': 0,
            'status': 'reset',
            'stats': {
                'avg': 0,
                'min': 0,
                'max': 0,
                'std': 0
            }
        }
    
    return jsonify({'status': 'reset'})


if __name__ == '__main__':
    print("="*60)
    print("  ❤️  Heart Rate Monitor - Web Interface")
    print("="*60)
    print("\nStarting server...")
    print("\n👉 Open your browser and navigate to:")
    print("   http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    print("="*60)
    print()
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        if cap:
            cap.release()
    except Exception as e:
        print(f"\n\nError: {e}")
        if cap:
            cap.release()
