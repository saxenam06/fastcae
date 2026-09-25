"""The design space: the one volume of air round a part where metal may be added.

Taken as defined - an input kept in the project's folder, like the CAD. Where the engineer has
brought none, rules that hold for any part define it from the CAD, the solver deck and the drawing:
a layer over the walls, outside and in, less what sits in the bores and passes through them, what
mates against held faces, and each fastener with its tool. See :func:`derive.derive` for the rules
and :mod:`store` for how it is kept.
"""

from .derive import derive
from .model import Evidence, Label, Params, Space

__all__ = ["Evidence", "Label", "Params", "Space", "derive"]
