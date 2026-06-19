from threading import Thread
from threading import Event
from datetime import datetime
import cv2
import os
import logging

COMMAND_RECORD = 0
COMMAND_STOP = 1

class VideoRecorder(Thread):
    def __init__(self, inputQueue, commandQueue, directory, imageSizeTuple, frameRate):
        super().__init__()
        self.name = "Queue Splitter"

        self.input_queue = inputQueue
        self.save_directory = directory
        self.command_queue = commandQueue

        self.frame_rate = frameRate
        self.image_size_tuple = imageSizeTuple

        self._stop_event = Event()  # Stop hook trigger

        self.recording_video = False

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
        command_queue_check_counter = 0
        while not self._stop_event.is_set():
            if self.input_queue.qsize() > 20:
                for data_index in range(0, 19):
                    self.input_queue.get()
            item = self.input_queue.get()

            if command_queue_check_counter > 15:
                if self.command_queue.qsize() > 0:
                    self.size_of_queue = self.command_queue.qsize()
                    new_command = self.command_queue.get()
                    if new_command == COMMAND_RECORD:
                        if self.recording_video:
                            logging.info("Cannot start new record while recording")
                        else:
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            self.cap = cv2.VideoWriter(self.get_name(), fourcc, self.frame_rate, self.image_size_tuple)
                            self.recording_video = True
                    if new_command == COMMAND_STOP:
                        if self.recording_video:
                            self.cap.release()
                            self.cap = None
                            self.recording_video = False
                        else:
                            logging.warn("Cannot stop recording when no recording started")

                    while self.command_queue.qsize() != 0:
                        self.command_queue.get()
                
                command_queue_check_counter = 0

            if self.recording_video:
                self.cap.write(item)

            # increment interation counter
            command_queue_check_counter = command_queue_check_counter + 1

        print ("Releasing cap!")
        self.cap.release()
