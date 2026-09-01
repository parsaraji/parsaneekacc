import os
import pytest
from database.db import init_db, get_connection
from database.repositories import (
    UserRepository, StudentRepository, TermRepository, ClassRepository,
    BookRepository, PaymentRepository
)
from business_logic.financial import FinancialEngine

TEST_DB = "test_batch_inventory.db"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_batch_inventory_fifo_and_financial_cogs():
    b_repo = BookRepository(TEST_DB)

    # 1. Register book with 100 items @ purchase_price 1000, sale_price 2000
    bid = b_repo.add_book("کتاب ریاضی کنکور", purchase_price=1000, sale_price=2000, stock_quantity=100)
    assert bid > 0
    assert b_repo.get_stock(bid) == 100
    batches = b_repo.list_batches(bid)
    assert len(batches) == 1
    assert batches[0]["quantity_remaining"] == 100

    # 2. Sell 50 items using FIFO
    consumed_1 = b_repo.consume_stock_fifo(bid, 50)
    assert len(consumed_1) == 1
    assert consumed_1[0]["quantity_taken"] == 50
    assert consumed_1[0]["purchase_price"] == 1000
    assert b_repo.get_stock(bid) == 50

    # 3. Restock 50 new items @ purchase_price 2000, sale_price 4000
    batch_2_id = b_repo.restock_book(bid, 50, purchase_price=2000, sale_price=4000, purchase_date="2024-04-01")
    assert batch_2_id > 0
    assert b_repo.get_stock(bid) == 100
    bk = b_repo.get_by_id(bid)
    assert bk["sale_price"] == 4000

    # 4. Sell 60 items using FIFO -> consumes 50 from batch 1 (cost=1000) + 10 from batch 2 (cost=2000)
    consumed_2 = b_repo.consume_stock_fifo(bid, 60)
    assert len(consumed_2) == 2
    assert consumed_2[0]["quantity_taken"] == 50
    assert consumed_2[0]["purchase_price"] == 1000
    assert consumed_2[1]["quantity_taken"] == 10
    assert consumed_2[1]["purchase_price"] == 2000
    assert b_repo.get_stock(bid) == 40

    total_cost_2 = sum(c["quantity_taken"] * c["purchase_price"] for c in consumed_2)
    weighted_cost_2 = total_cost_2 / 60.0
    assert abs(weighted_cost_2 - 1166.6666) < 0.01


def test_enrollment_records_book_cogs_and_batch_id():
    st_repo = StudentRepository(TEST_DB)
    sid = st_repo.create_student("علی", "رضایی", "محمد")

    term_repo = TermRepository(TEST_DB)
    tid = term_repo.create_term("ترم بهار")

    b_repo = BookRepository(TEST_DB)
    bid = b_repo.add_book("کتاب فیزیک ۱", purchase_price=3000, sale_price=5000, stock_quantity=10)

    class_repo = ClassRepository(TEST_DB)
    cid = class_repo.create_class("PHYS-1", "فیزیک عمومی", "استاد کریمی", tid, book_ids=[bid])

    # Enroll student in class (charges book fee)
    class_repo.add_enrollment(cid, sid)

    pay_repo = PaymentRepository(TEST_DB)
    payments = pay_repo.list_payments(student_id=sid)
    book_payments = [p for p in payments if "فیزیک" in p.get("description", "")]
    assert len(book_payments) == 1
    bp = book_payments[0]
    assert bp["book_id"] == bid
    assert bp["book_unit_cost"] == 3000

    # Settle debt via settle_and_record_transaction to verify metadata preservation & COGS reporting
    pay_repo.settle_and_record_transaction(
        student_id=sid,
        debt_settlements=[{"debt_id": bp["id"], "pay_amount": 5000, "total_debt_amount": 5000}],
        new_line_items=[],
        method="pos"
    )

    fin = FinancialEngine(TEST_DB)
    summary = fin.get_institute_financial_summary()
    assert summary["total_book_sales"] == 5000
    assert summary["book_cogs_cost"] == 3000
    assert summary["book_gross_profit"] == 2000


def test_book_inventory_financial_report():
    b_repo = BookRepository(TEST_DB)
    bid = b_repo.add_book("شیمی جامع", purchase_price=1000, sale_price=2000, stock_quantity=100)

    st_repo = StudentRepository(TEST_DB)
    sid1 = st_repo.create_student("سارا", "کاظمی")
    sid2 = st_repo.create_student("رضا", "نوری")

    pay_repo = PaymentRepository(TEST_DB)

    # 1. Paid sale for sid1
    c1 = b_repo.consume_stock_fifo(bid, 1)
    pay_repo.record_payment(
        student_id=sid1,
        payment_type_id=1,
        amount=2000,
        method="cash",
        description="کتاب شیمی جامع",
        status="paid",
        book_id=bid,
        book_batch_id=c1[0]["batch_id"],
        book_unit_cost=1000
    )

    # 2. Pending debt for sid2
    c2 = b_repo.consume_stock_fifo(bid, 1)
    pay_repo.record_payment(
        student_id=sid2,
        payment_type_id=1,
        amount=2000,
        method="cash",
        description="کتاب شیمی جامع",
        status="pending",
        book_id=bid,
        book_batch_id=c2[0]["batch_id"],
        book_unit_cost=1000
    )

    fin = FinancialEngine(TEST_DB)
    report = fin.get_book_inventory_financial_report(book_id=bid)

    assert report["total_purchase_cost"] == 100000  # 100 * 1000
    assert report["total_book_sales_revenue"] == 2000
    assert report["total_cogs"] == 1000
    assert report["book_gross_profit"] == 1000
    assert report["total_outstanding_receivables"] == 2000
    assert report["current_inventory_value"] == 98000  # 98 * 1000
    assert len(report["purchase_batches"]) == 1
    assert len(report["sales_transactions"]) == 2


def test_backfill_existing_books_on_init_db():
    # Insert raw book into sqlite directly without batch record to simulate old db
    conn = get_connection(TEST_DB)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO books (title, purchase_price, sale_price, stock_quantity) VALUES ('کتاب قدیمی', 1500, 3000, 25)"
    )
    conn.commit()
    conn.close()

    # Re-run init_db to trigger migration backfill
    init_db(TEST_DB)

    b_repo = BookRepository(TEST_DB)
    books = b_repo.list_books()
    old_bk = next(b for b in books if b["title"] == "کتاب قدیمی")
    batches = b_repo.list_batches(old_bk["id"])
    assert len(batches) == 1
    assert batches[0]["quantity_purchased"] == 25
    assert batches[0]["quantity_remaining"] == 25
    assert batches[0]["purchase_price"] == 1500
