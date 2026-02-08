#!/usr/bin/env python3
"""
Simple GUI for Real-time Heart Rate Detection
A clean, user-friendly interface with live video and heart rate display.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import numpy as np
from heart_rate_detector import HeartRateDetector
import time
from collections import deque


class HeartRateGUI:
    def __init__(self, window):
        self.window = window
        self.window.title("Heart Rate Monitor")
        self.window.geometry("1000x700")
        self.window.configure(bg='#1e1e1e')
        
        # Video capture
        self.cap = None
        self.detector = None
        self.is_running = False
        self.start_time = None
        
        # Heart rate history for graph
        self.hr_graph_data = deque(maxlen=100)
        self.graph_times = deque(maxlen=100)
        
        # Setup GUI
        self.setup_gui()
        
        # Bind window close event
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_gui(self):
        """Setup the GUI layout."""
        
        # Title
        title_frame = tk.Frame(self.window, bg='#1e1e1e')
        title_frame.pack(pady=10)
        
        title_label = tk.Label(
            title_frame, 
            text="❤️ Heart Rate Monitor", 
            font=('Arial', 24, 'bold'),
            fg='#ff4444',
            bg='#1e1e1e'
        )
        title_label.pack()
        
        # Main content frame
        content_frame = tk.Frame(self.window, bg='#1e1e1e')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left side - Video
        video_frame = tk.Frame(content_frame, bg='#2d2d2d', relief=tk.RAISED, borderwidth=2)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        video_title = tk.Label(
            video_frame,
            text="Live Video Feed",
            font=('Arial', 14, 'bold'),
            fg='#ffffff',
            bg='#2d2d2d'
        )
        video_title.pack(pady=5)
        
        self.video_label = tk.Label(video_frame, bg='#000000')
        self.video_label.pack(padx=10, pady=10)
        
        # Right side - Heart Rate Info
        info_frame = tk.Frame(content_frame, bg='#2d2d2d', relief=tk.RAISED, borderwidth=2)
        info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        info_frame.config(width=300)
        
        info_title = tk.Label(
            info_frame,
            text="Heart Rate Data",
            font=('Arial', 14, 'bold'),
            fg='#ffffff',
            bg='#2d2d2d'
        )
        info_title.pack(pady=10)
        
        # Current Heart Rate Display
        hr_display_frame = tk.Frame(info_frame, bg='#1a1a1a', relief=tk.SUNKEN, borderwidth=2)
        hr_display_frame.pack(pady=10, padx=10, fill=tk.X)
        
        tk.Label(
            hr_display_frame,
            text="Current Heart Rate",
            font=('Arial', 11),
            fg='#aaaaaa',
            bg='#1a1a1a'
        ).pack(pady=(10, 5))
        
        self.hr_value_label = tk.Label(
            hr_display_frame,
            text="--",
            font=('Arial', 48, 'bold'),
            fg='#00ff00',
            bg='#1a1a1a'
        )
        self.hr_value_label.pack()
        
        tk.Label(
            hr_display_frame,
            text="BPM",
            font=('Arial', 16),
            fg='#aaaaaa',
            bg='#1a1a1a'
        ).pack(pady=(0, 10))
        
        # Statistics Frame
        stats_frame = tk.Frame(info_frame, bg='#1a1a1a', relief=tk.SUNKEN, borderwidth=2)
        stats_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(
            stats_frame,
            text="Statistics",
            font=('Arial', 12, 'bold'),
            fg='#ffffff',
            bg='#1a1a1a'
        ).pack(pady=10)
        
        # Stats labels
        self.avg_label = self.create_stat_label(stats_frame, "Average:", "--")
        self.min_label = self.create_stat_label(stats_frame, "Minimum:", "--")
        self.max_label = self.create_stat_label(stats_frame, "Maximum:", "--")
        self.std_label = self.create_stat_label(stats_frame, "Std Dev:", "--")
        
        # Separator
        separator = tk.Frame(stats_frame, height=2, bg='#444444')
        separator.pack(fill=tk.X, padx=20, pady=10)
        
        # Status info
        self.status_label = self.create_stat_label(stats_frame, "Status:", "Not Started")
        self.buffer_label = self.create_stat_label(stats_frame, "Buffer:", "0%")
        self.confidence_label = self.create_stat_label(stats_frame, "Confidence:", "0%")
        
        # Simple heart rate graph
        graph_frame = tk.Frame(info_frame, bg='#1a1a1a', relief=tk.SUNKEN, borderwidth=2)
        graph_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(
            graph_frame,
            text="Heart Rate Trend",
            font=('Arial', 11, 'bold'),
            fg='#ffffff',
            bg='#1a1a1a'
        ).pack(pady=5)
        
        self.graph_canvas = tk.Canvas(
            graph_frame,
            width=260,
            height=120,
            bg='#000000',
            highlightthickness=0
        )
        self.graph_canvas.pack(pady=10, padx=10)
        
        # Control buttons at bottom
        button_frame = tk.Frame(self.window, bg='#1e1e1e')
        button_frame.pack(pady=10)
        
        self.start_button = tk.Button(
            button_frame,
            text="▶ Start",
            command=self.start_detection,
            font=('Arial', 14, 'bold'),
            bg='#00aa00',
            fg='#ffffff',
            activebackground='#00cc00',
            width=12,
            height=2,
            relief=tk.RAISED,
            borderwidth=3,
            cursor='hand2'
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(
            button_frame,
            text="⬛ Stop",
            command=self.stop_detection,
            font=('Arial', 14, 'bold'),
            bg='#aa0000',
            fg='#ffffff',
            activebackground='#cc0000',
            width=12,
            height=2,
            relief=tk.RAISED,
            borderwidth=3,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.reset_button = tk.Button(
            button_frame,
            text="↻ Reset",
            command=self.reset_detection,
            font=('Arial', 14, 'bold'),
            bg='#4444aa',
            fg='#ffffff',
            activebackground='#5555cc',
            width=12,
            height=2,
            relief=tk.RAISED,
            borderwidth=3,
            cursor='hand2'
        )
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
    def create_stat_label(self, parent, label_text, value_text):
        """Create a statistics label pair."""
        frame = tk.Frame(parent, bg='#1a1a1a')
        frame.pack(fill=tk.X, padx=20, pady=3)
        
        tk.Label(
            frame,
            text=label_text,
            font=('Arial', 10),
            fg='#aaaaaa',
            bg='#1a1a1a',
            anchor='w'
        ).pack(side=tk.LEFT)
        
        value_label = tk.Label(
            frame,
            text=value_text,
            font=('Arial', 10, 'bold'),
            fg='#ffffff',
            bg='#1a1a1a',
            anchor='e'
        )
        value_label.pack(side=tk.RIGHT)
        
        return value_label
        
    def start_detection(self):
        """Start heart rate detection."""
        try:
            # Initialize webcam
            self.cap = cv2.VideoCapture(0)
            
            if not self.cap.isOpened():
                messagebox.showerror("Error", "Could not open webcam!")
                return
            
            # Set webcam properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Get FPS
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0
            
            # Initialize detector
            self.detector = HeartRateDetector(buffer_size=300, fps=fps)
            
            self.is_running = True
            self.start_time = time.time()
            
            # Update button states
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            
            # Start video loop
            self.update_frame()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start: {str(e)}")
            
    def stop_detection(self):
        """Stop heart rate detection."""
        self.is_running = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # Update button states
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        # Update status
        self.status_label.config(text="Stopped")
        
    def reset_detection(self):
        """Reset all data."""
        if self.is_running:
            self.stop_detection()
        
        # Clear data
        if self.detector:
            self.detector.green_values.clear()
            self.detector.timestamps.clear()
            self.detector.hr_history.clear()
            self.detector.current_hr = 0
        
        self.hr_graph_data.clear()
        self.graph_times.clear()
        
        # Reset displays
        self.hr_value_label.config(text="--", fg='#00ff00')
        self.avg_label.config(text="--")
        self.min_label.config(text="--")
        self.max_label.config(text="--")
        self.std_label.config(text="--")
        self.status_label.config(text="Reset")
        self.buffer_label.config(text="0%")
        self.confidence_label.config(text="0%")
        
        # Clear graph
        self.graph_canvas.delete("all")
        
        # Clear video
        self.video_label.config(image='')
        
    def update_frame(self):
        """Update video frame and process heart rate."""
        if not self.is_running or not self.cap:
            return
        
        ret, frame = self.cap.read()
        
        if ret:
            # Flip for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Calculate timestamp
            timestamp = time.time() - self.start_time
            
            # Process frame
            annotated_frame, hr = self.detector.process_frame(frame, timestamp)
            
            # Resize for display (maintaining aspect ratio)
            display_width = 640
            display_height = 480
            annotated_frame = cv2.resize(annotated_frame, (display_width, display_height))
            
            # Convert to RGB for Tkinter
            frame_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            
            # Update video label
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)
            
            # Update heart rate display
            if hr > 0:
                self.hr_value_label.config(text=f"{hr:.0f}")
                
                # Color code based on heart rate
                if 60 <= hr <= 100:
                    self.hr_value_label.config(fg='#00ff00')  # Green - normal
                elif 100 < hr <= 120:
                    self.hr_value_label.config(fg='#ffaa00')  # Orange - elevated
                else:
                    self.hr_value_label.config(fg='#ff4444')  # Red - high/low
                
                # Update graph data
                self.hr_graph_data.append(hr)
                self.graph_times.append(timestamp)
                
                # Update statistics
                if self.detector.hr_history:
                    hrs = list(self.detector.hr_history)
                    self.avg_label.config(text=f"{np.mean(hrs):.1f} BPM")
                    self.min_label.config(text=f"{np.min(hrs):.1f} BPM")
                    self.max_label.config(text=f"{np.max(hrs):.1f} BPM")
                    self.std_label.config(text=f"{np.std(hrs):.1f}")
                    
                    # Update confidence
                    confidence = min(len(self.detector.hr_history) / 50.0, 1.0)
                    self.confidence_label.config(text=f"{confidence:.0%}")
                
                self.status_label.config(text="Detecting ✓")
            else:
                self.status_label.config(text="Searching...")
            
            # Update buffer status
            buffer_fill = len(self.detector.green_values) / self.detector.buffer_size
            self.buffer_label.config(text=f"{buffer_fill:.0%}")
            
            # Update graph
            self.draw_graph()
        
        # Schedule next update (30 FPS)
        self.window.after(33, self.update_frame)
    
    def draw_graph(self):
        """Draw simple heart rate graph."""
        self.graph_canvas.delete("all")
        
        if len(self.hr_graph_data) < 2:
            return
        
        # Canvas dimensions
        width = 260
        height = 120
        padding = 10
        
        # Get data
        hr_data = list(self.hr_graph_data)
        
        # Calculate scale
        if len(hr_data) > 0:
            min_hr = max(40, min(hr_data) - 10)
            max_hr = min(200, max(hr_data) + 10)
        else:
            min_hr = 40
            max_hr = 120
        
        hr_range = max_hr - min_hr
        
        # Draw grid lines
        for i in range(5):
            y = padding + (height - 2*padding) * i / 4
            self.graph_canvas.create_line(
                padding, y, width - padding, y,
                fill='#333333', width=1
            )
            
            # Draw HR labels
            hr_value = max_hr - (hr_range * i / 4)
            self.graph_canvas.create_text(
                5, y,
                text=f"{hr_value:.0f}",
                fill='#666666',
                font=('Arial', 7),
                anchor='w'
            )
        
        # Draw data line
        if len(hr_data) > 1:
            points = []
            for i, hr in enumerate(hr_data):
                x = padding + (width - 2*padding) * i / (len(hr_data) - 1)
                y = height - padding - (height - 2*padding) * (hr - min_hr) / hr_range
                points.extend([x, y])
            
            # Draw line
            self.graph_canvas.create_line(
                points,
                fill='#00ff00',
                width=2,
                smooth=True
            )
            
            # Draw points
            for i in range(0, len(points), 2):
                x, y = points[i], points[i+1]
                self.graph_canvas.create_oval(
                    x-2, y-2, x+2, y+2,
                    fill='#00ff00',
                    outline='#00ff00'
                )
    
    def on_closing(self):
        """Handle window closing."""
        self.stop_detection()
        self.window.destroy()


def main():
    """Run the GUI application."""
    root = tk.Tk()
    app = HeartRateGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
