from picamera2 import Picamera2, Preview
from libcamera import Transform
from libcamera import controls
from threading import Thread
from threading import Event
import queue
import time
import cv2
from threading import Lock

EXPOSURE_LIST = [1000,5000,10000,15000,20000,30000,40000,50000,70000,100000,500000,1000000,2000000,5000000,10000000]
GAIN_LIST = [1,2,3,4,5,7,10,15,20]

COMMAND_GAIN = 0
COMMAND_EXPOSURE = 1

class PiCameraCapture(Thread):
    CONTROLS_UPDATE_RATE_FRAMES = 10
    """
    Initialize the camera capture class

    Provide width and height
    """
    def __init__(self, width, height, commandQueue, frameRate):
        # Threading parameters
        super().__init__()
        self.name = "PiCameraCapture_HQ_Camera"

        # Output queue is a queue that frames are pushed to
        self.output_queue = commandQueue
        self.command_queue = queue.Queue()

        self._width = width
        self._height = height

        # Initialize the picam object
        self.picam2 = Picamera2()
        camera_config = self.picam2.create_still_configuration({"format": "BGR888", "size": (self._width,self._height)}, transform=Transform(hflip=0,vflip=0),
          controls={"FrameDurationLimits": (EXPOSURE_LIST[0], EXPOSURE_LIST[-1])})
        self.picam2.configure(camera_config)
        self.picam2.controls.ExposureTime = EXPOSURE_LIST[3]
        self.picam2.controls.AnalogueGain = GAIN_LIST[2]
        self.picam2.controls.FrameRate = frameRate

        self.picam2.start()

        self._stop_event = Event()  # Stop hook trigger

    def get_frame(self):
        frame = self.picam2.capture_array()
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return rgb_image

    def start(self):
        """Start hook: Called before the thread's run() method."""
        print("[Start Hook] Thread is being initialized/started...")
        super().start()

    def stop(self):
        """Stop hook: Sets the event flag to signal a graceful shutdown."""
        print("[Stop Hook] Stop signal received. Waiting for thread to finish...")
        self._stop_event.set()

    def change_gain(self, gain_index):
        self.command_queue.put((COMMAND_GAIN,gain_index))

    def change_exposure(self, exposure_index):
        self.command_queue.put((COMMAND_EXPOSURE,exposure_index))

    def run(self):
        """
        This class just grabs frames and dumps to a queue
        It also checks a queue periodically for configuration updates,
        and updates the camera config upon new items
        """
        index = 0
        while not self._stop_event.is_set():
            self.output_queue.put(self.get_frame())
            index += 1

            # If the index reaches an interval of the confnigured value,
            # check the controls and do the stinky
            if index % self.CONTROLS_UPDATE_RATE_FRAMES == 0:
                while not self.command_queue.empty():
                    command = self.command_queue.get()
                    if command[0] == COMMAND_GAIN:
                        print (f"Setting gain to {command[1]}")
                        self.picam2.controls.AnalogueGain = GAIN_LIST[command[1]]
                    if command[0] == COMMAND_EXPOSURE:
                        print (f"Setting exposure to {command[1]}")
                        self.picam2.controls.ExposureTime = EXPOSURE_LIST[command[1]]

class FramerateLoadBalancer(Thread):
    def __init__(self, inputQueue, framerate):
        super().__init__()
        self.name = "Framerate Load Balancer"

        self._stop_event = Event()  # Stop hook trigger

        self.input_queue = inputQueue

        self.lock = Lock()

        self.sleep_time = 1 / framerate

    def get_frame(self):
        with self.lock:
            return self.latest_frame

    def start(self):
        """Start hook: Called before the thread's run() method."""
        print("[Start Hook] Thread is being initialized/started...")
        super().start()

    def stop(self):
        """Stop hook: Sets the event flag to signal a graceful shutdown."""
        print("[Stop Hook] Stop signal received. Waiting for thread to finish...")
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            time.sleep(self.sleep_time)
            with self.lock:
                while not self.input_queue.empty():
                    self.latest_frame = self.input_queue.get(block=True)

# Define a unit test that can run this class()
running = True
# 2. Define the signal handler function
def handle_stop_signal(signum, frame):
    global running
    running = False  # Change flag to break the loop safely

if __name__ == "__main__":
    import cv2
    import signal

    output_queue = queue.Queue()

    width = 1920
    heigiht = 1080
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter('output.mp4', fourcc, 15, (width, heigiht));


    cameracapture = PiCameraCapture(width, heigiht, output_queue)
    cameracapture.start()

    # 3. Register the signals (SIGINT handles Ctrl+C, SIGTERM handles kill commands)
    signal.signal(signal.SIGINT, handle_stop_signal)
    signal.signal(signal.SIGTERM, handle_stop_signal)

    while running:
        out.write(output_queue.get())

    print("Loop exited cleanly. Performing final cleanup tasks.")
    out.release()
    cameracapture.stop()
