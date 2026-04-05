from flask import Flask, Response
import cv2
import numpy as np
import time
import threading
import queue
import sys
from picamera2 import Picamera2, Preview
from libcamera import Transform
from libcamera import controls

width = int(sys.argv[1])
height = int(sys.argv[2])
framerate = int(sys.argv[3])

app = Flask(__name__)

# Define the current session index for connected sessions
current_index = 0

class PiCameraCapture:
    # Define some constants
    ANALOG_GAIN = 10

    """
    Initialize the camera capture class

    Provide width and height
    """
    def __init__(self, width, height):
        self._width = width
        self._height = height

        # Initialize the picam object
        self.picam2 = Picamera2()
        camera_config = self.picam2.create_still_configuration({"format": "BGR888", "size": (self._width,self._height)}, transform=Transform(hflip=0,vflip=0))
        self.picam2.configure(camera_config)

        self.picam2.start()
        self.picam2.set_controls({"AnalogueGain": self.ANALOG_GAIN})

    def __del__(self):
        self.picam2.stop()

    def get_frame(self):
        return self.picam2.capture_array()

class VideoCamera:
    def __init__(self):
        # Open pipeline via OpenCV
        self.cap = PiCameraCapture(width,height)
        self.frame = None
        self.lock = threading.Lock()
        self.running = True

        thread = threading.Thread(target=self.update, daemon=True)
        thread.start()

    def update(self):
        while self.running:
            frame = self.cap.get_frame()
            if frame is not None:
                ret, jpeg = cv2.imencode('.jpg', frame)
                if ret:
                    with self.lock:
                        self.frame = jpeg.tobytes()

    def get_frame(self):
        with self.lock:
            return self.frame

camera = VideoCamera()

sleep_time = (1 / (framerate+1))

def generate():
    # Preallocate a numpy array for the frame
    frame = None
    while True:
        frame = camera.get_frame()
        if frame is None:
            continue
        time.sleep(sleep_time)

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return f'''
    <html>
        <head><title>GStreamer Stream</title></head>
        <body>
            <h1>Live Stream</h1>
            <img src="/video_feed" width="{width}" height="{height}" />
        </body>
    </html>
    '''

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
