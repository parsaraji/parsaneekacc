import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QTextEdit,
    QDialog, QFormLayout, QMessageBox, QCheckBox, QDoubleSpinBox, QSpinBox, QTabWidget, QGroupBox
)
from PySide6.QtCore import Qt, QMarginsF
from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from datetime import datetime

from database.repositories import PaymentRepository, StudentRepository, TermRepository, ConfigRepository, DailyClosingRepository
from business_logic.formatters import to_persian_digits, to_latin_digits, gregorian_to_shamsi, format_currency, get_current_shamsi_date
from business_logic.financial import FinancialEngine
from reports.invoice_renderer import InvoiceTemplateRenderer
from ui.student_views import StudentPickerDialog

class RecordPaymentDialog(QDialog):
    """Dialog for recording multi-debt settlements and new line items in a single card swipe or cash transaction."""
    def __init__(self, db_path=None, student_id=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.student_id = student_id
        self.payment_repo = PaymentRepository(db_path)
        self.student_repo = StudentRepository(db_path)
        self.term_repo = TermRepository(db_path)
        self.config_repo = ConfigRepository(db_path)
        self.financial_engine = FinancialEngine(db_path)

        self.new_line_items = []
        self.pending_debts = []

        self.setWindowTitle("ثبت تراکنش دریافتی، تسویه بدهی‌ها و بابت جدید")
        self.resize(700, 680)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Student Selection with Search Picker Button
        st_box = QHBoxLayout()
        self.cmb_student = QComboBox()
        self.reload_students()
        self.cmb_student.currentIndexChanged.connect(self.on_student_changed)

        btn_search_st = QPushButton("جستجوی پیشرفته دانش‌آموز...")
        btn_search_st.clicked.connect(self.open_student_picker)

        st_box.addWidget(self.cmb_student, 3)
        st_box.addWidget(btn_search_st, 1)

        if self.student_id:
            idx = self.cmb_student.findData(self.student_id)
            if idx >= 0:
                self.cmb_student.setCurrentIndex(idx)
                self.cmb_student.setEnabled(False)
            btn_search_st.setEnabled(False)

        # Term
        self.cmb_term = QComboBox()
        terms = self.term_repo.list_terms()
        for t in terms:
            self.cmb_term.addItem(t["name"], t["id"])

        form.addRow("دانش‌آموز:", st_box)
        form.addRow("ترم:", self.cmb_term)
        layout.addLayout(form)

        # 1. Existing Debts Group (Table with editable settlement amounts)
        self.box_debts = QGroupBox("۱. تسویه بدهی‌های معوق دانش‌آموز (امکان پرداخت کامل یا بخشی از هر بدهی)")
        v_debts = QVBoxLayout(self.box_debts)

        self.tbl_debts = QTableWidget()
        self.tbl_debts.setColumnCount(4)
        self.tbl_debts.setHorizontalHeaderLabels(["عنوان / شرح بدهی", "کل بدهی (تومان)", "مبلغ واریزی الان (تومان)", "انتخاب"])
        self.tbl_debts.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v_debts.addWidget(self.tbl_debts)
        layout.addWidget(self.box_debts)

        # 2. Multi-item Charges Group (New Items Mode)
        self.box_items = QGroupBox("۲. افزودن بابت جدید در همین کارت کشیدن / دریافت (مانند ثبت‌نام اولیه، کتاب جدید، کلاس خصوصی)")
        v_items = QVBoxLayout(self.box_items)

        self.tbl_items = QTableWidget()
        self.tbl_items.setColumnCount(3)
        self.tbl_items.setHorizontalHeaderLabels(["بابت", "مبلغ (تومان)", "عملیات"])
        self.tbl_items.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v_items.addWidget(self.tbl_items)

        add_item_h = QHBoxLayout()
        self.cmb_item_type = QComboBox()
        ptypes = self.config_repo.list_payment_types()
        for pt in ptypes:
            self.cmb_item_type.addItem(pt["name"], pt["id"])

        self.spn_item_amount = QDoubleSpinBox()
        self.spn_item_amount.setRange(0, 1000000000)
        self.spn_item_amount.setSingleStep(50000)
        self.spn_item_amount.setDecimals(0)

        btn_add_line = QPushButton("افزودن آیتم جدید +")
        btn_add_line.clicked.connect(self.add_new_line_item)

        add_item_h.addWidget(self.cmb_item_type, 2)
        add_item_h.addWidget(self.spn_item_amount, 2)
        add_item_h.addWidget(btn_add_line, 1)
        v_items.addLayout(add_item_h)

        layout.addWidget(self.box_items)

        # Payment Status, Method and Details
        form_pay = QFormLayout()

        self.cmb_method = QComboBox()
        self.cmb_method.addItem("کارت‌خوان (POS)", "pos")
        self.cmb_method.addItem("نقد", "cash")
        self.cmb_method.addItem("کارت به کارت", "card_to_card")
        self.cmb_method.currentIndexChanged.connect(self.on_method_changed)

        self.cmb_pos = QComboBox()
        pos_list = self.config_repo.list_pos_devices()
        for p in pos_list:
            self.cmb_pos.addItem(f"{p['label']} ({p.get('bank_name', '')})", p['id'])

        self.cmb_card = QComboBox()
        cards = self.config_repo.list_card_destinations()
        for c in cards:
            self.cmb_card.addItem(f"{c['owner_label']} - {c['card_number']}", c['id'])

        self.txt_ref_code = QLineEdit()
        self.txt_ref_code.setPlaceholderText("کد پیگیری یا شماره فیش")

        self.txt_desc = QLineEdit()

        form_pay.addRow("روش پرداخت:", self.cmb_method)
        form_pay.addRow("دستگاه کارت‌خوان:", self.cmb_pos)
        form_pay.addRow("حساب کارت به کارت:", self.cmb_card)
        form_pay.addRow("شماره پیگیری/فیش:", self.txt_ref_code)
        form_pay.addRow("توضیحات کلی:", self.txt_desc)

        layout.addLayout(form_pay)

        # Total Swipe / Payment Label
        self.lbl_total_sum = QLabel("مجموع کل کارت کشیدن / واریزی این فاکتور: ۰ تومان")
        self.lbl_total_sum.setStyleSheet("font-size: 14px; font-weight: bold; color: #27AE60; margin-top: 5px;")
        layout.addWidget(self.lbl_total_sum)

        # Buttons
        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("ثبت نهایی تراکنش و صدور تک‌فاکتور")
        self.btn_save.setProperty("accent", "true")
        self.btn_save.clicked.connect(self.save_payment)

        self.btn_cancel = QPushButton("انصراف")
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_save)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)

        self.on_student_changed()
        self.on_method_changed()

    def reload_students(self):
        self.cmb_student.clear()
        students = self.student_repo.search_students(limit=500)
        for s in students:
            self.cmb_student.addItem(f"{s['first_name']} {s['last_name']} ({s['unique_code']})", s['id'])

    def open_student_picker(self):
        picker = StudentPickerDialog(db_path=self.db_path, parent=self)
        if picker.exec() == QDialog.Accepted and picker.selected_student:
            st = picker.selected_student
            idx = self.cmb_student.findData(st["id"])
            if idx >= 0:
                self.cmb_student.setCurrentIndex(idx)

    def on_student_changed(self):
        st_id = self.cmb_student.currentData()
        self.pending_debts = []
        if st_id:
            all_p = self.payment_repo.list_payments(student_id=st_id, limit=300)
            self.pending_debts = [p for p in all_p if p["status"] == "pending"]

        self.refresh_debts_table()

    def refresh_debts_table(self):
        self.tbl_debts.setRowCount(len(self.pending_debts))
        for r, d in enumerate(self.pending_debts):
            desc = d.get("description") or d.get("payment_type_name", "بدهی")
            self.tbl_debts.setItem(r, 0, QTableWidgetItem(desc))
            self.tbl_debts.setItem(r, 1, QTableWidgetItem(format_currency(d["amount"])))

            spn = QDoubleSpinBox()
            spn.setRange(0, d["amount"])
            spn.setValue(d["amount"]) # default full settlement
            spn.setSingleStep(50000)
            spn.setDecimals(0)
            spn.valueChanged.connect(self.recalculate_total_payment)

            chk = QCheckBox()
            chk.setChecked(True) # checked by default
            chk.toggled.connect(self.recalculate_total_payment)

            self.tbl_debts.setCellWidget(r, 2, spn)

            chk_widget = QWidget()
            chk_lay = QHBoxLayout(chk_widget)
            chk_lay.addWidget(chk)
            chk_lay.setAlignment(Qt.AlignCenter)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            self.tbl_debts.setCellWidget(r, 3, chk_widget)

        self.recalculate_total_payment()

    def add_new_line_item(self):
        amt = self.spn_item_amount.value()
        if amt <= 0:
            QMessageBox.warning(self, "خطا", "لطفاً مبلغ معتبر وارد کنید.")
            return

        pt_id = self.cmb_item_type.currentData()
        pt_name = self.cmb_item_type.currentText()

        self.new_line_items.append({
            "payment_type_id": pt_id,
            "name_label": pt_name,
            "amount": amt
        })
        self.refresh_new_items_table()

    def refresh_new_items_table(self):
        self.tbl_items.setRowCount(len(self.new_line_items))
        for r, item in enumerate(self.new_line_items):
            self.tbl_items.setItem(r, 0, QTableWidgetItem(item["name_label"]))
            self.tbl_items.setItem(r, 1, QTableWidgetItem(format_currency(item["amount"])))

            btn_del = QPushButton("حذف")
            idx = r
            btn_del.clicked.connect(lambda _, i=idx: self.remove_new_line_item(i))
            self.tbl_items.setCellWidget(r, 2, btn_del)

        self.recalculate_total_payment()

    def remove_new_line_item(self, index: int):
        if 0 <= index < len(self.new_line_items):
            self.new_line_items.pop(index)
            self.refresh_new_items_table()

    def recalculate_total_payment(self):
        total_settled_debts = 0.0
        for r in range(self.tbl_debts.rowCount()):
            chk_widget = self.tbl_debts.cellWidget(r, 3)
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                if chk and chk.isChecked():
                    spn = self.tbl_debts.cellWidget(r, 2)
                    if spn:
                        total_settled_debts += spn.value()

        total_new_items = sum(item["amount"] for item in self.new_line_items)
        grand_total = total_settled_debts + total_new_items

        self.lbl_total_sum.setText(f"مجموع کل کارت کشیدن / واریزی این فاکتور: {format_currency(grand_total)}")

    def on_method_changed(self):
        method = self.cmb_method.currentData()
        self.cmb_pos.setEnabled(method == "pos")
        self.cmb_card.setEnabled(method == "card_to_card")

    def save_payment(self):
        st_id = self.cmb_student.currentData()
        if not st_id:
            QMessageBox.warning(self, "خطا", "لطفاً دانش‌آموز را انتخاب کنید.")
            return

        debt_settlements = []
        for r in range(self.tbl_debts.rowCount()):
            chk_widget = self.tbl_debts.cellWidget(r, 3)
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                if chk and chk.isChecked():
                    spn = self.tbl_debts.cellWidget(r, 2)
                    pay_val = spn.value() if spn else 0
                    if pay_val > 0 and r < len(self.pending_debts):
                        d_info = self.pending_debts[r]
                        debt_settlements.append({
                            "debt_id": d_info["id"],
                            "pay_amount": pay_val,
                            "total_debt_amount": d_info["amount"],
                            "description": d_info.get("description") or d_info.get("payment_type_name", "بدهی")
                        })

        if not debt_settlements and not self.new_line_items:
            QMessageBox.warning(self, "خطا", "هیچ بدهی برای تسویه انتخاب نشده و هیچ بابت جدیدی افزوده‌نشده است.")
            return

        method = self.cmb_method.currentData()
        pos_id = self.cmb_pos.currentData() if method == "pos" else None
        card_id = self.cmb_card.currentData() if method == "card_to_card" else None
        ref_code = to_latin_digits(self.txt_ref_code.text().strip())

        # Atomic transaction call - zero database lock
        res_pid = self.payment_repo.settle_and_record_transaction(
            student_id=st_id,
            debt_settlements=debt_settlements,
            new_line_items=self.new_line_items,
            method=method,
            term_id=self.cmb_term.currentData(),
            pos_device_id=pos_id,
            card_destination_id=card_id,
            bank_reference_number=ref_code,
            card_tracking_code=ref_code,
            description=self.txt_desc.text().strip()
        )

        QMessageBox.information(self, "موفقیت", "تراکنش مالی با موفقیت ثبت و تک‌فاکتور صادر گردید.")
        self.accept()


class DailyClosingDialog(QDialog):
    """Dialog for performing or viewing daily closings."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.closing_repo = DailyClosingRepository(db_path)
        self.config_repo = ConfigRepository(db_path)

        self.setWindowTitle("بستن صندوق و بستن روزانه")
        self.resize(550, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_h = QHBoxLayout()
        btn_close_today = QPushButton("بستن صندوق امروز")
        btn_close_today.setProperty("accent", "true")
        btn_close_today.clicked.connect(self.do_close_today)

        top_h.addWidget(btn_close_today)
        top_h.addStretch()
        layout.addLayout(top_h)

        lbl_hist = QLabel("سابقه بستن صندوق روزانه:")
        lbl_hist.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(lbl_hist)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["تاریخ", "جمع نقد", "جمع کارت‌خوان", "جمع کارت به کارت", "مجموع کل"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.load_closings()

    def load_closings(self):
        closings = self.closing_repo.list_closings()
        self.table.setRowCount(len(closings))

        unit = self.config_repo.get_setting("currency_unit", "toman")
        use_p = (self.config_repo.get_setting("numeral_format", "persian") == "persian")

        for r, c in enumerate(closings):
            self.table.setItem(r, 0, QTableWidgetItem(gregorian_to_shamsi(c["date"])))
            self.table.setItem(r, 1, QTableWidgetItem(format_currency(c["total_cash"], unit, use_p)))
            self.table.setItem(r, 2, QTableWidgetItem(format_currency(c["total_pos"], unit, use_p)))
            self.table.setItem(r, 3, QTableWidgetItem(format_currency(c["total_card_to_card"], unit, use_p)))
            self.table.setItem(r, 4, QTableWidgetItem(format_currency(c["total_amount"], unit, use_p)))

    def do_close_today(self):
        import datetime
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        self.closing_repo.perform_daily_closing(today_str)
        QMessageBox.information(self, "موفقیت", "صندوق امروز با موفقیت بسته شد.")
        self.load_closings()


class PaymentsAndInvoicingWidget(QWidget):
    """View for listing payments, batch invoicing, and daily closings."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.payment_repo = PaymentRepository(db_path)
        self.config_repo = ConfigRepository(db_path)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()

        self.btn_new_payment = QPushButton(" ثبت پرداخت / تسویه بدهی +")
        self.btn_new_payment.setProperty("accent", "true")
        self.btn_new_payment.clicked.connect(self.record_new_payment)

        self.btn_batch_print = QPushButton("چاپ گروهی فاکتورهای انتخابی")
        self.btn_batch_print.clicked.connect(self.batch_print_invoices)

        self.btn_daily_closing = QPushButton("بستن صندوق روزانه")
        self.btn_daily_closing.clicked.connect(self.open_daily_closing)

        top_bar.addWidget(self.btn_new_payment)
        top_bar.addWidget(self.btn_batch_print)
        top_bar.addWidget(self.btn_daily_closing)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "انتخاب", "کد فاکتور", "دانش‌آموز", "بابت", "مبلغ", "روش پرداخت", "تاریخ", "عملیات"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.load_payments()

    def load_payments(self):
        payments = self.payment_repo.list_payments(limit=300)
        self.table.setRowCount(len(payments))

        currency_unit = self.config_repo.get_setting("currency_unit", "toman")
        numeral_fmt = self.config_repo.get_setting("numeral_format", "persian")
        use_persian = (numeral_fmt == "persian")

        method_map = {"cash": "نقد", "pos": "کارت‌خوان", "card_to_card": "کارت به کارت"}

        for row, p in enumerate(payments):
            chk = QCheckBox()
            chk.setProperty("payment_id", p["id"])
            chk_widget = QWidget()
            chk_lay = QHBoxLayout(chk_widget)
            chk_lay.addWidget(chk)
            chk_lay.setAlignment(Qt.AlignCenter)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, chk_widget)

            inv_code = p.get("invoice_code") or "-"
            if use_persian:
                inv_code = to_persian_digits(inv_code)

            self.table.setItem(row, 1, QTableWidgetItem(inv_code))
            self.table.setItem(row, 2, QTableWidgetItem(p["student_name"]))
            self.table.setItem(row, 3, QTableWidgetItem(p["payment_type_name"]))

            fmt_amt = format_currency(p["amount"], currency_unit, use_persian)
            amt_item = QTableWidgetItem(fmt_amt)
            if p["status"] == "pending":
                amt_item.setForeground(Qt.red)
            self.table.setItem(row, 4, amt_item)

            self.table.setItem(row, 5, QTableWidgetItem(method_map.get(p["method"], p["method"])))
            self.table.setItem(row, 6, QTableWidgetItem(gregorian_to_shamsi(p["paid_date"])))

            btn_single_print = QPushButton("چاپ")
            p_id = p["id"]
            btn_single_print.clicked.connect(lambda _, id=p_id: self.print_single_invoice(id))
            self.table.setCellWidget(row, 7, btn_single_print)

    def record_new_payment(self):
        dlg = RecordPaymentDialog(db_path=self.db_path, parent=self)
        dlg.setWindowState(dlg.windowState() | Qt.WindowMaximized)
        if dlg.exec() == QDialog.Accepted:
            self.load_payments()

    def open_daily_closing(self):
        dlg = DailyClosingDialog(db_path=self.db_path, parent=self)
        dlg.exec()

    def get_selected_payment_ids(self) -> list:
        selected_ids = []
        for row in range(self.table.rowCount()):
            chk_widget = self.table.cellWidget(row, 0)
            if chk_widget:
                chk = chk_widget.findChild(QCheckBox)
                if chk and chk.isChecked():
                    selected_ids.append(chk.property("payment_id"))
        return selected_ids

    def print_single_invoice(self, payment_id: int):
        self._print_invoices([payment_id])

    def batch_print_invoices(self):
        selected_ids = self.get_selected_payment_ids()
        if not selected_ids:
            QMessageBox.warning(self, "خطا", "لطفاً حداقل یک فاکتور را برای چاپ انتخاب کنید.")
            return
        self._print_invoices(selected_ids)

    def _print_invoices(self, payment_ids: list):
        items = []
        for pid in payment_ids:
            p_data = self.payment_repo.get_payment_by_id(pid)
            if p_data:
                items.append(p_data)

        if not items:
            return

        currency_unit = self.config_repo.get_setting("currency_unit", "toman")
        numeral_fmt = self.config_repo.get_setting("numeral_format", "persian")
        page_size_setting = self.config_repo.get_setting("invoice_page_size", "A4")

        renderer = InvoiceTemplateRenderer(
            currency_unit=currency_unit,
            use_persian_digits=(numeral_fmt == "persian"),
            page_size=page_size_setting
        )
        html_content = renderer.render_batch_html(items)

        printer = QPrinter(QPrinter.HighResolution)
        page_sz = QPageSize(QPageSize.A5) if page_size_setting.upper() == "A5" else QPageSize(QPageSize.A4)
        printer.setPageSize(page_sz)

        margin_mm = 5.0 if page_size_setting.upper() == "A5" else 8.0
        printer.setPageMargins(QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm), QPageLayout.Millimeter)

        doc = QTextDocument()
        doc.setPageSize(printer.pageLayout().paintRect(QPageLayout.Point).size())
        doc.setHtml(html_content)

        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(lambda p: doc.print_(p))
        preview.exec()
