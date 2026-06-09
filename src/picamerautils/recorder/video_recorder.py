from threading import Thread
from threading import Event
from datetime import datetime
import cv2
import os

class VideoRecorder(Thread):
    def __init__(self, inputQueue, directory, imageSizeTuple, frameRate):
        super().__init__()
        self.name = "Queue Splitter"

        self.input_queue = inputQueue
        self.save_directory = directory

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.cap = cv2.VideoWriter(self.get_name(), fourcc, frameRate, imageSizeTuple)

        self._stop_event = Event()  # Stop hook trigger

    def get_name(self):
        if os.path.exists(self.save_directory):
            filename = os.path.join(self.save_directory,datetime.now().strftime("%y%m%d_%H%M%S.mp4"))
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
        while not self._stop_event.is_set():
            if self.input_queue.qsize() > 20:
                self.input_queue.clear()
            item = self.input_queue.get()
            self.cap.write(item)

        print ("Releasing cap!")
        self.cap.release()
