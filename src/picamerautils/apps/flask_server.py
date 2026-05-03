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
from picamerautils.controllers.hq_camera import PiCameraCapture,VideoCamera,EXPOSURE_LIST,GAIN_LIST

width = int(sys.argv[1])
height = int(sys.argv[2])
framerate = int(sys.argv[3])

app = Flask(__name__)

# Define the current session index for connected sessions
current_index = 0


sleep_time = (1 / (framerate+2))

camera = VideoCamera(width,height,framerate)

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
    exposure_to_set = EXPOSURE_LIST[slider_value_to_update]
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
    gain_to_set = GAIN_LIST[slider_value_to_update]
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
    <!DOCTYPE html>
    <html>
        <head>
            <title>GStreamer Stream</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
            <style>
                body {{
                    background-color: #1a1a1a;
                    color: white;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    text-align: center;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                }}
                h2 {{ margin-bottom: 10px; font-weight: 300; }}
                .stream-container {{
                    width: 95%;
                    max-width: 640px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.5);
                    border-radius: 12px;
                    overflow: hidden;
                    background-color: black;
                }}
                .slidecontainer {{
                /* Container padding helps prevent accidental screen edge swipes */
                    padding: 20px;
                    width: 100%;
                }}
                .slider {{
                    -webkit-appearance: none;  /* Hides default styles */
                    width: 100%;               /* Full width for easier touch */
                    height: 10px;              /* Thicker track for mobile */
                    background: #ddd;
                    border-radius: 5px;
                    outline: none;
                }}
                img {{
                    width: 100%;
                    height: auto;
                    display: block;
                }}
            </style>
        </head>
        <body>
            {generate_slider_html(EXPOSURE_LIST, "exposure", camera.exposure_index)}
            {generate_slider_html(GAIN_LIST, "gain", camera.gain_index)}
            <h2>Live Stream</h2>
            <div class="stream-container">
                <img src="/video_feed" width="{width}" height="{height}" />
            </div>
            <form method="POST">
                <label>
                    <input type="radio" name="hvflip" value="Upright" onchange="this.form.submit()"> Option 1
                </label><br>
                <label>
                    <input type="radio" name="hvflip" value="UpsideDown" onchange="this.form.submit()"> Option 2
                </label><br>
            </form>
        </body>
    </html>
    '''

    return stringsss

def main():
    app.run(host="0.0.0.0", port=5000, threaded=True)

if __name__ == "__main__":
    main()
