#!/usr/bin/env python3
"""
Quick launcher for Heart Rate Monitor GUI
"""

import sys
import subprocess

def check_dependencies():
    """Check if required packages are installed."""
    required = ['cv2', 'numpy', 'scipy', 'PIL', 'matplotlib']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("⚠️  Missing required packages!")
        print("\nPlease install dependencies by running:")
        print("  pip install -r requirements.txt")
        print("\nMissing packages:", ', '.join(missing))
        return False
    
    return True

def main():
    print("="*60)
    print("  ❤️  Heart Rate Monitor - GUI Launcher")
    print("="*60)
    print()
    
    if not check_dependencies():
        sys.exit(1)
    
    print("✓ All dependencies found")
    print("\nStarting Heart Rate Monitor GUI...")
    print("\nInstructions:")
    print("  1. Click 'Start' to begin monitoring")
    print("  2. Keep your face visible and still")
    print("  3. Wait ~10 seconds for accurate readings")
    print("  4. Click 'Stop' when done")
    print()
    print("="*60)
    print()
    
    # Import and run GUI
    try:
        from heart_rate_gui import main as run_gui
        run_gui()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
