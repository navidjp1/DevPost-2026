#!/usr/bin/env python3
"""
Launcher for Heart Rate Monitor Web Interface
"""

import sys
import webbrowser
import time
import threading

def check_dependencies():
    """Check if required packages are installed."""
    required = {
        'cv2': 'opencv-python',
        'numpy': 'numpy',
        'scipy': 'scipy',
        'flask': 'Flask'
    }
    missing = []
    
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("⚠️  Missing required packages!")
        print("\nPlease install dependencies by running:")
        print("  pip install -r requirements.txt")
        print("\nMissing packages:", ', '.join(missing))
        return False
    
    return True

def open_browser():
    """Open browser after a short delay."""
    time.sleep(2)
    webbrowser.open('http://localhost:5000')

def main():
    print("="*60)
    print("  ❤️  Heart Rate Monitor - Web Interface")
    print("="*60)
    print()
    
    if not check_dependencies():
        sys.exit(1)
    
    print("✓ All dependencies found")
    print("\nStarting web server...")
    print("\n👉 The application will open in your browser automatically")
    print("   URL: http://localhost:5000")
    print("\nInstructions:")
    print("  1. Click 'Start' to begin monitoring")
    print("  2. Allow browser to access your webcam")
    print("  3. Keep your face visible and still")
    print("  4. Wait ~10 seconds for accurate readings")
    print("\nPress Ctrl+C to stop the server")
    print("="*60)
    print()
    
    # Open browser in background thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Import and run Flask app
    try:
        from app import app
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
