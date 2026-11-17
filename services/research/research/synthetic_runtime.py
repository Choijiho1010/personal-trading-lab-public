import os
import time


class InvalidSyntheticDelay(ValueError):
    pass


def wait_for_synthetic_delay() -> None:
    raw_value = os.environ.get("RESEARCH_SYNTHETIC_DELAY_MS", "0")
    try:
        delay_ms = int(raw_value)
    except ValueError as error:
        raise InvalidSyntheticDelay() from error
    if delay_ms < 0:
        raise InvalidSyntheticDelay()
    time.sleep(delay_ms / 1000)
