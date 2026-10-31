"""Agent interface (HANDOFF §5): baselines and RL policies are interchangeable behind it."""

from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

State = npt.NDArray[np.float64]
Action = npt.NDArray[np.float64]


@runtime_checkable
class Agent(Protocol):
    def act(self, state: State) -> Action:
        """Map an observation to an action. Must be deterministic at inference time."""
        ...
