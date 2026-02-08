#!/usr/bin/env python3
"""
Flask backend for Heart Rate Monitor web interface
Streams video and heart rate data to browser via Server-Sent Events
"""

from flask import Flask, Response, render_template, jsonify
import cv2
import json
import time
import numpy as np
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


def generate_data_stream():
    """Generator function to yield Server-Sent Events with heart rate data."""
    global current_data
    
    while True:
        with data_lock:
            data = current_data.copy()
        
        # Format as Server-Sent Event
        yield f"data: {json.dumps(data)}\n\n"
        
        time.sleep(0.1)  # 10 Hz update rate


@app.route('/')
def index():
    """Serve the main HTML page."""
    return render_template('index.html')


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
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
