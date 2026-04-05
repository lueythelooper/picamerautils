from flask import Flask, Response
import cv2
import time
import threading
import queue
import sys

width = int(sys.argv[1])
height = int(sys.argv[2])
framerate = int(sys.argv[3])

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
            if frame is not None:
                if ret:
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
