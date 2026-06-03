"""
timing_distorter.py — Clock skew and timestamp distortion.

Injects:
- Clock skew (systematic offset applied to timestamps)
- Timestamp inversion (swapped ordering)
- Duplicate timestamps
- Forced delays on time.time() calls
"""

import random
import time
from typing import Callable, Optional


class TimingDistorter:
    """Wraps time.time() to inject timing distortions."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._skew: float = 0.0
        self._jitter: float = 0.0
        self._invert_flag: bool = False
        self._fixed_time: Optional[float] = None
        self._last_time: Optional[float] = None
        self._forced_delay: float = 0.0
        self._original_time = time.time

    def enable(self):
        """Replace time.time with distorted version."""
        time.time = self._distorted_time

    def disable(self):
        """Restore original time.time."""
        time.time = self._original_time

    def set_skew(self, seconds: float):
        """Apply a fixed clock skew (positive = forward, negative = backward)."""
        self._skew = seconds

    def set_jitter(self, seconds: float):
        """Add random jitter to each time.time() call."""
        self._jitter = seconds

    def set_fixed_time(self, t: float):
        """time.time() always returns this value."""
        self._fixed_time = t

    def enable_inversion(self):
        """Enable timestamp inversion (monotonicity break)."""
        self._invert_flag = True

    def disable_inversion(self):
        self._invert_flag = False

    def set_forced_delay(self, seconds: float):
        """Add forced sleep before each time.time() call."""
        self._forced_delay = seconds

    def reset(self):
        self._skew = 0.0
        self._jitter = 0.0
        self._invert_flag = False
        self._fixed_time = None
        self._last_time = None
        self._forced_delay = 0.0
        self.disable()

    def _distorted_time(self) -> float:
        if self._forced_delay > 0:
            time.sleep(self._forced_delay)
        if self._fixed_time is not None:
            return self._fixed_time
        t = self._original_time()
        t += self._skew
        if self._jitter > 0:
            t += self._rng.uniform(-self._jitter, self._jitter)
        if self._invert_flag and self._last_time is not None:
            if self._rng.random() < 0.3:
                t = self._last_time - abs(t - self._last_time) * 0.5
        self._last_time = t
        return t


class TimingDistorterContext:
    """Context manager for safe TimingDistorter usage."""

    def __init__(self, distorter: TimingDistorter):
        self._distorter = distorter

    def __enter__(self):
        self._distorter.enable()
        return self._distorter

    def __exit__(self, *args):
        self._distorter.disable()
