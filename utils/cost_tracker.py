"""
utils/cost_tracker.py — Session cost + token tracking
"""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ModelPricing:
    input_per_mtok:       float
    output_per_mtok:      float
    cache_write_per_mtok: float
    cache_read_per_mtok:  float


MODEL_PRICING: Dict[str, ModelPricing] = {
    "claude-sonnet-4-5":          ModelPricing(3.0,  15.0,  3.75, 0.30),
    "claude-sonnet-4-6":          ModelPricing(3.0,  15.0,  3.75, 0.30),
    "claude-sonnet-4":            ModelPricing(3.0,  15.0,  3.75, 0.30),
    "claude-haiku-4-5":           ModelPricing(1.0,   5.0,  1.25, 0.10),
    "claude-haiku-3-5":           ModelPricing(0.8,   4.0,  1.00, 0.08),
    "claude-opus-4":              ModelPricing(15.0, 75.0, 18.75, 1.50),
    "claude-opus-4-5":            ModelPricing(5.0,  25.0,  6.25, 0.50),
    "claude-opus-4-6":            ModelPricing(5.0,  25.0,  6.25, 0.50),
    "claude-3-5-sonnet-20241022": ModelPricing(3.0,  15.0,  3.75, 0.30),
    "claude-3-5-haiku-20241022":  ModelPricing(0.8,   4.0,  1.00, 0.08),
}
DEFAULT_PRICING = ModelPricing(3.0, 15.0, 3.75, 0.30)


def _get_pricing(model: str) -> ModelPricing:
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    for key in MODEL_PRICING:
        if model.startswith(key) or key in model:
            return MODEL_PRICING[key]
    return DEFAULT_PRICING


def calculate_cost(usage, model: str) -> float:
    p = _get_pricing(model)
    return (
        (getattr(usage, "input_tokens",                0) or 0) / 1_000_000 * p.input_per_mtok +
        (getattr(usage, "output_tokens",               0) or 0) / 1_000_000 * p.output_per_mtok +
        (getattr(usage, "cache_read_input_tokens",     0) or 0) / 1_000_000 * p.cache_read_per_mtok +
        (getattr(usage, "cache_creation_input_tokens", 0) or 0) / 1_000_000 * p.cache_write_per_mtok
    )


@dataclass
class CostTracker:
    total_input:       int   = 0
    total_output:      int   = 0
    total_cache_read:  int   = 0
    total_cache_write: int   = 0
    total_cost_usd:    float = 0.0
    api_call_count:    int   = 0
    _model:            str   = field(default="claude-sonnet-4-6", repr=False)

    def add(self, usage, model: str = None):
        if model:
            self._model = model
        self.total_input       += getattr(usage, "input_tokens",                0) or 0
        self.total_output      += getattr(usage, "output_tokens",               0) or 0
        self.total_cache_read  += getattr(usage, "cache_read_input_tokens",     0) or 0
        self.total_cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.total_cost_usd    += calculate_cost(usage, self._model)
        self.api_call_count    += 1

    def format_cost(self) -> str:
        c = self.total_cost_usd
        return f"${c:.2f}" if c >= 0.50 else f"${c:.4f}"

    def format_summary(self) -> str:
        return (
            f"💰 Session cost: {self.format_cost()}\n"
            f"📊 Tokens: {self.total_input:,} in · {self.total_output:,} out · "
            f"{self.total_cache_read:,} cache read · {self.total_cache_write:,} cache write\n"
            f"🔁 API calls: {self.api_call_count}"
        )

    def format_inline(self) -> str:
        return f"[{self.format_cost()} · {self.total_input + self.total_output:,} tok]"

    def reset(self):
        self.total_input = self.total_output = 0
        self.total_cache_read = self.total_cache_write = 0
        self.total_cost_usd = 0.0
        self.api_call_count = 0
