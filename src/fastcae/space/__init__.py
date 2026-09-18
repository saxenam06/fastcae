"""The design space: for every cell of air near a part, whether metal may be added there.

Derived from the part's CAD and its solver deck alone - a drawing adds evidence when there is one.
Nothing here knows what the part is for. It reads geometric kinds (planes, bores, holes, walls) and
what the deck acts on, and answers three things per cell: **allowed**, **forbidden and why**, or
**unknown** - evidence too weak to decide, so an engineer is asked.

See :func:`derive.derive` for the steps.
"""

from .derive import derive
from .model import Evidence, Label, Params, Reason, Space

__all__ = ["Evidence", "Label", "Params", "Reason", "Space", "derive"]
