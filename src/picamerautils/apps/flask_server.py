from flask import Flask, Response, request, jsonify
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

exposure_list = [1000,5000,10000,15000,20000,30000,40000,50000,70000,100000,500000,1000000,2000000,5000000,10000000]
gain_list = [1,2,3,4,5,7,10,15,20]

sleep_time = (1 / (framerate+2))

class PiCameraCapture:
    # Define some constants
    ANALOG_GAIN = 1

    """
    Initialize the camera capture class

    Provide width and height
    """
    def __init__(self, width, height):
        self._width = width
        self._height = height

        # Initialize the picam object
        self.picam2 = Picamera2()
        camera_config = self.picam2.create_video_configuration({"format": "BGR888", "size": (self._width,self._height)}, transform=Transform(hflip=0,vflip=0),
          controls={"FrameDurationLimits": (exposure_list[0], exposure_list[-1])})
        self.picam2.configure(camera_config)
        self.picam2.controls.ExposureTime = exposure_list[0]
        self.picam2.controls.AnalogueGain = gain_list[0]

        self.picam2.start()

    def __del__(self):
        self.picam2.stop()

    def get_frame(self):
        return self.picam2.capture_array()

class VideoCamera:
    def __init__(self):
        # Open pipeline via OpenCV
        self.cap = PiCameraCapture(width,height)
        self.raw_frame = None
        self.rgb_image = None
        self.frame = None
        self.lock = threading.Lock()
        self.jpeg = None
        self.running = True
        self.grabbed_frames = 0

        thread = threading.Thread(target=self.update, daemon=True)
        thread.start()

        self.gain_index = 0
        self.exposure_index = 0

    def update(self):
        start_time = time.perf_counter()
        while self.running:
            self.raw_frame = self.cap.get_frame()
            if self.raw_frame is not None:
                self.grabbed_frames += 1
                self.rgb_image = cv2.cvtColor(self.raw_frame, cv2.COLOR_BGR2RGB)
                ret, self.jpeg = cv2.imencode('.jpg', self.rgb_image)
                if ret:
                    with self.lock:
                        self.frame = self.jpeg.tobytes()
            if self.grabbed_frames % 100 == 0:
                print (f"Average framerate: { self.grabbed_frames / (time.perf_counter() - start_time) }")
            time.sleep(sleep_time/2)

    def get_frame(self):
        with self.lock:
            return self.frame

camera = VideoCamera()

frames_unsafe = 0

def generate():
    # Preallocate a numpy array for the frame
    frame = None
    while True:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(sleep_time)
            continue

        global frames_unsafe
        frames_unsafe += 1

        if frames_unsafe % 100 == 0:
            print (f"Average framerate: { frames_unsafe / (time.perf_counter() - start_time_unsafe) }")

        time.sleep(sleep_time)

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    global start_time_unsafe
    start_time_unsafe = time.perf_counter()
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/update_exposure', methods=['POST'])
def update_exposure():
    data = request.get_json()
    slider_value = data.get('value')

    slider_value_to_update = int(slider_value)
    exposure_to_set = exposure_list[slider_value_to_update]
    app.logger.info("Slider: ", slider_value_to_update, " and exposure: ", exposure_to_set)
    camera.cap.picam2.controls.ExposureTime = exposure_to_set

    camera.exposure_index = slider_value_to_update
    
    # Process value (e.g., update a database or control a device)
    print(f"Slider value received: {slider_value}")
    return jsonify({"status": "success", "received_value": exposure_to_set})

@app.route('/update_gain', methods=['POST'])
def update_gain():
    data = request.get_json()
    slider_value = data.get('value')

    slider_value_to_update = int(slider_value)
    app.logger.info("Slider: ", slider_value_to_update)
    gain_to_set = gain_list[slider_value_to_update]
    camera.cap.picam2.controls.AnalogueGain = gain_to_set

    camera.gain_index = slider_value_to_update 
    
    # Process value (e.g., update a database or control a device)
    print(f"Slider value received: {slider_value}")
    return jsonify({"status": "success", "received_value": gain_to_set})

def generate_slider_html(slider_values, slider_name, current_index):
    app.logger.info(len(slider_values)-1)
    div_class_string = f'''<label for="volume">{slider_name} ({slider_values[0]}-{slider_values[-1]}):</label>
    <div class="slidecontainer">
        <label for="{slider_name}">{slider_name}:</label>
        <input type="range" min="0" max="{len(slider_values)-1}" value="{current_index}" class="slider" id="{slider_name}">
        <p>Value: <span id="{slider_name}Value">1</span></p>
    </div>'''

    js_string = f'''<script>
            const {slider_name}slider = document.getElementById("{slider_name}");
            const {slider_name}output = document.getElementById("{slider_name}Value");
            {slider_name}slider.oninput = function() {{
                const val = this.value;
                {slider_name}output.innerHTML = val; // Immediate UI update

                // Send value to Flask backend
                fetch('/update_{slider_name}', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ value: val }})
                }})
                .then(response => response.json())
                .then(data => console.log('Server response:', data))
                .catch(error => console.error('Error:', error));
            }}
        </script>'''

    return div_class_string + js_string


@app.route('/')
def index():
    stringsss = f'''
    <html>
        <head><title>GStreamer Stream</title></head>
        <body>
            <h1>Live Stream</h1>
            {generate_slider_html(exposure_list, "exposure", camera.exposure_index)}
            {generate_slider_html(gain_list, "gain", camera.gain_index)}
            <img src="/video_feed" width="{width}" height="{height}" />
        </body>
    </html>
    '''

    return stringsss

def main():
    app.run(host="0.0.0.0", port=5000, threaded=True)

if __name__ == "__main__":
    main()
