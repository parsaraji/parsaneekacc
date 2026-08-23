import os
import pytest
import shutil
from database.db import init_db
from database.repositories import (
    UserRepository, StudentRepository, TermRepository, ClassRepository,
    PaymentRepository, ExpenseRepository, ConfigRepository
)
from business_logic.financial import FinancialEngine
from business_logic.formatters import format_currency, gregorian_to_shamsi, shamsi_to_gregorian, to_persian_digits
from reports.excel_export import ExcelExporter
from reports.invoice_renderer import InvoiceTemplateRenderer

TEST_DB = "test_full_suite.db"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_full_system_flow():
    # 1. Repositories
    user_repo = UserRepository(TEST_DB)
    uid = user_repo.create_user("accountant1", "hash", "حسابدار تستی", "accountant")
    assert uid > 0

    student_repo = StudentRepository(TEST_DB)
    sid = student_repo.create_student("امیر", "حسینی", "حسین", "تهران", "توضیحات", [{"phone_number": "09129999999", "is_primary": True}])
    student = student_repo.get_by_id(sid)
    assert student["unique_code"] == "PN-00001"

    term_repo = TermRepository(TEST_DB)
    tid = term_repo.create_term("زمستان ۱۴۰۳")

    class_repo = ClassRepository(TEST_DB)
    cid = class_repo.create_class("MATH-101", "ریاضیات کنکور", "استاد احمدی", tid, capacity=2)
    class_repo.add_enrollment(cid, sid)
    roster = class_repo.get_class_roster(cid)
    assert len(roster) == 1

    # Test update_enrollment_status with all status options
    enroll_id = roster[0]["enrollment_id"]
    for new_st in ["graduated", "dropped_out", "transferred_out", "active"]:
        class_repo.update_enrollment_status(enroll_id, new_st)

    # 2. Payment & Invoice
    pay_repo = PaymentRepository(TEST_DB)
    pid = pay_repo.record_payment(
        student_id=sid, payment_type_id=1, amount=1200000, method="pos",
        term_id=tid, recorded_by_user_id=uid
    )
    payment = pay_repo.get_payment_by_id(pid)
    assert payment["amount"] == 1200000
    assert payment["invoice_code"] is not None

    # 3. Financial Engine
    fin = FinancialEngine(TEST_DB)
    summary = fin.get_institute_financial_summary()
    assert summary["total_income"] == 1200000
    assert summary["income_pos"] == 1200000

    # 4. Expense
    exp_repo = ExpenseRepository(TEST_DB)
    exp_repo.add_expense("rent", 300000, "2024-03-20", "اجاره دفتر", uid)
    summary_after_exp = fin.get_institute_financial_summary()
    assert summary_after_exp["total_expenses"] == 300000
    assert summary_after_exp["net_income"] == 900000

    # 5. Invoice Renderer
    renderer = InvoiceTemplateRenderer(page_size="A4", use_persian_digits=True)
    html = renderer.render_batch_html([payment])
    assert "آموزشگاه پارسانیک" in html
    assert to_persian_digits(payment["invoice_code"]) in html

    # 6. Excel Export
    excel_path = "test_export.xlsx"
    ExcelExporter.export_table_to_excel(excel_path, ["عنوان", "مبلغ"], [["پرداخت", 1200000]])
    assert os.path.exists(excel_path)
    os.remove(excel_path)
