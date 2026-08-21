import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QTextEdit,
    QDialog, QFormLayout, QMessageBox, QCheckBox, QDoubleSpinBox, QSpinBox, QTabWidget
)
from PySide6.QtCore import Qt, QMarginsF
from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog

from database.repositories import PaymentRepository, StudentRepository, TermRepository, ConfigRepository, DailyClosingRepository
from business_logic.formatters import to_persian_digits, to_latin_digits, gregorian_to_shamsi, format_currency, get_current_shamsi_date
from business_logic.financial import FinancialEngine
from reports.invoice_renderer import InvoiceTemplateRenderer

class RecordPaymentDialog(QDialog):
    """Dialog for recording a payment or installment plan against a student."""
    def __init__(self, db_path=None, student_id=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.student_id = student_id
        self.payment_repo = PaymentRepository(db_path)
        self.student_repo = StudentRepository(db_path)
        self.term_repo = TermRepository(db_path)
        self.config_repo = ConfigRepository(db_path)
        self.financial_engine = FinancialEngine(db_path)

        self.setWindowTitle("ثبت تراکنش پرداخت یا اقساط جدید")
        self.resize(500, 550)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Student Selection
        self.cmb_student = QComboBox()
        students = self.student_repo.search_students(limit=500)
        for s in students:
            self.cmb_student.addItem(f"{s['first_name']} {s['last_name']} ({s['unique_code']})", s['id'])

        if self.student_id:
            idx = self.cmb_student.findData(self.student_id)
            if idx >= 0:
                self.cmb_student.setCurrentIndex(idx)
                self.cmb_student.setEnabled(False)

        # Term
        self.cmb_term = QComboBox()
        terms = self.term_repo.list_terms()
        for t in terms:
            self.cmb_term.addItem(t["name"], t["id"])

        # Category
        self.cmb_type = QComboBox()
        ptypes = self.config_repo.list_payment_types()
        for pt in ptypes:
            self.cmb_type.addItem(pt["name"], pt["id"])

        # Amounts
        self.spn_amount = QDoubleSpinBox()
        self.spn_amount.setRange(0, 1000000000)
        self.spn_amount.setSingleStep(50000)
        self.spn_amount.setDecimals(0)

        self.spn_discount_pct = QDoubleSpinBox()
        self.spn_discount_pct.setRange(0, 100)

        self.spn_discount_amt = QDoubleSpinBox()
        self.spn_discount_amt.setRange(0, 100000000)
        self.spn_discount_amt.setDecimals(0)

        self.spn_late_fee = QDoubleSpinBox()
        self.spn_late_fee.setRange(0, 100000000)
        self.spn_late_fee.setDecimals(0)

        # Installment Plan Option
        self.chk_installment = QCheckBox("ثبت به صورت طرح اقساطی")
        self.chk_installment.toggled.connect(self.on_installment_toggled)

        self.spn_inst_count = QSpinBox()
        self.spn_inst_count.setRange(2, 24)
        self.spn_inst_count.setValue(3)
        self.spn_inst_count.setEnabled(False)

        # Method
        self.cmb_method = QComboBox()
        self.cmb_method.addItem("نقد", "cash")
        self.cmb_method.addItem("کارت‌خوان (POS)", "pos")
        self.cmb_method.addItem("کارت به کارت", "card_to_card")
        self.cmb_method.currentIndexChanged.connect(self.on_method_changed)

        # Configured POS / Card
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

        form.addRow("دانش‌آموز:", self.cmb_student)
        form.addRow("ترم:", self.cmb_term)
        form.addRow("بابت:", self.cmb_type)
        form.addRow("مبلغ اولیه:", self.spn_amount)
        form.addRow("تخفیف (درصد):", self.spn_discount_pct)
        form.addRow("تخفیف (مبلغی):", self.spn_discount_amt)
        form.addRow("جریمه/هزینه اضافی:", self.spn_late_fee)
        form.addRow("", self.chk_installment)
        form.addRow("تعداد اقساط:", self.spn_inst_count)
        form.addRow("روش پرداخت:", self.cmb_method)
        form.addRow("دستگاه کارت‌خوان:", self.cmb_pos)
        form.addRow("حساب کارت به کارت:", self.cmb_card)
        form.addRow("شماره پیگیری/فیش:", self.txt_ref_code)
        form.addRow("توضیحات:", self.txt_desc)

        layout.addLayout(form)

        # Buttons
        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("ثبت و صدور فاکتور")
        self.btn_save.setProperty("accent", "true")
        self.btn_save.clicked.connect(self.save_payment)

        self.btn_cancel = QPushButton("انصراف")
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_save)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)

        self.on_method_changed()

    def on_installment_toggled(self, checked: bool):
        self.spn_inst_count.setEnabled(checked)

    def on_method_changed(self):
        method = self.cmb_method.currentData()
        self.cmb_pos.setEnabled(method == "pos")
        self.cmb_card.setEnabled(method == "card_to_card")

    def save_payment(self):
        st_id = self.cmb_student.currentData()
        if not st_id:
            QMessageBox.warning(self, "خطا", "لطفاً دانش‌آموز را انتخاب کنید.")
            return

        base_amount = self.spn_amount.value()
        disc_pct = self.spn_discount_pct.value()
        disc_amt = self.spn_discount_amt.value()
        late_fee = self.spn_late_fee.value()

        final_amount = self.financial_engine.calculate_discounted_amount(base_amount, disc_pct, disc_amt, late_fee)
        if final_amount <= 0:
            QMessageBox.warning(self, "خطا", "مبلغ پرداخت نهایی باید بزرگتر از صفر باشد.")
            return

        method = self.cmb_method.currentData()
        pos_id = self.cmb_pos.currentData() if method == "pos" else None
        card_id = self.cmb_card.currentData() if method == "card_to_card" else None
        ref_code = to_latin_digits(self.txt_ref_code.text().strip())

        is_inst = self.chk_installment.isChecked()
        inst_count = self.spn_inst_count.value() if is_inst else 1

        if is_inst and inst_count > 1:
            schedule = self.financial_engine.generate_installment_schedule(final_amount, inst_count)
            for idx, inst in enumerate(schedule, 1):
                st = "paid" if idx == 1 else "pending"
                self.payment_repo.record_payment(
                    student_id=st_id,
                    payment_type_id=self.cmb_type.currentData(),
                    amount=inst["amount"],
                    method=method if idx == 1 else "cash",
                    term_id=self.cmb_term.currentData(),
                    pos_device_id=pos_id if idx == 1 else None,
                    card_destination_id=card_id if idx == 1 else None,
                    bank_reference_number=ref_code if idx == 1 else "",
                    description=f"{self.txt_desc.text().strip()} (قسط {idx} از {inst_count})",
                    is_installment=True,
                    installment_no=idx,
                    installment_total=inst_count,
                    status=st,
                    create_invoice=(st == "paid")
                )
        else:
            self.payment_repo.record_payment(
                student_id=st_id,
                payment_type_id=self.cmb_type.currentData(),
                amount=final_amount,
                method=method,
                term_id=self.cmb_term.currentData(),
                discount_percent=disc_pct,
                discount_amount=disc_amt,
                late_fee_amount=late_fee,
                pos_device_id=pos_id,
                card_destination_id=card_id,
                bank_reference_number=ref_code,
                card_tracking_code=ref_code,
                description=self.txt_desc.text().strip(),
                status="paid",
                create_invoice=True
            )

        QMessageBox.information(self, "موفقیت", "تراکنش با موفقیت ثبت گردید.")
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

        self.btn_new_payment = QPushButton(" ثبت پرداخت جدید +")
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
            self.table.setItem(row, 4, QTableWidgetItem(fmt_amt))

            self.table.setItem(row, 5, QTableWidgetItem(method_map.get(p["method"], p["method"])))
            self.table.setItem(row, 6, QTableWidgetItem(gregorian_to_shamsi(p["paid_date"])))

            btn_single_print = QPushButton("چاپ")
            p_id = p["id"]
            btn_single_print.clicked.connect(lambda _, id=p_id: self.print_single_invoice(id))
            self.table.setCellWidget(row, 7, btn_single_print)

    def record_new_payment(self):
        dlg = RecordPaymentDialog(db_path=self.db_path, parent=self)
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
