from __future__ import annotations

import inspect
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.utils.elevenlabs_dynamic_context import format_dynamic_context


class Company(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    model_config = ConfigDict(extra="allow")


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def get_company_by_number(to_number: str) -> Any:
    raise NotImplementedError


async def get_products(company_id: str) -> Any:
    raise NotImplementedError


async def get_subsidy(company_id: str) -> Any:
    raise NotImplementedError


async def get_emi_policy(company_id: str) -> Any:
    raise NotImplementedError


async def get_active_offers(company_id: str) -> Any:
    raise NotImplementedError


async def build_dynamic_context(*, to_number: str) -> str:
    company_raw = await _maybe_await(get_company_by_number(to_number))
    if not company_raw:
        return format_dynamic_context(
            company_name="Unknown Company",
            products=[],
            subsidy=None,
            emi_policy=None,
            offers=[],
        )

    company = Company.model_validate(company_raw)
    company_id = (company.id or "").strip()
    if not company_id:
        return format_dynamic_context(
            company_name=company.name or "Unknown Company",
            products=[],
            subsidy=None,
            emi_policy=None,
            offers=[],
        )

    products = await _maybe_await(get_products(company_id))
    subsidy = await _maybe_await(get_subsidy(company_id))
    emi_policy = await _maybe_await(get_emi_policy(company_id))
    offers = await _maybe_await(get_active_offers(company_id))

    return format_dynamic_context(
        company_name=company.name or "Unknown Company",
        products=list(products or []),
        subsidy=subsidy,
        emi_policy=emi_policy,
        offers=list(offers or []),
    )
