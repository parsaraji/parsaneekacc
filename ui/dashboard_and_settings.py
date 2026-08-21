import os
import shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QTextEdit,
    QDialog, QFormLayout, QMessageBox, QFileDialog, QDoubleSpinBox, QFrame, QTabWidget, QCheckBox
)
from PySide6.QtCore import Qt
from database.repositories import (
    StudentRepository, PaymentRepository, ExpenseRepository, ConfigRepository, UserRepository, AuditRepository
)
from business_logic.financial import FinancialEngine
from business_logic.formatters import to_persian_digits, to_latin_digits, gregorian_to_shamsi, format_currency
from business_logic.auth import AuthService
from business_logic.backup import BackupManager
from reports.excel_export import ExcelExporter
from theme.theme import create_neumorphic_shadow

class DashboardWidget(QWidget):
    """Neumorphic Dashboard Widget showing KPIs, recent payments, and capacity alerts."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.student_repo = StudentRepository(db_path)
        self.payment_repo = PaymentRepository(db_path)
        self.financial_engine = FinancialEngine(db_path)
        self.config_repo = ConfigRepository(db_path)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        kpi_layout = QHBoxLayout()

        self.card_students = self._create_card("دانش‌آموزان فعال", "0")
        self.card_income = self._create_card("درآمد کل ثبت‌شده", "0 تومان")
        self.card_debt = self._create_card("کل بدهی معوق", "0 تومان")
        self.card_expenses = self._create_card("هزینه‌ها و برداشت‌ها", "0 تومان")

        kpi_layout.addWidget(self.card_students)
        kpi_layout.addWidget(self.card_income)
        kpi_layout.addWidget(self.card_debt)
        kpi_layout.addWidget(self.card_expenses)

        layout.addLayout(kpi_layout)

        lbl_feed = QLabel("آخرین پرداخت‌های ثبت‌شده:")
        lbl_feed.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(lbl_feed)

        self.table_recent = QTableWidget()
        self.table_recent.setColumnCount(5)
        self.table_recent.setHorizontalHeaderLabels(["کد فاکتور", "دانش‌آموز", "بابت", "مبلغ", "تاریخ"])
        self.table_recent.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_recent)

        self.refresh_dashboard()

    def _create_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #E4E9F0;
                border: 1px solid #D0D7DE;
                border-radius: 12px;
                padding: 10px;
            }
        """)
        card.setGraphicsEffect(create_neumorphic_shadow(card))

        vbox = QVBoxLayout(card)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #7F8C8D; font-size: 11px;")
        lbl_val = QLabel(value)
        lbl_val.setObjectName("value_label")
        lbl_val.setStyleSheet("color: #2C3E50; font-size: 16px; font-weight: bold;")

        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_val)
        return card

    def refresh_dashboard(self):
        active_count = self.student_repo.count_students(status="active")
        fin = self.financial_engine.get_institute_financial_summary()

        unit = self.config_repo.get_setting("currency_unit", "toman")
        use_p = (self.config_repo.get_setting("numeral_format", "persian") == "persian")

        self.card_students.findChild(QLabel, "value_label").setText(to_persian_digits(active_count) if use_p else str(active_count))
        self.card_income.findChild(QLabel, "value_label").setText(format_currency(fin["total_income"], unit, use_p))
        self.card_debt.findChild(QLabel, "value_label").setText(format_currency(fin["total_outstanding_debt"], unit, use_p))
        self.card_expenses.findChild(QLabel, "value_label").setText(format_currency(fin["total_expenses"], unit, use_p))

        payments = self.payment_repo.list_payments(limit=10)
        self.table_recent.setRowCount(len(payments))
        for row, p in enumerate(payments):
            inv_code = p.get("invoice_code") or "-"
            if use_p:
                inv_code = to_persian_digits(inv_code)
            self.table_recent.setItem(row, 0, QTableWidgetItem(inv_code))
            self.table_recent.setItem(row, 1, QTableWidgetItem(p["student_name"]))
            self.table_recent.setItem(row, 2, QTableWidgetItem(p["payment_type_name"]))
            self.table_recent.setItem(row, 3, QTableWidgetItem(format_currency(p["amount"], unit, use_p)))
            self.table_recent.setItem(row, 4, QTableWidgetItem(gregorian_to_shamsi(p["paid_date"])))


class ExpensesWidget(QWidget):
    """View for managing institute expenses, insurance, and withdrawals."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.expense_repo = ExpenseRepository(db_path)
        self.config_repo = ConfigRepository(db_path)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.btn_add = QPushButton("ثبت هزینه / برداشت جدید +")
        self.btn_add.setProperty("accent", "true")
        self.btn_add.clicked.connect(self.add_expense)

        top_bar.addWidget(self.btn_add)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["دسته‌بندی", "مبلغ", "تاریخ", "توضیحات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.load_expenses()

    def load_expenses(self):
        expenses = self.expense_repo.list_expenses()
        self.table.setRowCount(len(expenses))

        unit = self.config_repo.get_setting("currency_unit", "toman")
        use_p = (self.config_repo.get_setting("numeral_format", "persian") == "persian")

        cat_map = {
            "rent": "اجاره",
            "salary": "حقوق",
            "printing": "چاپ",
            "supplies": "ملزومات",
            "insurance": "بیمه حوادث/تکمیلی",
            "withdrawal": "برداشت مدیر/صندوق",
            "other": "سایر"
        }

        for row, e in enumerate(expenses):
            cat_text = cat_map.get(e["category"], e["category"])
            self.table.setItem(row, 0, QTableWidgetItem(cat_text))
            self.table.setItem(row, 1, QTableWidgetItem(format_currency(e["amount"], unit, use_p)))
            self.table.setItem(row, 2, QTableWidgetItem(gregorian_to_shamsi(e["date"])))
            self.table.setItem(row, 3, QTableWidgetItem(e.get("description") or "-"))

    def add_expense(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("ثبت هزینه یا برداشت جدید")
        form = QFormLayout(dlg)

        cmb_cat = QComboBox()
        cmb_cat.addItem("اجاره", "rent")
        cmb_cat.addItem("حقوق", "salary")
        cmb_cat.addItem("چاپ و تکثیر", "printing")
        cmb_cat.addItem("ملزومات و اداری", "supplies")
        cmb_cat.addItem("بیمه دانش‌آموزی / تکمیلی", "insurance")
        cmb_cat.addItem("برداشت مدیر / برداشت از صندوق", "withdrawal")
        cmb_cat.addItem("سایر", "other")

        spn_amount = QDoubleSpinBox()
        spn_amount.setRange(0, 1000000000)
        spn_amount.setSingleStep(50000)
        spn_amount.setDecimals(0)

        txt_desc = QLineEdit()

        form.addRow("دسته‌بندی:", cmb_cat)
        form.addRow("مبلغ:", spn_amount)
        form.addRow("توضیحات:", txt_desc)

        btn = QPushButton("ذخیره")
        form.addRow(btn)

        def save():
            amt = spn_amount.value()
            if amt > 0:
                self.expense_repo.add_expense(cmb_cat.currentData(), amt, gregorian_to_shamsi(""), txt_desc.text().strip())
                dlg.accept()
                self.load_expenses()

        btn.clicked.connect(save)
        dlg.exec()


class ReportsWidget(QWidget):
    """View for financial reports and Excel exports."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.payment_repo = PaymentRepository(db_path)
        self.student_repo = StudentRepository(db_path)
        self.config_repo = ConfigRepository(db_path)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.btn_export_payments = QPushButton("خروجی اکسل تراکنش‌ها")
        self.btn_export_payments.clicked.connect(self.export_payments_excel)

        self.btn_export_students = QPushButton("خروجی اکسل دانش‌آموزان")
        self.btn_export_students.clicked.connect(self.export_students_excel)

        top_bar.addWidget(self.btn_export_payments)
        top_bar.addWidget(self.btn_export_students)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["کد فاکتور", "دانش‌آموز", "بابت", "مبلغ", "تاریخ", "وضعیت"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        payments = self.payment_repo.list_payments(limit=500)
        self.table.setRowCount(len(payments))

        unit = self.config_repo.get_setting("currency_unit", "toman")
        use_p = (self.config_repo.get_setting("numeral_format", "persian") == "persian")

        for row, p in enumerate(payments):
            inv_code = p.get("invoice_code") or "-"
            if use_p:
                inv_code = to_persian_digits(inv_code)
            self.table.setItem(row, 0, QTableWidgetItem(inv_code))
            self.table.setItem(row, 1, QTableWidgetItem(p["student_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(p["payment_type_name"]))
            self.table.setItem(row, 3, QTableWidgetItem(format_currency(p["amount"], unit, use_p)))
            self.table.setItem(row, 4, QTableWidgetItem(gregorian_to_shamsi(p["paid_date"])))
            self.table.setItem(row, 5, QTableWidgetItem("پرداخت‌شده" if p["status"] == "paid" else "معوق"))

    def export_payments_excel(self):
        filePath, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل اکسل", "", "Excel Files (*.xlsx)")
        if filePath:
            payments = self.payment_repo.list_payments(limit=5000)
            headers = ["کد فاکتور", "نام دانش‌آموز", "بابت", "مبلغ", "روش پرداخت", "تاریخ پرداخت", "وضعیت"]
            rows = []
            for p in payments:
                rows.append([
                    p.get("invoice_code", "-"),
                    p.get("student_name", "-"),
                    p.get("payment_type_name", "-"),
                    p.get("amount", 0.0),
                    p.get("method", "-"),
                    gregorian_to_shamsi(p.get("paid_date", "")),
                    p.get("status", "-")
                ])
            ExcelExporter.export_table_to_excel(filePath, headers, rows, title="گزارش تراکنش‌های مالی")
            QMessageBox.information(self, "موفقیت", "فایل اکسل با موفقیت ذخیره گردید.")

    def export_students_excel(self):
        filePath, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل اکسل دانش‌آموزان", "", "Excel Files (*.xlsx)")
        if filePath:
            students = self.student_repo.search_students(limit=5000)
            headers = ["کد دانش‌آموزی", "نام", "نام خانوادگی", "نام پدر", "شماره همراه", "وضعیت"]
            rows = []
            for s in students:
                rows.append([
                    s.get("unique_code", "-"),
                    s.get("first_name", "-"),
                    s.get("last_name", "-"),
                    s.get("father_name", "-"),
                    s.get("primary_phone", "-"),
                    s.get("status", "-")
                ])
            ExcelExporter.export_table_to_excel(filePath, headers, rows, title="لیست دانش‌آموزان")
            QMessageBox.information(self, "موفقیت", "فایل اکسل دانش‌آموزان با موفقیت ذخیره گردید.")


class SettingsWidget(QWidget):
    """View for POS configuration, Card destinations, numeral/currency toggles, Backups, and User Management with edit/delete controls."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.config_repo = ConfigRepository(db_path)
        self.user_repo = UserRepository(db_path)
        self.auth_service = AuthService(db_path)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Tab 1: General Config
        tab_general = QWidget()
        form = QFormLayout(tab_general)

        self.cmb_numeral = QComboBox()
        self.cmb_numeral.addItem("فارسی (۰۱۲۳۴۵۶۷۸۹)", "persian")
        self.cmb_numeral.addItem("لاتین (0123456789)", "latin")

        current_numeral = self.config_repo.get_setting("numeral_format", "persian")
        idx_num = self.cmb_numeral.findData(current_numeral)
        if idx_num >= 0:
            self.cmb_numeral.setCurrentIndex(idx_num)

        self.cmb_currency = QComboBox()
        self.cmb_currency.addItem("تومان", "toman")
        self.cmb_currency.addItem("ریال", "rial")

        current_currency = self.config_repo.get_setting("currency_unit", "toman")
        idx_curr = self.cmb_currency.findData(current_currency)
        if idx_curr >= 0:
            self.cmb_currency.setCurrentIndex(idx_curr)

        self.cmb_pagesize = QComboBox()
        self.cmb_pagesize.addItem("A4 (پیش‌فرض)", "A4")
        self.cmb_pagesize.addItem("A5", "A5")

        current_ps = self.config_repo.get_setting("invoice_page_size", "A4")
        idx_ps = self.cmb_pagesize.findData(current_ps)
        if idx_ps >= 0:
            self.cmb_pagesize.setCurrentIndex(idx_ps)

        form.addRow("فرمت نمایش ارقام:", self.cmb_numeral)
        form.addRow("واحد پول عمومی:", self.cmb_currency)
        form.addRow("سایز کاغذ فاکتور:", self.cmb_pagesize)

        btn_save_config = QPushButton("ذخیره تنظیمات عمومی")
        btn_save_config.setProperty("accent", "true")
        btn_save_config.clicked.connect(self.save_general_config)
        form.addRow(btn_save_config)

        btn_backup = QPushButton("پشتیبان‌گیری از دیتابیس (Backup)")
        btn_backup.clicked.connect(self.backup_db)
        form.addRow(btn_backup)

        tabs.addTab(tab_general, "تنظیمات عمومی")

        # Tab 2: POS Devices Management
        tab_pos = QWidget()
        pos_lay = QVBoxLayout(tab_pos)

        pos_top = QHBoxLayout()
        btn_add_pos = QPushButton("افزودن دستگاه کارت‌خوان +")
        btn_add_pos.setProperty("accent", "true")
        btn_add_pos.clicked.connect(self.add_pos_dialog)
        pos_top.addWidget(btn_add_pos)
        pos_top.addStretch()
        pos_lay.addLayout(pos_top)

        self.tbl_pos = QTableWidget()
        self.tbl_pos.setColumnCount(3)
        self.tbl_pos.setHorizontalHeaderLabels(["عنوان کارت‌خوان", "نام بانک", "عملیات"])
        self.tbl_pos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        pos_lay.addWidget(self.tbl_pos)

        tabs.addTab(tab_pos, "مدیریت دستگاه‌های کارت‌خوان")

        # Tab 3: Card Destinations Management
        tab_cards = QWidget()
        cards_lay = QVBoxLayout(tab_cards)

        cards_top = QHBoxLayout()
        btn_add_card = QPushButton("افزودن حساب کارت به کارت +")
        btn_add_card.setProperty("accent", "true")
        btn_add_card.clicked.connect(self.add_card_dialog)
        cards_top.addWidget(btn_add_card)
        cards_top.addStretch()
        cards_lay.addLayout(cards_top)

        self.tbl_cards = QTableWidget()
        self.tbl_cards.setColumnCount(3)
        self.tbl_cards.setHorizontalHeaderLabels(["شماره کارت", "نام دارنده حساب", "عملیات"])
        self.tbl_cards.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        cards_lay.addWidget(self.tbl_cards)

        tabs.addTab(tab_cards, "مدیریت حساب‌های کارت به کارت")

        # Tab 4: User Accounts Management
        tab_users = QWidget()
        u_layout = QVBoxLayout(tab_users)

        u_top = QHBoxLayout()
        btn_add_user = QPushButton("ایجاد کاربر جدید +")
        btn_add_user.setProperty("accent", "true")
        btn_add_user.clicked.connect(self.add_user_dialog)
        u_top.addWidget(btn_add_user)
        u_top.addStretch()
        u_layout.addLayout(u_top)

        self.tbl_users = QTableWidget()
        self.tbl_users.setColumnCount(5)
        self.tbl_users.setHorizontalHeaderLabels(["نام کاربری", "نام و نام خانوادگی", "نقش", "وضعیت", "عملیات"])
        self.tbl_users.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        u_layout.addWidget(self.tbl_users)

        tabs.addTab(tab_users, "مدیریت کاربران سیستم")

        layout.addWidget(tabs)
        self.load_users()
        self.load_pos_devices()
        self.load_card_destinations()

    def save_general_config(self):
        self.config_repo.set_setting("numeral_format", self.cmb_numeral.currentData())
        self.config_repo.set_setting("currency_unit", self.cmb_currency.currentData())
        self.config_repo.set_setting("invoice_page_size", self.cmb_pagesize.currentData())
        QMessageBox.information(self, "موفقیت", "تنظیمات عمومی با موفقیت ذخیره شد.")

    def load_pos_devices(self):
        pos_list = self.config_repo.list_pos_devices()
        self.tbl_pos.setRowCount(len(pos_list))
        for r, p in enumerate(pos_list):
            self.tbl_pos.setItem(r, 0, QTableWidgetItem(p["label"]))
            self.tbl_pos.setItem(r, 1, QTableWidgetItem(p.get("bank_name") or "-"))

            pnl = QWidget()
            lay = QHBoxLayout(pnl)
            lay.setContentsMargins(0, 0, 0, 0)

            btn_edit = QPushButton("ویرایش")
            btn_del = QPushButton("حذف")
            pid = p["id"]
            lbl = p["label"]
            bank = p.get("bank_name", "")

            btn_edit.clicked.connect(lambda _, id=pid, l=lbl, b=bank: self.edit_pos_dialog(id, l, b))
            btn_del.clicked.connect(lambda _, id=pid: self.delete_pos(id))

            lay.addWidget(btn_edit)
            lay.addWidget(btn_del)
            self.tbl_pos.setCellWidget(r, 2, pnl)

    def add_pos_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("افزودن دستگاه کارت‌خوان")
        form = QFormLayout(dlg)
        txt_label = QLineEdit()
        txt_bank = QLineEdit()
        form.addRow("عنوان کارت‌خوان:", txt_label)
        form.addRow("نام بانک:", txt_bank)
        btn = QPushButton("ذخیره")
        form.addRow(btn)

        def save():
            if txt_label.text().strip():
                self.config_repo.add_pos_device(txt_label.text().strip(), txt_bank.text().strip())
                dlg.accept()
                self.load_pos_devices()

        btn.clicked.connect(save)
        dlg.exec()

    def edit_pos_dialog(self, pos_id, current_label, current_bank):
        dlg = QDialog(self)
        dlg.setWindowTitle("ویرایش دستگاه کارت‌خوان")
        form = QFormLayout(dlg)
        txt_label = QLineEdit(current_label)
        txt_bank = QLineEdit(current_bank)
        form.addRow("عنوان کارت‌خوان:", txt_label)
        form.addRow("نام بانک:", txt_bank)
        btn = QPushButton("ذخیره ویرایش")
        form.addRow(btn)

        def save():
            if txt_label.text().strip():
                self.config_repo.update_pos_device(pos_id, txt_label.text().strip(), txt_bank.text().strip())
                dlg.accept()
                self.load_pos_devices()

        btn.clicked.connect(save)
        dlg.exec()

    def delete_pos(self, pos_id):
        if QMessageBox.question(self, "تأیید حذف", "آیا از حذف این دستگاه کارت‌خوان اطمینان دارید؟") == QMessageBox.Yes:
            self.config_repo.delete_pos_device(pos_id)
            self.load_pos_devices()

    def load_card_destinations(self):
        cards = self.config_repo.list_card_destinations()
        self.tbl_cards.setRowCount(len(cards))
        for r, c in enumerate(cards):
            self.tbl_cards.setItem(r, 0, QTableWidgetItem(to_persian_digits(c["card_number"])))
            self.tbl_cards.setItem(r, 1, QTableWidgetItem(c["owner_label"]))

            pnl = QWidget()
            lay = QHBoxLayout(pnl)
            lay.setContentsMargins(0, 0, 0, 0)

            btn_edit = QPushButton("ویرایش")
            btn_del = QPushButton("حذف")
            cid = c["id"]
            num = c["card_number"]
            owner = c["owner_label"]

            btn_edit.clicked.connect(lambda _, id=cid, n=num, o=owner: self.edit_card_dialog(id, n, o))
            btn_del.clicked.connect(lambda _, id=cid: self.delete_card(id))

            lay.addWidget(btn_edit)
            lay.addWidget(btn_del)
            self.tbl_cards.setCellWidget(r, 2, pnl)

    def add_card_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("افزودن حساب کارت به کارت")
        form = QFormLayout(dlg)
        txt_num = QLineEdit()
        txt_owner = QLineEdit()
        form.addRow("شماره کارت:", txt_num)
        form.addRow("نام دارنده حساب:", txt_owner)
        btn = QPushButton("ذخیره")
        form.addRow(btn)

        def save():
            if txt_num.text().strip() and txt_owner.text().strip():
                self.config_repo.add_card_destination(to_latin_digits(txt_num.text().strip()), txt_owner.text().strip())
                dlg.accept()
                self.load_card_destinations()

        btn.clicked.connect(save)
        dlg.exec()

    def edit_card_dialog(self, card_id, current_num, current_owner):
        dlg = QDialog(self)
        dlg.setWindowTitle("ویرایش حساب کارت به کارت")
        form = QFormLayout(dlg)
        txt_num = QLineEdit(current_num)
        txt_owner = QLineEdit(current_owner)
        form.addRow("شماره کارت:", txt_num)
        form.addRow("نام دارنده حساب:", txt_owner)
        btn = QPushButton("ذخیره ویرایش")
        form.addRow(btn)

        def save():
            if txt_num.text().strip() and txt_owner.text().strip():
                self.config_repo.update_card_destination(card_id, to_latin_digits(txt_num.text().strip()), txt_owner.text().strip())
                dlg.accept()
                self.load_card_destinations()

        btn.clicked.connect(save)
        dlg.exec()

    def delete_card(self, card_id):
        if QMessageBox.question(self, "تأیید حذف", "آیا از حذف این حساب کارت به کارت اطمینان دارید؟") == QMessageBox.Yes:
            self.config_repo.delete_card_destination(card_id)
            self.load_card_destinations()

    def backup_db(self):
        bm = BackupManager(self.db_path)
        path = bm.create_backup()
        QMessageBox.information(self, "پشتیبان‌گیری", f"فایل پشتیبان با موفقیت در مسیر زیر ایجاد شد:\n{path}")

    def load_users(self):
        users = self.user_repo.list_users()
        self.tbl_users.setRowCount(len(users))
        role_map = {"manager": "مدیر", "accountant": "حسابدار", "secretary": "منشی"}

        for r, u in enumerate(users):
            self.tbl_users.setItem(r, 0, QTableWidgetItem(u["username"]))
            self.tbl_users.setItem(r, 1, QTableWidgetItem(u["full_name"]))
            self.tbl_users.setItem(r, 2, QTableWidgetItem(role_map.get(u["role"], u["role"])))
            self.tbl_users.setItem(r, 3, QTableWidgetItem("فعال" if u["is_active"] else "غیرفعال"))

            btn_toggle = QPushButton("تغییر وضعیت")
            uid = u["id"]
            act = u["is_active"]
            fname = u["full_name"]
            role = u["role"]
            btn_toggle.clicked.connect(lambda _, id=uid, a=act, fn=fname, rl=role: self.toggle_user_active(id, fn, rl, a))
            self.tbl_users.setCellWidget(r, 4, btn_toggle)

    def toggle_user_active(self, user_id, full_name, role, is_active):
        self.user_repo.update_user(user_id, full_name, role, not is_active)
        self.load_users()

    def add_user_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("افزودن کاربر جدید")
        form = QFormLayout(dlg)

        txt_u = QLineEdit()
        txt_p = QLineEdit()
        txt_p.setEchoMode(QLineEdit.Password)
        txt_f = QLineEdit()

        cmb_r = QComboBox()
        cmb_r.addItem("مدیر", "manager")
        cmb_r.addItem("حسابدار", "accountant")
        cmb_r.addItem("منشی", "secretary")

        form.addRow("نام کاربری:", txt_u)
        form.addRow("کلمه عبور:", txt_p)
        form.addRow("نام و نام خانوادگی:", txt_f)
        form.addRow("نقش کاربر:", cmb_r)

        btn = QPushButton("ایجاد کاربر")
        form.addRow(btn)

        def save():
            u = txt_u.text().strip()
            p = txt_p.text().strip()
            f = txt_f.text().strip()
            if u and p and f:
                p_hash = self.auth_service.hash_password(p)
                self.user_repo.create_user(u, p_hash, f, cmb_r.currentData())
                dlg.accept()
                self.load_users()

        btn.clicked.connect(save)
        dlg.exec()
