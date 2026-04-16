from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.middleware import emit_entity_event
from theseus.keel.event_store.store import PostgresEventStore


class InvoicingService:
    """Domain service for the Invoicing Plank."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresEventStore(session=session)

    async def create_invoice(
        self,
        *,
        invoice_number: str,
        customer_id: uuid.UUID,
        issue_date: date,
        due_date: date | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        invoice_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": invoice_id, "invoice_number": invoice_number,
            "customer_id": customer_id, "status": "draft",
            "issue_date": issue_date, "subtotal": 0, "tax_rate": 0,
            "tax_amount": 0, "total": 0,
        }
        if due_date is not None:
            params["due_date"] = due_date
        if notes is not None:
            params["notes"] = notes

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO invoicing_invoice ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="invoicing",
            entity="Invoice", entity_id=invoice_id,
            data={"invoice_number": invoice_number, "customer_id": str(customer_id)},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def add_line_item(
        self,
        *,
        invoice_id: uuid.UUID,
        description: str,
        quantity: float,
        unit_price: float,
        product_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        line_id = uuid.uuid4()
        line_total = round(quantity * unit_price, 2)
        params: dict[str, Any] = {
            "id": line_id, "invoice_id": invoice_id, "description": description,
            "quantity": quantity, "unit_price": unit_price, "line_total": line_total,
        }
        if product_id is not None:
            params["product_id"] = product_id

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO invoicing_invoice_line ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def compute_totals(self, invoice_id: uuid.UUID, tax_rate: float = 0) -> dict[str, Any]:
        """Recompute invoice totals from line items."""
        subtotal_query = text(
            "SELECT COALESCE(SUM(line_total), 0) as subtotal "
            "FROM invoicing_invoice_line WHERE invoice_id = :invoice_id"
        )
        result = await self._session.execute(subtotal_query, {"invoice_id": invoice_id})
        subtotal = float(result.mappings().one()["subtotal"])
        tax_amount = round(subtotal * tax_rate, 2)
        total = round(subtotal + tax_amount, 2)

        update_query = text(
            "UPDATE invoicing_invoice SET subtotal = :subtotal, tax_rate = :tax_rate, "
            "tax_amount = :tax_amount, total = :total, updated_at = now() "
            "WHERE id = :id RETURNING *"
        )
        result = await self._session.execute(update_query, {
            "id": invoice_id, "subtotal": subtotal, "tax_rate": tax_rate,
            "tax_amount": tax_amount, "total": total,
        })
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def record_payment(
        self,
        *,
        invoice_id: uuid.UUID,
        amount: float,
        payment_date: date,
        payment_method: str,
        reference: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        payment_id = uuid.uuid4()
        params: dict[str, Any] = {
            "id": payment_id, "invoice_id": invoice_id, "amount": amount,
            "payment_date": payment_date, "payment_method": payment_method,
        }
        if reference is not None:
            params["reference"] = reference
        if notes is not None:
            params["notes"] = notes

        col_names = ", ".join(params.keys())
        col_params = ", ".join(f":{k}" for k in params.keys())
        query = text(f"INSERT INTO invoicing_payment ({col_names}) VALUES ({col_params}) RETURNING *")
        result = await self._session.execute(query, params)

        await emit_entity_event(
            store=self._store, action="created", plank="invoicing",
            entity="Payment", entity_id=payment_id,
            data={"invoice_id": str(invoice_id), "amount": amount, "payment_method": payment_method},
        )
        await self._session.flush()
        return _row_to_dict(result.mappings().one())

    async def get_invoice_detail(self, invoice_id: uuid.UUID) -> dict[str, Any]:
        invoice_query = text("SELECT * FROM invoicing_invoice WHERE id = :id")
        inv_result = await self._session.execute(invoice_query, {"id": invoice_id})
        inv_row = inv_result.mappings().one_or_none()
        if inv_row is None:
            raise ValueError(f"Invoice {invoice_id} not found")

        lines_query = text("SELECT * FROM invoicing_invoice_line WHERE invoice_id = :id ORDER BY created_at")
        lines_result = await self._session.execute(lines_query, {"id": invoice_id})

        payments_query = text("SELECT * FROM invoicing_payment WHERE invoice_id = :id ORDER BY payment_date")
        payments_result = await self._session.execute(payments_query, {"id": invoice_id})

        invoice = _row_to_dict(inv_row)
        invoice["lines"] = [_row_to_dict(r) for r in lines_result.mappings().all()]
        invoice["payments"] = [_row_to_dict(r) for r in payments_result.mappings().all()]
        return invoice


def _row_to_dict(row: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, date):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
