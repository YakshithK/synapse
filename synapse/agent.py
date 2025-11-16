# synapse/agent.py
import time
import traceback
import uuid
from typing import Any, Callable, Dict, Optional


class Agent:
    """
    Enhanced Agent abstraction with metadata support.
    """

    def __init__(
        self,
        name: str,
        func: Callable[[Dict], Any],
        model: str = "mock",
        retries: int = 1,
        timeout_s: float = 30.0,
        metadata: Optional[Dict] = None,
    ):
        self.name = name
        self.func = func
        self.model = model
        self.retries = retries
        self.timeout_s = timeout_s
        self.metadata = metadata or {}
        self.id = str(uuid.uuid4())

    def run(self, context: Dict[str, Any], tracer: Any) -> Any:
        """
        Run the agent synchronously with enhanced error handling.
        """
        attempt = 0
        last_exc = None

        while attempt <= self.retries:
            attempt += 1
            start = time.time()

            try:
                # Validate context
                if not isinstance(context, dict):
                    raise ValueError(
                        f"Context must be a dictionary, got {type(context)}"
                    )

                # Call agent function
                out = self.func(context)

                # Validate output
                if out is None:
                    raise ValueError(f"Agent {self.name} returned None")

                duration = time.time() - start

                # Record success
                tracer.record_node(
                    run_id=tracer.current_run_id,
                    agent_id=self.id,
                    name=self.name,
                    input_ctx=context,
                    output=out,
                    duration=duration,
                    attempt=attempt,
                    model=self.model,
                    metadata=self.metadata,
                )

                # Let mypy know out is a Dict[str, Any]
                # out = cast(Dict[str, Any], out)

                return out

            except Exception as e:
                duration = time.time() - start
                err = traceback.format_exc()

                # Enhanced error information
                error_info = self._format_error(e, err, context)

                tracer.record_error(
                    run_id=tracer.current_run_id,
                    agent_id=self.id,
                    name=self.name,
                    error=error_info["message"],
                    stack=error_info["stack"],
                    duration=duration,
                    attempt=attempt,
                    model=self.model,
                    metadata=self.metadata,
                )

                last_exc = e

                # Backoff
                if attempt <= self.retries:
                    time.sleep(min(1 * attempt, 3))

        # All retries exhausted
        raise AgentExecutionError(
            f"Agent {self.name} failed after {self.retries + 1} attempts",
            agent_name=self.name,
            last_error=last_exc or Exception("No error"),
            context=context,
        )

    def _format_error(
        self, error: Exception, stack: str, context: dict
    ) -> Dict[str, Any]:
        """Format error with agent context."""
        return {
            "message": str(error),
            "type": type(error).__name__,
            "stack": stack,
            "agent": self.name,
            "context_keys": list(context.keys()),
            "context_size": str(len(str(context))),
        }


class AgentExecutionError(Exception):
    """Custom exception for agent execution errors."""

    def __init__(
        self,
        message: str,
        agent_name: str,
        last_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.agent_name = agent_name
        self.last_error = last_error
        self.context = context
        super().__init__(self.message)
