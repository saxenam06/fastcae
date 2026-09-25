"""The one GPU, shared by what builds designs and what solves them.

Memory freed on the card does not go back to it by itself: CuPy keeps what its arrays freed in a
pool for reuse, and Warp's allocator keeps its own. cuDSS allocates outside both, so a card that
holds nothing in use can still be full to it - a solve after a few builds ran out of memory that
nothing held. :func:`release` hands all of it back; whatever uses the card calls it when done.
"""

from __future__ import annotations

import gc
import sys


def release() -> None:
    """Every block freed on the card, handed back to it: CuPy's pools emptied, Warp's pool told
    to keep nothing and synchronised so it lets go, and dead arrays collected first."""
    gc.collect()
    if "cupy" in sys.modules:
        import cupy as cp

        cp.get_default_memory_pool().free_all_blocks()
        cp.get_default_pinned_memory_pool().free_all_blocks()
    if "warp" in sys.modules:
        import warp as wp

        if wp.is_cuda_available():
            for device in wp.get_cuda_devices():
                if wp.is_mempool_enabled(device):
                    # Past this many bytes kept, the pool gives memory back at a synchronize.
                    wp.set_mempool_release_threshold(device, 0)
                wp.synchronize_device(device)
