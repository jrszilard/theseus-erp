from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from theseus.keel.llm_gateway.gateway import LLMGateway

_SYSTEM_PROMPT = (
    "You convert a maker's free-text sale note into JSON. Return ONLY a JSON array; "
    "each element is {\"sku\": <one of the listed skus>, \"quantity\": <number>, "
    "\"unit_price\": <number, optional>}. No prose, no markdown."
)
_FENCE = re.compile(r"^\s*```(?:json)?\s*$", re.MULTILINE)


@dataclass
class ParsedSaleLine:
    variation_id: str
    label: str
    quantity: float
    unit_price: float | None


def llm_available() -> bool:
    """True when an LLM provider/model/key is configured (NL capture is optional)."""
    return LLMGateway().is_configured()


def _extract_json(content: str) -> str:
    return _FENCE.sub("", content).strip()


async def parse_sale_text(
    text: str, variations: list[dict[str, Any]], gateway: LLMGateway,
) -> list[ParsedSaleLine]:
    """ONE structured LLM call -> candidate sale lines. Never writes. Returns [] on any
    failure (unconfigured, gateway error, unparseable, unknown skus)."""
    if not text.strip() or not variations:
        return []
    catalog = "\n".join(f'- sku={v["label"]} (price {v["price"]})' for v in variations)
    result = await gateway.complete(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Available skus:\n{catalog}\n\nNote: {text}"},
        ],
        temperature=0,
    )
    if result.get("error") or not result.get("content"):
        return []
    try:
        items = json.loads(_extract_json(result["content"]))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(items, list):
        return []

    by_sku = {str(v["label"]).lower(): v for v in variations}
    lines: list[ParsedSaleLine] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        v = by_sku.get(str(it.get("sku", "")).lower())
        if v is None:
            continue
        try:
            qty = float(it["quantity"])
        except (KeyError, ValueError, TypeError):
            continue
        if qty <= 0:
            continue
        up = it.get("unit_price")
        unit_price: float | None
        if isinstance(up, bool):
            unit_price = None
        elif isinstance(up, (int, float)):
            unit_price = float(up)
        elif isinstance(up, str):
            try:
                unit_price = float(up)
            except ValueError:
                unit_price = None
        else:
            unit_price = None
        lines.append(ParsedSaleLine(
            variation_id=str(v["id"]), label=str(v["label"]), quantity=qty,
            unit_price=unit_price,
        ))
    return lines
