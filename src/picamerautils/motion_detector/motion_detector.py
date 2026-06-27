import time
import cv2
import os
from datetime import datetime
from threading import Event, Thread

DIRECTORY = "/data/motiondetector/"

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
            if cv2.contourArea(contour) < 2000:
                countour_count -= 1
                continue

        if countour_count == 0:
            return False
        else:
            return True

class MotionDetectorProcess(Thread):
    DUMP_FRAMES_COUNT = 20

    def __init__(self, inputQueue, directory, imageSizeTuple, frameRate):
        super().__init__()
        self.name = "Motion Detector Process"

        self.input_queue = inputQueue
        self.save_directory = directory

        self.frame_rate = frameRate
        self.image_size_tuple = imageSizeTuple
        self._stop_event = Event()  # Stop hook trigger

        self.motion_detector = MotionDetector()

        self.recording_video = False

    def get_name(self):
        if os.path.exists(self.save_directory):
            filename = os.path.join(self.save_directory,datetime.now().strftime("%Y%m%d_%H%M%S.mp4"))
            return filename

    def start(self):
        """Start hook: Called before the thread's run() method."""
        print("[Start Hook] Thread is being initialized/started...")
        super().start()

    def stop(self):
        """Stop hook: Sets the event flag to signal a graceful shutdown."""
        print("[Stop Hook] Stop signal received. Waiting for thread to finish...")
        self._stop_event.set()

    def run(self):
        """
        This class just grabs frames and dumps to a queue
        It also checks a queue periodically for configuration updates,
        and updates the camera config upon new items
        """
        command_queue_check_counter = 0
        while not self._stop_event.is_set():
            if self.input_queue.qsize() > self.DUMP_FRAMES_COUNT:
                print (f"WARN: Dumping {self.DUMP_FRAMES_COUNT} frames")
                for data_index in range(0, self.DUMP_FRAMES_COUNT-1):
                    self.input_queue.get()
            item = self.input_queue.get()
            video_resized = cv2.resize(item, (640, 480))

            if self.motion_detector.detect_motion(video_resized):
                if self.recording_video:
                    # Extend video record for 2 seconds
                    self.end_record_time += 2
                else:
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    self.cap = cv2.VideoWriter(self.get_name(), fourcc, self.frame_rate, self.image_size_tuple)
                    self.recording_video = True
                    self.end_record_time = time.time() + 2
            else:
                if self.recording_video:
                    if time.time() > self.end_record_time:
                        self.cap.release()
                        self.cap = None
                        self.recording_video = False

            if self.recording_video:
                self.cap.write(item)

            # increment interation counter
            command_queue_check_counter = command_queue_check_counter + 1

        if self.recording_video:
            self.cap.release()
            self.recording_video = False
