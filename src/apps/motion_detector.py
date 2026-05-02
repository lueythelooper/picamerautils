from picamera2 import Picamera2, Preview
from libcamera import Transform
from libcamera import controls
import time
import cv2
import os
from datetime import datetime

DIRECTORY = "/data/motiondetector/"


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

class MotionDetector():
    ALPHA_BACKGROUND = 0.05

    def __init__(self):
        self.first_frame = True

    def detect_motion(self, frame):
        # 1. Preprocess the frame
        # Convert to grayscale and apply Gaussian blur to reduce noise
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (41, 41), 0)

        if self.first_frame:
            self.current_background = gray
            self.first_frame = False
            return False
        self.current_background = cv2.addWeighted(gray, self.ALPHA_BACKGROUND, self.current_background, 1-self.ALPHA_BACKGROUND, 0)
        # 2. Calculate the difference between the current frame and the first frame
        frame_delta = cv2.absdiff(self.current_background, gray)

        # 3. Apply a threshold to isolate significant changes (motion areas)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]

        # Dilate the thresholded image to fill in holes (optional, but helps with finding contours)
        thresh = cv2.dilate(thresh, None, iterations=2)

        # 4. Find contours of the moving objects
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        countour_count = len(contours)

        # 5. Draw rectangles around the detected motion
        for contour in contours:
            # Filter out small contours (noise)
            if cv2.contourArea(contour) < 8000:
                countour_count -= 1
                continue

        if countour_count == 0:
            return False
        else:
            return True

def main():
    width = 4608
    height = 2592

    OUT_WIDTH = 640
    OUT_HEIGHT = 480

    camera = PiCameraCapture(width,height)

    #picam2.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": 1.0/distance})

    # Define the GStreamer output pipeline
    # 'appsrc ! videoconvert ! x264enc tune=zerolatency ! mpegtsmux ! udpsink host=127.0.0.1 port=5000'
    # The pipeline takes frames from appsrc, converts them, encodes them to h264,
    # multiplexes them, and sends them to a UDP sink.
    gst_out_pipeline = (
        f"appsrc ! video/x-raw,width={OUT_WIDTH},height={OUT_HEIGHT} ! videoconvert ! x264enc ! h264parse ! "
        " mpegtsmux ! tcpserversink port=8080 host=0.0.0.0"
    )

    # Open the VideoWriter with the GStreamer pipeline
    # The '0' is for the default fourcc code, which is ignored when using a GStreamer pipeline string
    out = cv2.VideoWriter(gst_out_pipeline, cv2.CAP_GSTREAMER, 0, (5), (OUT_WIDTH, OUT_HEIGHT), True)

    if not out.isOpened():
        print("Cannot open GStreamer writer. Check pipeline and build configuration.")
        exit(0)

    detector = MotionDetector()

    # Initialize the first frame as the static background
    background = None
    while (True):
        # Slow the framerate so we can make the processing timeline
        time.sleep(0.2)
        frame = camera.get_frame()
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_resize = cv2.resize(rgb_image, (OUT_WIDTH,OUT_HEIGHT))
        # Always write to pipeline
        out.write(rgb_resize)

        if detector.detect_motion(rgb_image):
            # Get current date and time
            now = datetime.now()

            # Format as string: Month/Day/Year, Hour:Minute:Second
            formatted_datetime = now.strftime("Image_%Y%m%d_%H:%M:%S.png")
            cv2.imwrite(DIRECTORY + "/" + formatted_datetime, rgb_image)

if __name__ == "__main__":
    main()
