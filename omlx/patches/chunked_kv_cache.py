"""Patch ChunkedKVCache for batch=1 BatchGenerator compatibility.

mlx-lm's ChunkedKVCache (used by Llama-4-style sliding-window architectures)
ships without `merge`, `extend`, or `filter` methods, so any path that wraps
it via mlx_lm.generate.BatchGenerator raises:

    <class 'mlx_lm.models.cache.ChunkedKVCache'> does not yet support
    batching with history

oMLX's scheduler always uses BatchGenerator, even at max-concurrent-requests=1.
With concurrency=1 the operations only ever run on a single cache, so
single-element implementations are sufficient and don't change semantics.

Implementations:
- merge(caches): single-element batches return caches[0]; otherwise raise so
  upstream callers fall back instead of silently corrupting state.
- filter(batch_indices): single-index passthrough; raise on multi-batch.
- extend(other): in-place append along the seq dim, mirroring KVCache.extend.

Bumping concurrency back up requires a real BatchChunkedKVCache (separate work).
"""

from __future__ import annotations

import logging

import mlx.core as mx
from mlx_lm.models.cache import ChunkedKVCache

logger = logging.getLogger(__name__)

_PATCH_APPLIED = False


def _merge(cls, caches):
    if len(caches) == 1:
        return caches[0]
    raise NotImplementedError(
        f"ChunkedKVCache.merge with batch_size={len(caches)} requires a "
        "BatchChunkedKVCache implementation; only single-batch is supported."
    )


def _filter(self, batch_indices):
    if len(batch_indices) == 1 and batch_indices[0] == 0:
        return
    raise NotImplementedError(
        f"ChunkedKVCache.filter with indices={batch_indices} requires a "
        "BatchChunkedKVCache implementation; only single-batch is supported."
    )


def _extract(self, idx):
    """Return self for batch_size=1 extract at idx 0; raise otherwise.

    BatchGenerator.extract_cache(idx) is called per request to pull that
    request's cache out of the batched cache. With concurrency=1, idx is
    always 0 and the single-batch cache IS that request's cache.
    """
    if idx == 0:
        return self
    raise NotImplementedError(
        f"ChunkedKVCache.extract(idx={idx}) requires a BatchChunkedKVCache; "
        "only single-batch is supported."
    )


def _extend(self, other):
    """Append other's keys/values along the sequence dimension.

    Mirrors KVCache.extend: concatenates the populated regions of both caches
    so that subsequent attention sees the combined history.
    """
    if other.keys is None or other.offset == 0:
        return
    if self.keys is None:
        self.keys = other.keys[..., : other.offset, :]
        self.values = other.values[..., : other.offset, :]
        self.offset = other.offset
        return
    self_used = self.offset - self.start_position
    other_used = other.offset - other.start_position
    self_keys = self.keys[..., :self_used, :]
    self_values = self.values[..., :self_used, :]
    other_keys = other.keys[..., :other_used, :]
    other_values = other.values[..., :other_used, :]
    self.keys = mx.concatenate([self_keys, other_keys], axis=2)
    self.values = mx.concatenate([self_values, other_values], axis=2)
    self.offset = self.start_position + self.keys.shape[2]
    self.maybe_trim_front()


def apply_patch():
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return
    if not hasattr(ChunkedKVCache, "merge"):
        ChunkedKVCache.merge = classmethod(_merge)
    if not hasattr(ChunkedKVCache, "filter"):
        ChunkedKVCache.filter = _filter
    if not hasattr(ChunkedKVCache, "extend"):
        ChunkedKVCache.extend = _extend
    if not hasattr(ChunkedKVCache, "extract"):
        ChunkedKVCache.extract = _extract
    _PATCH_APPLIED = True
    logger.info(
        "ChunkedKVCache patch applied (single-batch merge/filter/extend) — "
        "fixes Llama-4-Scout 'batching with history' error at concurrency=1"
    )
