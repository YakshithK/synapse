from typing import Callable, Any
import uuid, time

class Agent:
    def __init__(self, name: str, func: Callable, model: str="gpt-4", retries: int=1):
        self.name = name
        self.func = func
        self.model = model
        self.retries = retries
        self.id = str(uuid.uuid4())

    def run(self, input_context: dict, trace):
        attempt = 0
        while attempt <= self.retires:
            attempt += 1
            start = time.time()
            try:
                out = self.func(input_context)
                duration = time.time() - start
                trace.record(self.id, self.name, input_context, out, duration, attempt)
                return out
            except Exception as e:
                trace.record_error(self.id, self.name, str(e), attempt)
                if attempt > self.retries:
                    raise