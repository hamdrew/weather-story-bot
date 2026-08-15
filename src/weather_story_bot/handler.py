"""Lambda entry points for the Weather Story service.

Business behavior is added in subsequent implementation tasks.  Keeping the
entry point importable establishes the package shape used by SAM packaging.
"""

from collections.abc import Mapping
from typing import Any


def publisher_handler(event: Mapping[str, Any], context: object) -> None:
    """Reserved publisher Lambda entry point."""
    del event, context
