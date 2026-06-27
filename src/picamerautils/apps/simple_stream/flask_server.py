from flask import Flask, Response, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
import time
import threading
import queue
import sys
from picamera2 import Picamera2, Preview
from libcamera import Transform
from libcamera import controls
from picamerautils.controllers.hq_camera import PiCameraCapture,FramerateLoadBalancer,EXPOSURE_LIST,GAIN_LIST
from picamerautils.controllers.queue_splitter import QueueSplitter
from picamerautils.recorder.video_recorder import VideoRecorder, COMMAND_RECORD, COMMAND_STOP
from picamerautils.motion_detector.motion_detector import MotionDetectorProcess


width = int(sys.argv[1])
height = int(sys.argv[2])
framerate = int(sys.argv[3])

sleep_time = 1/framerate

OUT_WIDTH = 720
OUT_HEIGHT = 480

video_input_queue = queue.Queue()
to_framerate_output_queue = queue.Queue()
to_recorder_output_queue = queue.Queue()
to_recorder_command_queue = queue.Queue()
queue_splitter = QueueSplitter(video_input_queue)
queue_splitter.add_output_queue(to_framerate_output_queue)
queue_splitter.add_output_queue(to_recorder_output_queue)
framerate_balancer = FramerateLoadBalancer(to_framerate_output_queue, framerate)
hq_camera_controller = PiCameraCapture(width,height,video_input_queue,framerate)
# video_recorder = VideoRecorder(to_recorder_output_queue,to_recorder_command_queue,"/mnt/data/", (width,height), framerate)
video_recorder = MotionDetectorProcess(to_recorder_output_queue,"/mnt/data/", (width,height), framerate)

app = Flask(__name__)
CORS(app)

# Define the current session index for connected sessions
current_index = 0
frames_unsafe = 0

def generate():
    # Preallocate a numpy array for the frame
    frame = None
    while True:
        frame = framerate_balancer.get_frame()
        if frame is None:
            time.sleep(0.1)
            continue

        resize_frame = cv2.resize(frame, (OUT_WIDTH,OUT_HEIGHT))
        ret, jpeg = cv2.imencode('.jpg', resize_frame)

        global frames_unsafe
        global start_time_unsafe 
        frames_unsafe += 1

        time.sleep(sleep_time)

        if frames_unsafe == 100:
            print (f"Average framerate generator: { frames_unsafe / (time.perf_counter() - start_time_unsafe) }")
            frames_unsafe = 0
            start_time_unsafe = time.perf_counter()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    global start_time_unsafe
    start_time_unsafe = time.perf_counter()
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/update_gain', methods=['POST'])
def update_gain():
    data = request.get_json()
    slider_value = data.get('value')

    slider_value_to_update = int(slider_value)
    app.logger.info("Slider: ", slider_value_to_update)
    gain_to_set = GAIN_LIST[slider_value_to_update]
    hq_camera_controller.change_gain(slider_value_to_update)
    
    # Process value (e.g., update a database or control a device)
    print(f"Slider value received: {slider_value}")
    return jsonify({"status": "success", "received_value": slider_value_to_update, "control_value": gain_to_set})

@app.route('/update_exposure', methods=['POST'])
def update_exposure():
    data = request.get_json()
    slider_value = data.get('value')

    slider_value_to_update = int(slider_value)
    app.logger.info("Slider: ", slider_value_to_update)
    exposure_to_set = EXPOSURE_LIST[slider_value_to_update]
    hq_camera_controller.change_exposure(slider_value_to_update)
    
    # Process value (e.g., update a database or control a device)
    print(f"Slider value received: {slider_value}")
    return jsonify({"status": "success", "received_value": slider_value_to_update, "control_value": exposure_to_set})

@app.route('/start_record', methods=['POST'])
def start_record():
    to_recorder_command_queue.put(COMMAND_RECORD)
    
    # Process value (e.g., update a database or control a device)
    print(f"START RECORDING")
    return jsonify({"status": "success"})

@app.route('/stop_record', methods=['POST'])
def stop_record():
    to_recorder_command_queue.put(COMMAND_STOP)
    
    # Process value (e.g., update a database or control a device)
    print(f"STOP_RECORDING")
    return jsonify({"status": "success"})



def main():
    queue_splitter.start()
    hq_camera_controller.start()
    framerate_balancer.start()
    video_recorder.start()

    app.run(host="0.0.0.0", port=5000, threaded=True)
    video_recorder.stop()
    framerate_balancer.stop()
    queue_splitter.stop()
    hq_camera_controller.stop()

# Define a unit test that can run this class()
running = True
# 2. Define the signal handler function
def handle_stop_signal(signum, frame):
    global running
    running = False  # Change flag to break the loop safely

if __name__ == "__main__":
    main()
