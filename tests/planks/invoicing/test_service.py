import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from theseus.keel.event_store.store import PostgresEventStore
from theseus.planks.contacts.service import ContactService
from theseus.planks.invoicing.service import InvoicingService


class TestInvoicingService:
    @pytest.mark.asyncio
    async def test_create_invoice(self, db_session: AsyncSession) -> None:
        # First create a contact to reference
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Invoice Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-001",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
            due_date=date(2026, 5, 15),
        )
        assert invoice["invoice_number"] == "INV-001"
        assert invoice["status"] == "draft"
        assert "id" in invoice

    @pytest.mark.asyncio
    async def test_add_line_items_and_compute_total(self, db_session: AsyncSession) -> None:
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Total Test Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-002",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
        )
        invoice_id = uuid.UUID(invoice["id"])

        await svc.add_line_item(
            invoice_id=invoice_id,
            description="Steel Brackets x100",
            quantity=100,
            unit_price=4.50,
        )
        await svc.add_line_item(
            invoice_id=invoice_id,
            description="Powder Coating",
            quantity=1,
            unit_price=200.00,
        )

        totaled = await svc.compute_totals(invoice_id, tax_rate=0.08)
        assert float(totaled["subtotal"]) == 650.0  # 100*4.50 + 200
        assert float(totaled["tax_amount"]) == 52.0  # 650 * 0.08
        assert float(totaled["total"]) == 702.0  # 650 + 52

    @pytest.mark.asyncio
    async def test_record_payment(self, db_session: AsyncSession) -> None:
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Payment Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-003",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
        )
        invoice_id = uuid.UUID(invoice["id"])

        payment = await svc.record_payment(
            invoice_id=invoice_id,
            amount=500.00,
            payment_date=date(2026, 4, 20),
            payment_method="bank_transfer",
            reference="TXN-12345",
        )
        assert float(payment["amount"]) == 500.0
        assert payment["payment_method"] == "bank_transfer"

    @pytest.mark.asyncio
    async def test_payment_emits_event(self, db_session: AsyncSession) -> None:
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Event Payment Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-004",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
        )

        await svc.record_payment(
            invoice_id=uuid.UUID(invoice["id"]),
            amount=100.00,
            payment_date=date(2026, 4, 20),
            payment_method="cash",
        )

        store = PostgresEventStore(session=db_session)
        events = await store.get_events_by_type("invoicing.Payment.created")
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_get_invoice_with_lines_and_payments(self, db_session: AsyncSession) -> None:
        contacts = ContactService(session=db_session)
        customer = await contacts.create_contact(name="Full Invoice Customer", contact_type="customer")

        svc = InvoicingService(session=db_session)
        invoice = await svc.create_invoice(
            invoice_number="INV-005",
            customer_id=uuid.UUID(customer["id"]),
            issue_date=date(2026, 4, 15),
        )
        invoice_id = uuid.UUID(invoice["id"])

        await svc.add_line_item(invoice_id=invoice_id, description="Item A", quantity=2, unit_price=50.00)
        await svc.add_line_item(invoice_id=invoice_id, description="Item B", quantity=1, unit_price=75.00)
        await svc.record_payment(invoice_id=invoice_id, amount=100.00,
                                  payment_date=date(2026, 4, 20), payment_method="check")

        full = await svc.get_invoice_detail(invoice_id)
        assert full["invoice_number"] == "INV-005"
        assert len(full["lines"]) == 2
        assert len(full["payments"]) == 1
        assert float(full["payments"][0]["amount"]) == 100.0
