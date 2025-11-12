# synapse/agent.py
from typing import Callable, Any, Dict
import time 
import uuid
import traceback

class Agent:
    """
    Minimal Agent abstraction.
    - name: identifier
    - func: callable(context) -> output (dict or str)
    - model: label for which model adapter to use (openai, local, mock)
    - retries: retry count on failure
    """

    def __init__(self, name: str, func: Callable[[Dict], Any], model: str = "mock", retries: int = 1, timeout_s: float = 30.0):
        self.name = name
        self.func = func
        self.model = model
        self.retries = retries
        self.timeout_s = timeout_s
        self.id = str(uuid.uuid4())

    def run(self, context: dict, tracer):
        """
        Run the agent synchronously.
        Records success or error into tracer.
        Returns the output (could be dict or text).
        """
        attempt = 0
        last_exc = None
        while attempt <= self.retries:
            attempt += 1
            start = time.time()
            try:
                out = self.func(context) # adapter // builtin
                duration = time.time() - start
                tracer.record_node(run_id=tracer.current_run_id,
                                    agent_id=self.id,
                                    name=self.name,
                                    input_ctx=context,
                                    output=out,
                                    duration=duration,
                                    attempt=attempt,
                                    model=self.model)

                return out

            except Exception as e:
                duration = time.time() - start
                err = traceback.format_exc()
                tracer.record_error(run_id=tracer.current_run_id,
                                    agent_id=self.id,
                                    name=self.name,
                                    error=str(e),
                                    stack=err,
                                    duration=duration,
                                    attempt=attempt,
                                    model=self.model)

                last_exc = e

                #simple backoff
                time.sleep(min(1 * attempt, 3))

        raise last_exc