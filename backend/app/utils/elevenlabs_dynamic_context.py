from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional


def _as_mapping(value: Any) -> Optional[Mapping[str, Any]]:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if isinstance(dumped, Mapping):
                return dumped
        except Exception:
            return None
    if hasattr(value, "__dict__"):
        try:
            data = dict(value.__dict__)
            return data
        except Exception:
            return None
    return None


def _json_line(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _format_section(title: str, lines: Iterable[str]) -> list[str]:
    clean_lines = [line.strip() for line in lines if line and str(line).strip()]
    if not clean_lines:
        return [f"{title}:", "-"]
    return [f"{title}:", *clean_lines]


def format_dynamic_context(
    *,
    company_name: str,
    products: Optional[list[Any]],
    subsidy: Any,
    emi_policy: Any,
    offers: Optional[list[Any]],
) -> str:
    output: list[str] = []

    output.append(f"Company name: {company_name.strip() or 'Unknown Company'}")

    product_lines: list[str] = []
    for product in products or []:
        pdata = _as_mapping(product)
        if pdata:
            name = str(pdata.get("name") or pdata.get("title") or "").strip()
            price = pdata.get("price") or pdata.get("mrp") or pdata.get("amount")
            details_bits = []
            if name:
                details_bits.append(name)
            if price is not None and str(price).strip():
                details_bits.append(f"Price: {price}")
            sku = pdata.get("sku") or pdata.get("code")
            if sku is not None and str(sku).strip():
                details_bits.append(f"SKU: {sku}")
            if details_bits:
                product_lines.append(f"- {' | '.join(details_bits)}")
            else:
                product_lines.append(f"- {_json_line(pdata)}")
        else:
            product_lines.append(f"- {_json_line(product)}")

    output.extend(_format_section("Product catalog", product_lines))

    subsidy_map = _as_mapping(subsidy)
    if subsidy_map:
        output.extend(_format_section("Subsidy information", [f"- {_json_line(subsidy_map)}"]))
    elif subsidy is not None:
        output.extend(_format_section("Subsidy information", [f"- {_json_line(subsidy)}"]))
    else:
        output.extend(_format_section("Subsidy information", []))

    emi_map = _as_mapping(emi_policy)
    if emi_map:
        output.extend(_format_section("EMI policy", [f"- {_json_line(emi_map)}"]))
    elif emi_policy is not None:
        output.extend(_format_section("EMI policy", [f"- {_json_line(emi_policy)}"]))
    else:
        output.extend(_format_section("EMI policy", []))

    offer_lines: list[str] = []
    for offer in offers or []:
        offer_map = _as_mapping(offer)
        if offer_map:
            title = str(offer_map.get("title") or offer_map.get("name") or "").strip()
            if title:
                offer_lines.append(f"- {title}")
            else:
                offer_lines.append(f"- {_json_line(offer_map)}")
        else:
            offer_lines.append(f"- {_json_line(offer)}")

    output.extend(_format_section("Active offers", offer_lines))

    return "\n".join(output).strip() + "\n"
