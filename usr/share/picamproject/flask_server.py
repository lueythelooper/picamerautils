from flask import Flask, Response
import cv2
import threading
import queue
import sys

width = int(sys.argv[1])
height = int(sys.argv[2])

app = Flask(__name__)

# Define the current session index for connected sessions
current_index = 0

class VideoCamera:
    def __init__(self):
        # Open pipeline via OpenCV
        self.cap = cv2.VideoCapture("/dev/stdin")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width);
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height);
        self.frame = None
        self.lock = threading.Lock()
        self.running = True

        thread = threading.Thread(target=self.update, daemon=True)
        thread.start()

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def get_frame(self):
        with self.lock:
            if self.frame is None:
                return None
            ret, jpeg = cv2.imencode('.jpg', self.frame)
            return jpeg.tobytes() if ret else None

camera = VideoCamera()

def generate_frames():
    while True:
        frame = camera.get_frame()
        if frame is None:
            continue

        # Encode as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def generate():
    while True:
        frame = camera.get_frame()
        if frame is None:
            continue

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
