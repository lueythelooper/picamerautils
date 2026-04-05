from flask import Flask, Response
import cv2

app = Flask(__name__)

# GStreamer pipeline (modify as needed)
PIPELINE = (
    "fdsrc fd=0 ! h264parse ! avdec_h264 ! videoconvert ! appsink"
)

# Open pipeline via OpenCV
#cap = cv2.VideoCapture(PIPELINE, cv2.CAP_GSTREAMER)
cap = cv2.VideoCapture("/dev/stdin")
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640);
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480);

def generate_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break

        # Encode as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/')
def index():
    return """
    <html>
        <body>
            <h1>GStreamer Live Stream</h1>
            <img src="/video">
        </body>
    </html>
    """


@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
