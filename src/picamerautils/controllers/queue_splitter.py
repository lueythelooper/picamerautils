from picamerautils.controllers.hq_camera import PiCameraCapture
from threading import Thread
from threading import Event

class QueueSplitter(Thread):
    def __init__(self, inputQueue):
        super().__init__()
        self.name = "Queue Splitter"

        self.input_queue = inputQueue
        self.output_queues = []

        self._stop_event = Event()  # Stop hook trigger

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
            item = self.input_queue.get()
            for queue in self.output_queues:
                queue.put(item)

    def add_output_queue(self, outputQueue):
        self.output_queues.append(outputQueue)

