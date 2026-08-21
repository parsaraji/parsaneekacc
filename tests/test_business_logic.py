import os
import pytest
import shutil
from database.db import init_db
from database.repositories import UserRepository, StudentRepository, PaymentRepository, ExpenseRepository
from business_logic.auth import AuthService
from business_logic.financial import FinancialEngine
from business_logic.formatters import to_persian_digits, to_latin_digits, gregorian_to_shamsi, shamsi_to_gregorian, format_currency
from business_logic.backup import BackupManager

TEST_DB = "test_logic_db.db"
TEST_BACKUP_DIR = "test_backups"

@pytest.fixture(autouse=True)
def setup_teardown():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    if os.path.exists(TEST_BACKUP_DIR):
        shutil.rmtree(TEST_BACKUP_DIR)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    if os.path.exists(TEST_BACKUP_DIR):
        shutil.rmtree(TEST_BACKUP_DIR)

def test_auth_service():
    auth = AuthService(TEST_DB)
    auth.create_initial_manager()
    user = auth.login("admin", "admin123")
    assert user is not None
    assert user["role"] == "manager"
    assert auth.can_manage_users() is True
    assert auth.can_record_payment() is True

    # Failed login
    assert auth.login("admin", "wrongpass") is None

def test_financial_engine_discounts():
    fin = FinancialEngine(TEST_DB)
    # 1,000,000 - 10% (100,000) - 50,000 fixed discount + 20,000 late fee = 870,000
    res = fin.calculate_discounted_amount(1000000, discount_percent=10, discount_amount=50000, late_fee_amount=20000)
    assert res == 870000.0

def test_financial_engine_installments():
    fin = FinancialEngine(TEST_DB)
    sched = fin.generate_installment_schedule(1000000, 3, "1403/01/01")
    assert len(sched) == 3
    assert sched[0]["amount"] == 333333.33
    assert sched[1]["amount"] == 333333.33
    assert sched[2]["amount"] == 333333.34
    assert sum(s["amount"] for s in sched) == 1000000.0

def test_formatters():
    assert to_persian_digits("1234567890") == "۱۲۳۴۵۶۷۸۹۰"
    assert to_latin_digits("۱۲۳۴۵۶۷۸۹۰") == "1234567890"

    shamsi = gregorian_to_shamsi("2024-03-20")
    assert shamsi == "1403/01/01"

    greg = shamsi_to_gregorian("1403/01/01")
    assert greg == "2024-03-20"

    fmt = format_currency(1500000, unit="toman", use_persian_digits=True)
    assert "۱,۵۰۰,۰۰۰" in fmt
    assert "تومان" in fmt

def test_backup_and_restore():
    bm = BackupManager(TEST_DB, TEST_BACKUP_DIR)
    path = bm.create_backup()
    assert os.path.exists(path)

    # Modify DB then restore
    student_repo = StudentRepository(TEST_DB)
    student_repo.create_student("تست", "تستی")
    assert len(student_repo.search_students()) == 1

    bm.restore_backup(path)
    student_repo_restored = StudentRepository(TEST_DB)
    assert len(student_repo_restored.search_students()) == 0
