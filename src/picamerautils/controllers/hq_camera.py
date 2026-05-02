from picamera2 import Picamera2, Preview
from libcamera import Transform
from libcamera import controls
import threading
import time
import cv2


EXPOSURE_LIST = [1000,5000,10000,15000,20000,30000,40000,50000,70000,100000,500000,1000000,2000000,5000000,10000000]
GAIN_LIST = [1,2,3,4,5,7,10,15,20]


class PiCameraCapture:
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
          controls={"FrameDurationLimits": (EXPOSURE_LIST[0], EXPOSURE_LIST[-1])})
        self.picam2.configure(camera_config)
        self.picam2.controls.ExposureTime = EXPOSURE_LIST[0]
        self.picam2.controls.AnalogueGain = GAIN_LIST[0]

        self.picam2.start()

    def __del__(self):
        self.picam2.stop()

    def get_frame(self):
        return self.picam2.capture_array()

class VideoCamera:
    def __init__(self,width,height,framerate=15):
        # Open pipeline via OpenCV
        self.cap = PiCameraCapture(width,height)
        self.raw_frame = None
        self.rgb_image = None
        self.frame = None
        self.lock = threading.Lock()
        self.jpeg = None
        self.running = True
        self.grabbed_frames = 0

        self.sleep_time = 1.0 / (framerate+2)

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
            time.sleep(self.sleep_time/2)

    def get_frame(self):
        with self.lock:
            return self.frame

