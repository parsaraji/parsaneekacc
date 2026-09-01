import os
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QTextEdit,
    QDialog, QFormLayout, QMessageBox, QTabWidget, QFileDialog, QListWidget, QListWidgetItem,
    QCheckBox, QDoubleSpinBox, QGroupBox
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from database.repositories import StudentRepository, TermRepository, ClassRepository, AuditRepository, AttachmentRepository, PaymentRepository, ConfigRepository, BookRepository
from business_logic.formatters import to_persian_digits, to_latin_digits, gregorian_to_shamsi, format_currency
from business_logic.financial import FinancialEngine
from reports.excel_export import ExcelExporter

class StudentDialog(QDialog):
    """Dialog for creating or editing a student with direct class enrollment and initial registration fee option."""
    def __init__(self, parent=None, db_path=None, student_id=None, user_id=None):
        super().__init__(parent)
        self.db_path = db_path
        self.student_id = student_id
        self.user_id = user_id
        self.student_repo = StudentRepository(db_path)
        self.class_repo = ClassRepository(db_path)
        self.payment_repo = PaymentRepository(db_path)
        self.config_repo = ConfigRepository(db_path)

        self.setWindowTitle("ویرایش دانش‌آموز" if student_id else "افزودن دانش‌آموز جدید")
        self.resize(500, 500)
        self.init_ui()
        if student_id:
            self.load_student_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.txt_first_name = QLineEdit()
        self.txt_last_name = QLineEdit()
        self.txt_father_name = QLineEdit()
        self.txt_phone = QLineEdit()
        self.txt_phone.setPlaceholderText("مثال: ۰۹۱۲۳۴۵۶۷۸۹")
        self.txt_address = QLineEdit()

        self.cmb_status = QComboBox()
        self.cmb_status.addItem("فعال", "active")
        self.cmb_status.addItem("غیرفعال", "inactive")
        self.cmb_status.addItem("انصرافی", "dropped_out")
        self.cmb_status.addItem("فارغ‌التحصیل", "graduated")

        self.cmb_class = QComboBox()
        self.cmb_class.addItem("-- بدون ثبت‌نام اولیه در کلاس --", None)
        active_classes = self.class_repo.list_classes(status="active")
        for c in active_classes:
            self.cmb_class.addItem(f"{c['name']} ({c['code']}) - شهریه: {format_currency(c['tuition_fee'])}", c['id'])

        self.chk_reg_fee = QCheckBox("افزودن بدهی هزینه ثبت‌نام اولیه")
        self.spn_reg_fee = QDoubleSpinBox()
        self.spn_reg_fee.setRange(0, 100000000)
        self.spn_reg_fee.setValue(100000)
        self.spn_reg_fee.setSingleStep(10000)
        self.spn_reg_fee.setDecimals(0)
        self.spn_reg_fee.setEnabled(False)
        self.chk_reg_fee.toggled.connect(lambda chk: self.spn_reg_fee.setEnabled(chk))

        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(70)

        form.addRow("نام:", self.txt_first_name)
        form.addRow("نام خانوادگی:", self.txt_last_name)
        form.addRow("نام پدر:", self.txt_father_name)
        form.addRow("شماره همراه اصلی:", self.txt_phone)
        form.addRow("آدرس:", self.txt_address)
        form.addRow("وضعیت:", self.cmb_status)
        if not self.student_id:
            form.addRow("ثبت‌نام مستقیم در کلاس:", self.cmb_class)
            form.addRow(self.chk_reg_fee, self.spn_reg_fee)
        form.addRow("یادداشت خصوصی:", self.txt_notes)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("ذخیره دانش‌آموز")
        self.btn_save.setProperty("accent", "true")
        self.btn_save.clicked.connect(self.save)

        self.btn_cancel = QPushButton("انصراف")
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_save)
        btn_box.addWidget(self.btn_cancel)
        layout.addLayout(btn_box)

    def load_student_data(self):
        s = self.student_repo.get_by_id(self.student_id)
        if s:
            self.txt_first_name.setText(s["first_name"])
            self.txt_last_name.setText(s["last_name"])
            self.txt_father_name.setText(s.get("father_name", ""))
            self.txt_address.setText(s.get("address", ""))
            self.txt_notes.setText(s.get("private_notes", ""))

            idx = self.cmb_status.findData(s.get("status", "active"))
            if idx >= 0:
                self.cmb_status.setCurrentIndex(idx)

            phones = self.student_repo.get_phones(self.student_id)
            if phones:
                self.txt_phone.setText(phones[0]["phone_number"])

    def save(self):
        first_name = self.txt_first_name.text().strip()
        last_name = self.txt_last_name.text().strip()
        phone = to_latin_digits(self.txt_phone.text().strip())

        if not first_name or not last_name:
            QMessageBox.warning(self, "خطا", "لطفاً نام و نام خانوادگی را وارد کنید.")
            return

        status = self.cmb_status.currentData()
        father_name = self.txt_father_name.text().strip()
        address = self.txt_address.text().strip()
        notes = self.txt_notes.toPlainText().strip()

        if self.student_id:
            self.student_repo.update_student(self.student_id, first_name, last_name, father_name, address, status, notes, user_id=self.user_id)
            if phone:
                self.student_repo.set_primary_phone(self.student_id, phone, "همراه")
        else:
            phones_list = [{"phone_number": phone, "is_primary": True}] if phone else None
            self.student_id = self.student_repo.create_student(first_name, last_name, father_name, address, notes, phones_list, user_id=self.user_id)

            chosen_cid = self.cmb_class.currentData()
            if chosen_cid:
                self.class_repo.add_enrollment(chosen_cid, self.student_id)

            if self.chk_reg_fee.isChecked() and self.spn_reg_fee.value() > 0:
                ptypes = self.config_repo.list_payment_types()
                reg_pt_id = 1
                for pt in ptypes:
                    if "ثبت‌نام" in pt["name"]:
                        reg_pt_id = pt["id"]
                        break
                self.payment_repo.record_payment(
                    student_id=self.student_id,
                    payment_type_id=reg_pt_id,
                    amount=self.spn_reg_fee.value(),
                    method="cash",
                    description="هزینه ثبت‌نام اولیه دانش‌آموز",
                    status="pending",
                    create_invoice=False
                )

        self.accept()


class StudentProfileDialog(QDialog):
    """Full Student Profile Dialog with Distinct Paid vs Pending Debt Ledgers & Creditor/Debtor Status."""
    def __init__(self, student_id, db_path=None, parent=None):
        super().__init__(parent)
        self.student_id = student_id
        self.db_path = db_path
        self.student_repo = StudentRepository(db_path)
        self.class_repo = ClassRepository(db_path)
        self.term_repo = TermRepository(db_path)
        self.financial_engine = FinancialEngine(db_path)
        self.payment_repo = PaymentRepository(db_path)
        self.audit_repo = AuditRepository(db_path)
        self.attachment_repo = AttachmentRepository(db_path)

        self.setWindowTitle("شناسنامه کامل و تراز مالی دانش‌آموز")
        self.setWindowState(self.windowState() | Qt.WindowMaximized)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        student = self.student_repo.get_by_id(self.student_id)
        if not student:
            layout.addWidget(QLabel("دانش‌آموز یافت نشد."))
            return

        hdr_box = QHBoxLayout()
        header = QLabel(f"پروفایل: {student['first_name']} {student['last_name']} ({student['unique_code']})")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2980B9;")

        lbl_photo = QLabel()
        lbl_photo.setFixedSize(70, 70)
        lbl_photo.setStyleSheet("border: 2px solid #2980B9; border-radius: 35px; background-color: #ECF0F1;")
        lbl_photo.setAlignment(Qt.AlignCenter)
        lbl_photo.setText("عکس")

        # Load student photo from attachments if available
        atts = self.attachment_repo.list_attachments(self.student_id)
        for a in atts:
            cat = a.get("category", "")
            fpath = a.get("file_path", "")
            if "عکس" in cat or fpath.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                if os.path.exists(fpath):
                    from PySide6.QtGui import QPixmap
                    pix = QPixmap(fpath).scaled(70, 70, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    lbl_photo.setPixmap(pix)
                    break

        hdr_box.addWidget(lbl_photo)
        hdr_box.addWidget(header, 1)
        layout.addLayout(hdr_box)

        tabs = QTabWidget()

        # Tab 1: Separated Ledgers (Paid vs Pending) & Debtor/Creditor Status
        tab_summary = QWidget()
        sum_layout = QVBoxLayout(tab_summary)
        fin = self.financial_engine.get_student_financial_summary(self.student_id)

        info_h = QHBoxLayout()
        info_h.addWidget(QLabel(f"کد: {student['unique_code']}"))
        info_h.addWidget(QLabel(f"نام پدر: {student.get('father_name', '-')}"))
        info_h.addWidget(QLabel(f"مجموع پرداختی‌های وصول‌شده: {format_currency(fin['total_paid'])}"))

        debt_amt = fin['total_pending_debt']
        net_bal = fin.get('net_balance', 0.0)
        if debt_amt > 0:
            status_str = f"وضعیت حساب: بدهکار ({format_currency(debt_amt)})"
            lbl_status = QLabel(status_str)
            lbl_status.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 13px;")
        elif net_bal > 0 and fin.get('total_paid', 0) > 0:
            status_str = f"وضعیت حساب: بستانکار / دارای پیش‌پرداخت ({format_currency(net_bal)})"
            lbl_status = QLabel(status_str)
            lbl_status.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 13px;")
        else:
            status_str = "وضعیت حساب: تسویه کامل (بدون بدهی)"
            lbl_status = QLabel(status_str)
            lbl_status.setStyleSheet("color: #27AE60; font-weight: bold; font-size: 13px;")

        info_h.addWidget(lbl_status)
        sum_layout.addLayout(info_h)

        # 1. Pending Debts Table & Debt Creation (Private Class & Inventory Goods)
        h_debt_top = QHBoxLayout()
        lbl_debts = QLabel("۱. لیست بدهی‌های معوق و تسویه‌نشده دانش‌آموز (مستقل از پرداختی‌ها):")
        lbl_debts.setStyleSheet("font-weight: bold; color: #C0392B; margin-top: 5px;")

        btn_add_inv_goods = QPushButton("ثبت بدهی کتاب/کالا از انبار +")
        btn_add_inv_goods.setProperty("accent", "true")
        btn_add_inv_goods.clicked.connect(self.add_inventory_item_charge)

        btn_add_private_class = QPushButton("ثبت کلاس خصوصی / بدهی سفارشی +")
        btn_add_private_class.clicked.connect(self.add_private_class_charge)

        h_debt_top.addWidget(lbl_debts)
        h_debt_top.addStretch()
        h_debt_top.addWidget(btn_add_inv_goods)
        h_debt_top.addWidget(btn_add_private_class)
        sum_layout.addLayout(h_debt_top)

        self.tbl_pending = QTableWidget()
        self.tbl_pending.setColumnCount(5)
        self.tbl_pending.setHorizontalHeaderLabels(["تاریخ ثبت بدهی", "شرح و بابت بدهی", "مبلغ بدهی (تومان)", "وضعیت", "عملیات"])
        for col in range(4):
            self.tbl_pending.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.tbl_pending.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        sum_layout.addWidget(self.tbl_pending)

        # 2. Paid Payments Table
        lbl_paid = QLabel("۲. لیست پرداختی‌های وصول‌شده و فاکتورهای صادرشده (مستقل از بدهی‌ها):")
        lbl_paid.setStyleSheet("font-weight: bold; color: #27AE60; margin-top: 5px;")
        sum_layout.addWidget(lbl_paid)

        self.tbl_paid = QTableWidget()
        self.tbl_paid.setColumnCount(6)
        self.tbl_paid.setHorizontalHeaderLabels(["تاریخ و زمان", "شرح و بابت", "روش پرداخت", "مبلغ پرداختی (تومان)", "کد پیگیری / فاکتور", "نمایش / چاپ فاکتور"])
        for col in range(5):
            self.tbl_paid.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.tbl_paid.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        sum_layout.addWidget(self.tbl_paid)

        btn_export_st_ledger = QPushButton("خروجی اکسل تراز مالی کامل این دانش‌آموز")
        btn_export_st_ledger.setProperty("accent", "true")
        btn_export_st_ledger.clicked.connect(self.export_student_ledger_excel)
        sum_layout.addWidget(btn_export_st_ledger, alignment=Qt.AlignRight)

        self.load_financial_ledgers()
        tabs.addTab(tab_summary, "تراز مالی و بدهی‌ها")

        # Tab 2: Phone Numbers
        tab_phones = QWidget()
        ph_layout = QVBoxLayout(tab_phones)
        self.tbl_phones = QTableWidget()
        self.tbl_phones.setColumnCount(3)
        self.tbl_phones.setHorizontalHeaderLabels(["شماره تماس", "عنوان/نسبت", "اصلی"])
        self.tbl_phones.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        ph_layout.addWidget(self.tbl_phones)
        self.load_phones()
        tabs.addTab(tab_phones, "شماره‌های تماس")

        # Tab 3: Class History (سابقه کلاس‌ها)
        tab_classes_hist = QWidget()
        ch_layout = QVBoxLayout(tab_classes_hist)
        self.tbl_classes_hist = QTableWidget()
        self.tbl_classes_hist.setColumnCount(6)
        self.tbl_classes_hist.setHorizontalHeaderLabels(["کد کلاس", "نام کلاس", "استاد", "تاریخ ثبت‌نام", "وضعیت ثبت‌نام", "عملیات"])
        for col in range(5):
            self.tbl_classes_hist.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.tbl_classes_hist.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        ch_layout.addWidget(self.tbl_classes_hist)
        self.load_classes_history()
        tabs.addTab(tab_classes_hist, "سابقه کلاس‌ها")

        # Tab 4: Categorized Attachments Table
        tab_att = QWidget()
        att_lay = QVBoxLayout(tab_att)

        h_att_btn = QHBoxLayout()
        btn_add_att = QPushButton("افزودن مدرک / پیوست جدید +")
        btn_add_att.setProperty("accent", "true")
        btn_add_att.clicked.connect(self.upload_attachment_dialog)
        h_att_btn.addWidget(btn_add_att)
        h_att_btn.addStretch()
        att_lay.addLayout(h_att_btn)

        self.tbl_att = QTableWidget()
        self.tbl_att.setColumnCount(5)
        self.tbl_att.setHorizontalHeaderLabels(["ردیف", "عنوان مدرک / نوع برگه", "نام فایل", "تاریخ بارگذاری", "عملیات"])
        for col in range(4):
            self.tbl_att.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.tbl_att.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tbl_att.doubleClicked.connect(self.open_selected_attachment_row)

        att_lay.addWidget(self.tbl_att)
        self.load_attachments()
        tabs.addTab(tab_att, "مدارک و پیوست‌ها")

        # Tab 5: Audit Trail
        tab_audit = QWidget()
        a_layout = QVBoxLayout(tab_audit)
        self.tbl_audit = QTableWidget()
        self.tbl_audit.setColumnCount(4)
        self.tbl_audit.setHorizontalHeaderLabels(["فیلد", "مقدار قبلی", "مقدار جدید", "تاریخ تغییر"])
        self.tbl_audit.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        a_layout.addWidget(self.tbl_audit)
        self.load_audit_trail()
        tabs.addTab(tab_audit, "سابقه تغییرات")

        layout.addWidget(tabs)

        btn_close = QPushButton("بستن")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignLeft)

    def load_financial_ledgers(self):
        all_records = self.payment_repo.list_payments(student_id=self.student_id, limit=500)

        pending_list = [p for p in all_records if p["status"] == "pending"]
        paid_list = [p for p in all_records if p["status"] == "paid"]

        # Populate Pending Debts Table
        self.tbl_pending.setRowCount(len(pending_list))
        for r, p in enumerate(pending_list):
            self.tbl_pending.setItem(r, 0, QTableWidgetItem(gregorian_to_shamsi(p["paid_date"])))
            desc = p.get("description") or p.get("payment_type_name", "بدهی آموزشی")
            self.tbl_pending.setItem(r, 1, QTableWidgetItem(desc))

            amt_item = QTableWidgetItem(format_currency(p["amount"]))
            amt_item.setForeground(Qt.red)
            self.tbl_pending.setItem(r, 2, amt_item)
            self.tbl_pending.setItem(r, 3, QTableWidgetItem("معوق / تسویه‌نشده"))

            btn_pnl = QWidget()
            btn_lay = QHBoxLayout(btn_pnl)
            btn_lay.setContentsMargins(0, 0, 0, 0)

            btn_disc = QPushButton("ثبت تخفیف")
            btn_disc.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold; border-radius: 4px; padding: 3px 8px;")
            btn_del = QPushButton("حذف این بدهی")
            btn_del.setStyleSheet("color: #C0392B; font-weight: bold;")

            p_id = p["id"]
            p_amt = p["amount"]
            btn_disc.clicked.connect(lambda _, id=p_id, a=p_amt: self.apply_debt_discount_dialog(id, a))
            btn_del.clicked.connect(lambda _, id=p_id: self.delete_debt(id))

            btn_lay.addWidget(btn_disc)
            btn_lay.addWidget(btn_del)
            self.tbl_pending.setCellWidget(r, 4, btn_pnl)

        # Populate Paid Payments Table with Print Invoice Button
        self.tbl_paid.setRowCount(len(paid_list))
        method_map = {"cash": "نقد", "pos": "کارت‌خوان", "card_to_card": "کارت به کارت"}
        for r, p in enumerate(paid_list):
            date_str = f"{gregorian_to_shamsi(p['paid_date'])} {p.get('paid_time', '')}".strip()
            self.tbl_paid.setItem(r, 0, QTableWidgetItem(date_str))

            exact_desc = p.get("description") or p.get("payment_type_name", "پرداختی وصول‌شده")
            self.tbl_paid.setItem(r, 1, QTableWidgetItem(exact_desc))

            m_text = method_map.get(p["method"], p["method"])
            if p.get("pos_device_label"):
                m_text += f" ({p['pos_device_label']})"
            elif p.get("card_destination_number"):
                m_text += f" ({p.get('card_destination_owner', '')} - {p['card_destination_number']})"
            self.tbl_paid.setItem(r, 2, QTableWidgetItem(m_text))

            amt_item = QTableWidgetItem(format_currency(p["amount"]))
            amt_item.setForeground(Qt.darkGreen)
            self.tbl_paid.setItem(r, 3, amt_item)

            track_code = p.get("bank_reference_number") or p.get("invoice_code") or p.get("unique_code") or "-"
            self.tbl_paid.setItem(r, 4, QTableWidgetItem(track_code))

            btn_print_inv = QPushButton("مشاهده / چاپ فاکتور")
            btn_print_inv.setProperty("accent", "true")
            pid = p["id"]
            btn_print_inv.clicked.connect(lambda _, id=pid: self.print_student_invoice(id))
            self.tbl_paid.setCellWidget(r, 5, btn_print_inv)

    def apply_debt_discount_dialog(self, debt_id: int, current_amount: float):
        dlg = QDialog(self)
        dlg.setWindowTitle("ثبت و اعمال تخفیف روی بدهی دانش‌آموز")
        dlg.resize(380, 200)
        form = QFormLayout(dlg)

        lbl_info = QLabel(f"مبلغ بدهی فعلی: {format_currency(current_amount)}")
        lbl_info.setStyleSheet("font-weight: bold; color: #2C3E50;")
        form.addRow(lbl_info)

        spn_disc_amt = QDoubleSpinBox()
        spn_disc_amt.setRange(0, current_amount)
        spn_disc_amt.setSingleStep(10000)
        spn_disc_amt.setDecimals(0)

        spn_disc_pct = QDoubleSpinBox()
        spn_disc_pct.setRange(0, 100)
        spn_disc_pct.setSingleStep(5)
        spn_disc_pct.setSuffix("%")

        form.addRow("مبلغ تخفیف ثابت (تومان):", spn_disc_amt)
        form.addRow("یا درصد تخفیف:", spn_disc_pct)

        btn_save = QPushButton("اعمال تخفیف")
        btn_save.setProperty("accent", "true")
        form.addRow(btn_save)

        def save():
            amt = spn_disc_amt.value()
            pct = spn_disc_pct.value()
            if amt <= 0 and pct <= 0:
                QMessageBox.warning(dlg, "خطا", "لطفاً مبلغ یا درصد تخفیف معتبر وارد کنید.")
                return

            self.payment_repo.apply_discount_to_debt(debt_id, discount_amount=amt, discount_percent=pct)
            QMessageBox.information(dlg, "موفقیت", "تخفیف با موفقیت روی این بدهی اعمال گردید و تراز دانش‌آموز بروز شد.")
            dlg.accept()
            self.load_financial_ledgers()

        btn_save.clicked.connect(save)
        dlg.exec()

    def print_student_invoice(self, payment_id: int):
        p_data = self.payment_repo.get_payment_by_id(payment_id)
        if not p_data:
            QMessageBox.warning(self, "خطا", "اطلاعات فاکتور یافت نشد.")
            return

        cfg_repo = ConfigRepository(self.db_path)
        currency_unit = cfg_repo.get_setting("currency_unit", "toman")
        numeral_fmt = cfg_repo.get_setting("numeral_format", "persian")
        page_size_setting = cfg_repo.get_setting("invoice_page_size", "A4")

        from reports.invoice_renderer import InvoiceTemplateRenderer
        from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize
        from PySide6.QtCore import QMarginsF

        renderer = InvoiceTemplateRenderer(
            currency_unit=currency_unit,
            use_persian_digits=(numeral_fmt == "persian"),
            page_size=page_size_setting
        )
        html_content = renderer.render_batch_html([p_data])

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

    def add_inventory_item_charge(self):
        b_repo = BookRepository(self.db_path)
        all_books = b_repo.list_books()
        if not all_books:
            QMessageBox.warning(self, "اطلاع", "هیچ کالایی در انبار یافت نشد.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("ثبت بدهی کتاب / کالا از انبار برای دانش‌آموز")
        dlg.resize(550, 400)
        v_box = QVBoxLayout(dlg)

        top_srch_h = QHBoxLayout()
        txt_srch = QLineEdit()
        txt_srch.setPlaceholderText("جستجو در کالاها و کتاب‌های انبار...")
        top_srch_h.addWidget(QLabel("جستجو:"))
        top_srch_h.addWidget(txt_srch)
        v_box.addLayout(top_srch_h)

        tbl_inv = QTableWidget()
        tbl_inv.setColumnCount(4)
        tbl_inv.setHorizontalHeaderLabels(["عنوان کالا / کتاب", "قیمت (تومان)", "موجودی انبار", "انتخاب"])
        tbl_inv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v_box.addWidget(tbl_inv)

        selected_bids = set()

        def load_inv(q=""):
            current_books = b_repo.list_books()
            filtered = [b for b in current_books if q.strip() in b["title"]] if q.strip() else current_books
            tbl_inv.setRowCount(len(filtered))

            for r, bk in enumerate(filtered):
                bid = bk["id"]
                tbl_inv.setItem(r, 0, QTableWidgetItem(bk["title"]))
                tbl_inv.setItem(r, 1, QTableWidgetItem(format_currency(bk["sale_price"])))
                tbl_inv.setItem(r, 2, QTableWidgetItem(to_persian_digits(bk["stock_quantity"])))

                chk = QCheckBox("انتخاب")
                if bid in selected_bids:
                    chk.setChecked(True)

                def make_toggle(book_id):
                    return lambda state: selected_bids.add(book_id) if state else selected_bids.discard(book_id)

                chk.toggled.connect(make_toggle(bid))

                chk_w = QWidget()
                c_lay = QHBoxLayout(chk_w)
                c_lay.addWidget(chk)
                c_lay.setAlignment(Qt.AlignCenter)
                c_lay.setContentsMargins(0, 0, 0, 0)
                tbl_inv.setCellWidget(r, 3, chk_w)

        txt_srch.textChanged.connect(load_inv)
        load_inv()

        btn_confirm = QPushButton("ثبت بدهی کالاهای انتخابی")
        btn_confirm.setProperty("accent", "true")
        v_box.addWidget(btn_confirm)

        def save():
            if not selected_bids:
                QMessageBox.warning(dlg, "خطا", "لطفاً حداقل یک کالا را انتخاب کنید.")
                return

            all_books_map = {b["id"]: b for b in b_repo.list_books()}
            chosen_items = [all_books_map[bid] for bid in selected_bids if bid in all_books_map]

            out_of_stock = [bk for bk in chosen_items if bk["stock_quantity"] <= 0]
            if out_of_stock:
                titles = " - ".join(bk["title"] for bk in out_of_stock)
                if QMessageBox.question(dlg, "هشدار اتمام موجودی", f"موجودی آیتم‌های زیر صفر یا منفی است:\n{titles}\n\nآیا مایلید بدهی ثبت شده و موجودی انبار منفی گردد؟") != QMessageBox.Yes:
                    return

            cfg_repo = ConfigRepository(self.db_path)
            ptypes = cfg_repo.list_payment_types()
            book_pt_id = 1
            for pt in ptypes:
                if "کتاب" in pt["name"]:
                    book_pt_id = pt["id"]
                    break

            for bk in chosen_items:
                consumed = b_repo.consume_stock_fifo(bk["id"], 1)
                total_cost = sum(item["quantity_taken"] * item["purchase_price"] for item in consumed)
                total_qty = sum(item["quantity_taken"] for item in consumed)
                unit_cost = (total_cost / total_qty) if total_qty > 0 else bk["purchase_price"]
                batch_id = consumed[0]["batch_id"] if (len(consumed) == 1 and consumed[0]["batch_id"] is not None) else None

                self.payment_repo.record_payment(
                    student_id=self.student_id,
                    payment_type_id=book_pt_id,
                    amount=bk["sale_price"],
                    method="cash",
                    description=f"کالا / کتاب انبار: {bk['title']}",
                    status="pending",
                    create_invoice=False,
                    book_id=bk["id"],
                    book_batch_id=batch_id,
                    book_unit_cost=unit_cost
                )

            QMessageBox.information(dlg, "موفقیت", "بدهی کالاهای انتخابی با موفقیت ثبت گردید و موجودی انبار کسر شد.")
            dlg.accept()
            self.load_financial_ledgers()

        btn_confirm.clicked.connect(save)
        dlg.exec()

    def add_private_class_charge(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("ثبت کلاس خصوصی با شهریه دلخواه")
        dlg.resize(400, 220)
        form = QFormLayout(dlg)

        txt_title = QLineEdit("کلاس خصوصی")
        spn_fee = QDoubleSpinBox()
        spn_fee.setRange(10000, 1000000000)
        spn_fee.setValue(500000)
        spn_fee.setSingleStep(50000)
        spn_fee.setDecimals(0)

        form.addRow("عنوان کلاس / خدمت:", txt_title)
        form.addRow("مبلغ شهریه (تومان):", spn_fee)

        btn_save = QPushButton("ثبت بدهی")
        btn_save.setProperty("accent", "true")
        form.addRow(btn_save)

        def save():
            title = txt_title.text().strip()
            fee = spn_fee.value()
            if not title or fee <= 0:
                QMessageBox.warning(dlg, "خطا", "لطفاً عنوان و مبلغ معتبر وارد کنید.")
                return

            cfg_repo = ConfigRepository(self.db_path)
            ptypes = cfg_repo.list_payment_types()
            pt_id = 1
            for pt in ptypes:
                if "کلاس" in pt["name"] or "شهریه" in pt["name"]:
                    pt_id = pt["id"]
                    break

            self.payment_repo.record_payment(
                student_id=self.student_id,
                payment_type_id=pt_id,
                amount=fee,
                method="cash",
                description=f"کلاس خصوصی: {title}",
                status="pending",
                create_invoice=False
            )
            QMessageBox.information(dlg, "موفقیت", "بدهی کلاس خصوصی با موفقیت به بدهی‌های معوق دانش‌آموز اضافه گردید.")
            dlg.accept()
            self.load_financial_ledgers()

        btn_save.clicked.connect(save)
        dlg.exec()

    def delete_debt(self, debt_id: int):
        if QMessageBox.question(self, "تأیید حذف بدهی", "آیا از حذف کامل این بدهی از حساب دانش‌آموز اطمینان دارید؟") == QMessageBox.Yes:
            self.payment_repo.delete_payment(debt_id)
            self.load_financial_ledgers()

    def export_student_ledger_excel(self):
        s = self.student_repo.get_by_id(self.student_id)
        fpath, _ = QFileDialog.getSaveFileName(self, "ذخیره تراز مالی دانش‌آموز", f"Taraz_{s['unique_code']}.xlsx", "Excel Files (*.xlsx)")
        if fpath:
            all_records = self.payment_repo.list_payments(student_id=self.student_id, limit=1000)
            headers = ["تاریخ", "شرح و بابت", "نوع ثبت", "روش پرداخت", "مبلغ (تومان)", "وضعیت", "کد پیگیری / فاکتور"]
            rows = []
            method_map = {"cash": "نقد", "pos": "کارت‌خوان", "card_to_card": "کارت به کارت"}
            for p in all_records:
                rows.append([
                    gregorian_to_shamsi(p.get("paid_date", "")),
                    p.get("description") or p.get("payment_type_name", ""),
                    "بدهی ثبت‌شده" if p.get("status") == "pending" else "پرداختی وصول‌شده",
                    method_map.get(p.get("method"), p.get("method")),
                    p.get("amount", 0.0),
                    "پرداخت‌شده" if p.get("status") == "paid" else "معوق / تسویه‌نشده",
                    p.get("bank_reference_number") or p.get("unique_code") or "-"
                ])
            ExcelExporter.export_table_to_excel(fpath, headers, rows, title=f"تراز مالی: {s['first_name']} {s['last_name']}")
            QMessageBox.information(self, "موفقیت", "فایل تراز مالی دانش‌آموز با موفقیت ایجاد شد.")

    def load_phones(self):
        phones = self.student_repo.get_phones(self.student_id)
        self.tbl_phones.setRowCount(len(phones))
        for row, p in enumerate(phones):
            self.tbl_phones.setItem(row, 0, QTableWidgetItem(to_persian_digits(p["phone_number"])))
            self.tbl_phones.setItem(row, 1, QTableWidgetItem(p.get("label", "")))
            self.tbl_phones.setItem(row, 2, QTableWidgetItem("بله" if p.get("is_primary") else "خیر"))

    def load_classes_history(self):
        from database.db import get_connection
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT ce.id as enrollment_id, ce.status as enrollment_status, c.code, c.name, c.teacher_name, ce.enrolled_at
               FROM class_enrollments ce
               JOIN classes c ON ce.class_id = c.id
               WHERE ce.student_id = ?
               ORDER BY ce.id DESC""",
            (self.student_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        status_map = {
            "active": "درحال یادگیری / فعال",
            "graduated": "فارغ‌التحصیل",
            "dropped_out": "حذف‌شده / انصرافی",
            "transferred_out": "منتقل‌شده"
        }

        self.tbl_classes_hist.setRowCount(len(rows))
        for row, r in enumerate(rows):
            self.tbl_classes_hist.setItem(row, 0, QTableWidgetItem(r["code"]))
            self.tbl_classes_hist.setItem(row, 1, QTableWidgetItem(r["name"]))
            self.tbl_classes_hist.setItem(row, 2, QTableWidgetItem(r["teacher_name"] or "-"))
            self.tbl_classes_hist.setItem(row, 3, QTableWidgetItem(gregorian_to_shamsi(r["enrolled_at"])))

            st_val = r["enrollment_status"]
            st_item = QTableWidgetItem(status_map.get(st_val, st_val))
            if st_val == "active":
                st_item.setForeground(Qt.blue)
            elif st_val == "graduated":
                st_item.setForeground(Qt.darkGreen)
            else:
                st_item.setForeground(Qt.red)
            self.tbl_classes_hist.setItem(row, 4, st_item)

            btn_edit_st = QPushButton("تغییر وضعیت")
            btn_edit_st.setProperty("accent", "true")
            eid = r["enrollment_id"]
            curr_st = st_val
            c_name = r["name"]
            btn_edit_st.clicked.connect(lambda _, id=eid, s=curr_st, cn=c_name: self.edit_enrollment_status_dialog(id, s, cn))
            self.tbl_classes_hist.setCellWidget(row, 5, btn_edit_st)

    def edit_enrollment_status_dialog(self, enrollment_id: int, current_status: str, class_name: str):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"تغییر وضعیت ثبت‌نام در کلاس '{class_name}'")
        dlg.resize(400, 180)
        form = QFormLayout(dlg)

        cmb_st = QComboBox()
        cmb_st.addItem("فعال / درحال یادگیری", "active")
        cmb_st.addItem("فارغ‌التحصیل", "graduated")
        cmb_st.addItem("حذف‌شده / انصرافی", "dropped_out")
        cmb_st.addItem("منتقل‌شده به کلاس دیگر", "transferred_out")

        idx = cmb_st.findData(current_status)
        if idx >= 0:
            cmb_st.setCurrentIndex(idx)

        form.addRow("وضعیت جدید این کلاس:", cmb_st)

        btn_save = QPushButton("ذخیره وضعیت جدید")
        btn_save.setProperty("accent", "true")
        form.addRow(btn_save)

        def save():
            new_st = cmb_st.currentData()
            try:
                self.class_repo.update_enrollment_status(enrollment_id, new_st)
                QMessageBox.information(dlg, "موفقیت", "وضعیت ثبت‌نام با موفقیت بروزرسانی شد.")
                dlg.accept()
                self.load_classes_history()
            except Exception as e:
                QMessageBox.critical(dlg, "خطا در ثبت وضعیت", f"خطا در بروزرسانی وضعیت:\n{e}")

        btn_save.clicked.connect(save)
        dlg.exec()

    def load_attachments(self):
        atts = self.attachment_repo.list_attachments(self.student_id)
        self.tbl_att.setRowCount(len(atts))

        for row, a in enumerate(atts):
            # Row index
            self.tbl_att.setItem(row, 0, QTableWidgetItem(to_persian_digits(row + 1)))

            # Document Category
            cat_text = a.get("category") or "سایر مدارک"
            self.tbl_att.setItem(row, 1, QTableWidgetItem(cat_text))

            # File name
            fname = os.path.basename(a["file_path"])
            self.tbl_att.setItem(row, 2, QTableWidgetItem(fname))

            # Upload Date
            self.tbl_att.setItem(row, 3, QTableWidgetItem(gregorian_to_shamsi(a["uploaded_at"])))

            # Actions panel: Open, Rename, Delete
            pnl = QWidget()
            lay = QHBoxLayout(pnl)
            lay.setContentsMargins(0, 0, 0, 0)

            btn_open = QPushButton("نمایش")
            btn_edit = QPushButton("ویرایش/تغییرنام")
            btn_del = QPushButton("حذف")
            btn_del.setStyleSheet("color: #C0392B; font-weight: bold;")

            att_id = a["id"]
            fpath = a["file_path"]
            cat = cat_text

            btn_open.clicked.connect(lambda _, fp=fpath: self.open_file_path(fp))
            btn_edit.clicked.connect(lambda _, id=att_id, c=cat, fp=fpath: self.edit_attachment_dialog(id, c, fp))
            btn_del.clicked.connect(lambda _, id=att_id: self.delete_attachment_action(id))

            lay.addWidget(btn_open)
            lay.addWidget(btn_edit)
            lay.addWidget(btn_del)
            self.tbl_att.setCellWidget(row, 4, pnl)

    def upload_attachment_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("بارگذاری مدرک و پیوست جدید")
        dlg.resize(450, 200)
        form = QFormLayout(dlg)

        cmb_cat = QComboBox()
        cmb_cat.addItem("۱. برگه اول شناسنامه", "برگه اول شناسنامه")
        cmb_cat.addItem("۲. تصویر دانش‌آموز", "تصویر دانش‌آموز")
        cmb_cat.addItem("۳. برگه ثبت‌نام", "برگه ثبت‌نام")
        cmb_cat.addItem("۴. برگه رضایت والدین", "برگه رضایت والدین")
        cmb_cat.addItem("۵. سایر مدارک", "سایر مدارک")

        txt_file = QLineEdit()
        txt_file.setReadOnly(True)
        btn_browse = QPushButton("انتخاب فایل...")

        h_file = QHBoxLayout()
        h_file.addWidget(txt_file, 3)
        h_file.addWidget(btn_browse, 1)

        def browse():
            fpath, _ = QFileDialog.getOpenFileName(dlg, "انتخاب تصویر یا مدرک", "", "All Files (*.*);;Images (*.png *.jpg *.jpeg *.bmp)")
            if fpath:
                txt_file.setText(fpath)

        btn_browse.clicked.connect(browse)

        form.addRow("عنوان / نوع مدرک:", cmb_cat)
        form.addRow("مسیر فایل:", h_file)

        btn_save = QPushButton("بارگذاری مدرک")
        btn_save.setProperty("accent", "true")
        form.addRow(btn_save)

        def save():
            fp = txt_file.text().strip()
            if not fp:
                QMessageBox.warning(dlg, "خطا", "لطفاً ابتدا فایل مدرک را انتخاب کنید.")
                return
            cat = cmb_cat.currentData()
            self.attachment_repo.add_attachment(self.student_id, fp, category=cat)
            QMessageBox.information(dlg, "موفقیت", "مدرک با موفقیت اضافه شد.")
            dlg.accept()
            self.load_attachments()

        btn_save.clicked.connect(save)
        dlg.exec()

    def edit_attachment_dialog(self, att_id: int, current_cat: str, current_path: str):
        dlg = QDialog(self)
        dlg.setWindowTitle("ویرایش عنوان و تغییر فایل مدرک")
        dlg.resize(450, 200)
        form = QFormLayout(dlg)

        cmb_cat = QComboBox()
        cmb_cat.addItem("۱. برگه اول شناسنامه", "برگه اول شناسنامه")
        cmb_cat.addItem("۲. تصویر دانش‌آموز", "تصویر دانش‌آموز")
        cmb_cat.addItem("۳. برگه ثبت‌نام", "برگه ثبت‌نام")
        cmb_cat.addItem("۴. برگه رضایت والدین", "برگه رضایت والدین")
        cmb_cat.addItem("۵. سایر مدارک", "سایر مدارک")

        idx = cmb_cat.findData(current_cat)
        if idx >= 0:
            cmb_cat.setCurrentIndex(idx)

        txt_file = QLineEdit(current_path)
        btn_browse = QPushButton("تغییر فایل...")

        h_file = QHBoxLayout()
        h_file.addWidget(txt_file, 3)
        h_file.addWidget(btn_browse, 1)

        def browse():
            fpath, _ = QFileDialog.getOpenFileName(dlg, "انتخاب فایل مدرک جدید", "", "All Files (*.*)")
            if fpath:
                txt_file.setText(fpath)

        btn_browse.clicked.connect(browse)

        form.addRow("عنوان مدرک:", cmb_cat)
        form.addRow("مسیر فایل:", h_file)

        btn_save = QPushButton("ذخیره تغییرات")
        btn_save.setProperty("accent", "true")
        form.addRow(btn_save)

        def save():
            fp = txt_file.text().strip()
            if not fp:
                return
            self.attachment_repo.update_attachment(att_id, cmb_cat.currentData(), fp)
            dlg.accept()
            self.load_attachments()

        btn_save.clicked.connect(save)
        dlg.exec()

    def delete_attachment_action(self, att_id: int):
        if QMessageBox.question(self, "تأیید حذف", "آیا از حذف این مدرک اطمینان دارید؟") == QMessageBox.Yes:
            self.attachment_repo.delete_attachment(att_id)
            self.load_attachments()

    def open_file_path(self, file_path: str):
        if file_path and os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            QMessageBox.warning(self, "خطا", "فایل مورد نظر در مسیر مربوطه یافت نشد.")

    def open_selected_attachment_row(self, index):
        row = index.row()
        atts = self.attachment_repo.list_attachments(self.student_id)
        if 0 <= row < len(atts):
            self.open_file_path(atts[row]["file_path"])

    def load_audit_trail(self):
        logs = self.audit_repo.get_logs_for_entity("student", self.student_id)
        self.tbl_audit.setRowCount(len(logs))
        for row, l in enumerate(logs):
            self.tbl_audit.setItem(row, 0, QTableWidgetItem(l["field_name"]))
            self.tbl_audit.setItem(row, 1, QTableWidgetItem(str(l.get("old_value", ""))))
            self.tbl_audit.setItem(row, 2, QTableWidgetItem(str(l.get("new_value", ""))))
            self.tbl_audit.setItem(row, 3, QTableWidgetItem(gregorian_to_shamsi(l["changed_at"])))


class StudentManagementWidget(QWidget):
    """Main Student Management View with Debt Column."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.student_repo = StudentRepository(db_path)
        self.term_repo = TermRepository(db_path)
        self.financial_engine = FinancialEngine(db_path)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("جستجو براساس نام، شماره تماس یا کد دانش‌آموزی...")
        self.txt_search.textChanged.connect(self.load_students)

        self.cmb_status_filter = QComboBox()
        self.cmb_status_filter.addItem("همه وضعيتها", "")
        self.cmb_status_filter.addItem("فعال", "active")
        self.cmb_status_filter.addItem("غیرفعال", "inactive")
        self.cmb_status_filter.addItem("انصرافی", "dropped_out")
        self.cmb_status_filter.addItem("فارغ‌التحصیل", "graduated")
        self.cmb_status_filter.currentIndexChanged.connect(self.load_students)

        self.btn_refresh = QPushButton("بروزرسانی لیست")
        self.btn_refresh.clicked.connect(self.load_students)

        self.btn_add = QPushButton(" دانش‌آموز جدید +")
        self.btn_add.setProperty("accent", "true")
        self.btn_add.clicked.connect(self.add_student)

        top_bar.addWidget(QLabel("جستجو:"))
        top_bar.addWidget(self.txt_search, 2)
        top_bar.addWidget(QLabel("فیلتر وضعیت:"))
        top_bar.addWidget(self.cmb_status_filter, 1)
        top_bar.addWidget(self.btn_refresh)
        top_bar.addWidget(self.btn_add)

        layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["کد", "نام و نام خانوادگی", "نام پدر", "شماره تماس اصلی", "بدهی معوق", "وضعیت", "عملیات"])
        for col in range(6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.view_profile)

        layout.addWidget(self.table)
        self.load_students()

    def load_students(self):
        q = to_latin_digits(self.txt_search.text())
        st = self.cmb_status_filter.currentData()

        students = self.student_repo.search_students(query=q, status=st)
        self.table.setRowCount(len(students))

        status_map = {
            "active": "فعال",
            "inactive": "غیرفعال",
            "dropped_out": "انصرافی",
            "graduated": "فارغ‌التحصیل"
        }

        for row, s in enumerate(students):
            self.table.setItem(row, 0, QTableWidgetItem(s["unique_code"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"{s['first_name']} {s['last_name']}"))
            self.table.setItem(row, 2, QTableWidgetItem(s.get("father_name") or "-"))

            phone = s.get("primary_phone") or "-"
            self.table.setItem(row, 3, QTableWidgetItem(to_persian_digits(phone)))

            fin = self.financial_engine.get_student_financial_summary(s["id"])
            debt_amt = fin["total_pending_debt"]
            debt_item = QTableWidgetItem(format_currency(debt_amt))
            if debt_amt > 0:
                debt_item.setForeground(Qt.red)
            self.table.setItem(row, 4, debt_item)

            st_text = status_map.get(s["status"], s["status"])
            self.table.setItem(row, 5, QTableWidgetItem(st_text))

            btn_panel = QWidget()
            btn_lay = QHBoxLayout(btn_panel)
            btn_lay.setContentsMargins(2, 2, 2, 2)

            btn_edit = QPushButton("ویرایش")
            s_id = s["id"]
            btn_edit.clicked.connect(lambda _, id=s_id: self.edit_student(id))

            btn_prof = QPushButton("پروفایل / تراز")
            btn_prof.clicked.connect(lambda _, id=s_id: self.view_profile_by_id(id))

            btn_lay.addWidget(btn_edit)
            btn_lay.addWidget(btn_prof)

            self.table.setCellWidget(row, 6, btn_panel)

    def add_student(self):
        dlg = StudentDialog(self, db_path=self.db_path)
        if dlg.exec() == QDialog.Accepted:
            self.load_students()

    def edit_student(self, student_id):
        dlg = StudentDialog(self, db_path=self.db_path, student_id=student_id)
        if dlg.exec() == QDialog.Accepted:
            self.load_students()

    def view_profile_by_id(self, student_id):
        dlg = StudentProfileDialog(student_id, db_path=self.db_path, parent=self)
        dlg.exec()

    def view_profile(self, index):
        row = index.row()
        code_item = self.table.item(row, 0)
        if code_item:
            code = code_item.text()
            st_list = self.student_repo.search_students(query=code)
            if st_list:
                self.view_profile_by_id(st_list[0]["id"])


class StudentPickerDialog(QDialog):
    """Search Picker Dialog showing details (Name, Code, Father Name, Phone) before selecting student."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.student_repo = StudentRepository(db_path)
        self.selected_student = None

        self.setWindowTitle("جستجو و انتخاب دقیق دانش‌آموز")
        self.resize(600, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_h = QHBoxLayout()
        self.txt_q = QLineEdit()
        self.txt_q.setPlaceholderText("جستجوی نام، کد یا شماره تماس...")
        self.txt_q.textChanged.connect(self.search)

        top_h.addWidget(QLabel("عبارت جستجو:"))
        top_h.addWidget(self.txt_q)
        layout.addLayout(top_h)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(4)
        self.tbl.setHorizontalHeaderLabels(["کد", "نام و نام خانوادگی", "نام پدر", "شماره تماس"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.doubleClicked.connect(self.confirm_selection)
        layout.addWidget(self.tbl)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("انتخاب دانش‌آموز")
        btn_ok.setProperty("accent", "true")
        btn_ok.clicked.connect(self.confirm_selection)
        btn_cancel = QPushButton("انصراف")
        btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

        self.search()

    def search(self):
        q = to_latin_digits(self.txt_q.text().strip())
        results = self.student_repo.search_students(query=q)
        self.tbl.setRowCount(len(results))
        for r, s in enumerate(results):
            self.tbl.setItem(r, 0, QTableWidgetItem(s["unique_code"]))
            self.tbl.setItem(r, 1, QTableWidgetItem(f"{s['first_name']} {s['last_name']}"))
            self.tbl.setItem(r, 2, QTableWidgetItem(s.get("father_name") or "-"))
            self.tbl.setItem(r, 3, QTableWidgetItem(to_persian_digits(s.get("primary_phone") or "-")))

            self.tbl.item(r, 0).setData(Qt.UserRole, s)

    def confirm_selection(self):
        curr_row = self.tbl.currentRow()
        if curr_row >= 0:
            item = self.tbl.item(curr_row, 0)
            if item:
                self.selected_student = item.data(Qt.UserRole)
                self.accept()
        else:
            QMessageBox.warning(self, "خطا", "لطفاً یک دانش‌آموز را از لیست انتخاب کنید.")


class TermClassManagementWidget(QWidget):
    """Class and Inventory Management View with tuition, book and other fees."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.term_repo = TermRepository(db_path)
        self.class_repo = ClassRepository(db_path)
        self.student_repo = StudentRepository(db_path)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        self.btn_new_class = QPushButton("تشکیل کلاس جدید +")
        self.btn_new_class.setProperty("accent", "true")
        self.btn_new_class.clicked.connect(self.add_class)

        btn_refresh_classes = QPushButton("بروزرسانی لیست کلاس‌ها")
        btn_refresh_classes.clicked.connect(self.load_classes)

        top_bar.addWidget(self.btn_new_class)
        top_bar.addWidget(btn_refresh_classes)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        tabs = QTabWidget()

        # Tab 1: Class List
        self.tab_classes = QWidget()
        c_layout = QVBoxLayout(self.tab_classes)
        self.tbl_classes = QTableWidget()
        self.tbl_classes.setColumnCount(9)
        self.tbl_classes.setHorizontalHeaderLabels(["کد", "نام کلاس", "استاد", "وضعیت کلاس", "شهریه", "کتاب", "ظرفیت / ثبت‌نام", "مدیریت کلاس", "لیست"])
        for col in range(7):
            self.tbl_classes.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.tbl_classes.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.tbl_classes.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        c_layout.addWidget(self.tbl_classes)
        tabs.addTab(self.tab_classes, "مدیریت کلاس‌ها")

        # Tab 2: Book Inventory Management (مدیریت انبار کتاب)
        self.tab_books = QWidget()
        b_layout = QVBoxLayout(self.tab_books)

        b_top = QHBoxLayout()
        btn_add_book = QPushButton("تعریف کتاب جدید +")
        btn_add_book.setProperty("accent", "true")
        btn_add_book.clicked.connect(self.add_book_dialog)

        btn_restock_book = QPushButton("افزودن موجودی جدید (خرید تازه) +")
        btn_restock_book.setProperty("accent", "true")
        btn_restock_book.clicked.connect(lambda: self.restock_book_dialog())

        btn_ref_books = QPushButton("بروزرسانی انبار")
        btn_ref_books.clicked.connect(self.load_books)

        b_top.addWidget(btn_add_book)
        b_top.addWidget(btn_restock_book)
        b_top.addWidget(btn_ref_books)
        b_top.addStretch()
        b_layout.addLayout(b_top)

        self.tbl_books = QTableWidget()
        self.tbl_books.setColumnCount(5)
        self.tbl_books.setHorizontalHeaderLabels(["عنوان کتاب / کالا", "آخرین قیمت خرید", "قیمت فروش جاری", "موجودی انبار", "عملیات"])
        for col in range(4):
            self.tbl_books.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.tbl_books.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        b_layout.addWidget(self.tbl_books)
        tabs.addTab(self.tab_books, "انبار کتاب‌ها و کالاها")

        layout.addWidget(tabs)

        self.load_classes()
        self.load_books()

    def load_books(self):
        b_repo = BookRepository(self.db_path)
        books = b_repo.list_books()
        self.tbl_books.setRowCount(len(books))
        for r, b in enumerate(books):
            self.tbl_books.setItem(r, 0, QTableWidgetItem(b["title"]))
            self.tbl_books.setItem(r, 1, QTableWidgetItem(format_currency(b["purchase_price"])))
            self.tbl_books.setItem(r, 2, QTableWidgetItem(format_currency(b["sale_price"])))
            self.tbl_books.setItem(r, 3, QTableWidgetItem(to_persian_digits(b["stock_quantity"])))

            bid = b["id"]
            btn_pnl = QWidget()
            btn_lay = QHBoxLayout(btn_pnl)
            btn_lay.setContentsMargins(0, 0, 0, 0)

            btn_edit = QPushButton("ویرایش")
            btn_restock = QPushButton("+ خرید جدید")
            btn_batches = QPushButton("تاریخچه خریدها")

            btn_edit.clicked.connect(lambda _, id=bid: self.edit_book_dialog(id))
            btn_restock.clicked.connect(lambda _, id=bid: self.restock_book_dialog(book_id=id))
            btn_batches.clicked.connect(lambda _, id=bid: self.view_batches_dialog(id))

            btn_lay.addWidget(btn_edit)
            btn_lay.addWidget(btn_restock)
            btn_lay.addWidget(btn_batches)
            self.tbl_books.setCellWidget(r, 4, btn_pnl)

    def restock_book_dialog(self, book_id: Optional[int] = None):
        b_repo = BookRepository(self.db_path)
        all_books = b_repo.list_books()
        if not all_books:
            QMessageBox.warning(self, "خطا", "ابتدا باید یک کتاب در انبار تعریف کنید.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("ثبت موجودی جدید و خرید دسته‌ای کتاب (Batch Restock)")
        dlg.resize(450, 280)
        form = QFormLayout(dlg)

        cmb_book = QComboBox()
        for bk in all_books:
            cmb_book.addItem(f"{bk['title']} (موجودی فعلی: {bk['stock_quantity']})", bk["id"])

        if book_id:
            idx = cmb_book.findData(book_id)
            if idx >= 0:
                cmb_book.setCurrentIndex(idx)

        spn_qty = QDoubleSpinBox()
        spn_qty.setRange(1, 100000)
        spn_qty.setValue(50)
        spn_qty.setDecimals(0)

        spn_purchase = QDoubleSpinBox()
        spn_purchase.setRange(0, 100000000)
        spn_purchase.setSingleStep(5000)
        spn_purchase.setDecimals(0)

        spn_sale = QDoubleSpinBox()
        spn_sale.setRange(0, 100000000)
        spn_sale.setSingleStep(5000)
        spn_sale.setDecimals(0)

        curr_bid = cmb_book.currentData()
        curr_bk = b_repo.get_by_id(curr_bid) if curr_bid else None
        if curr_bk:
            spn_purchase.setValue(curr_bk["purchase_price"])
            spn_sale.setValue(curr_bk["sale_price"])

        def on_book_selected():
            bid = cmb_book.currentData()
            bk = b_repo.get_by_id(bid)
            if bk:
                spn_purchase.setValue(bk["purchase_price"])
                spn_sale.setValue(bk["sale_price"])

        cmb_book.currentIndexChanged.connect(on_book_selected)

        txt_pdate = QLineEdit(datetime.now().strftime("%Y-%m-%d"))

        form.addRow("انتخاب کتاب:", cmb_book)
        form.addRow("تعداد خریداری‌شده (موجودی جدید):", spn_qty)
        form.addRow("قیمت خرید این پارت (تومان):", spn_purchase)
        form.addRow("قیمت فروش به دانش‌آموز (تومان):", spn_sale)
        form.addRow("تاریخ خرید (YYYY-MM-DD):", txt_pdate)

        btn_save = QPushButton("ثبت موجودی جدید")
        btn_save.setProperty("accent", "true")
        form.addRow(btn_save)

        def save():
            bid = cmb_book.currentData()
            qty = int(spn_qty.value())
            p_price = spn_purchase.value()
            s_price = spn_sale.value()
            p_date = txt_pdate.text().strip() or datetime.now().strftime("%Y-%m-%d")

            if bid and qty > 0:
                b_repo.restock_book(bid, qty, p_price, s_price, purchase_date=p_date)
                QMessageBox.information(dlg, "موفقیت", "خرید جدید کتاب با موفقیت ثبت و به انبار اضافه شد.")
                dlg.accept()
                self.load_books()

        btn_save.clicked.connect(save)
        dlg.exec()

    def view_batches_dialog(self, book_id: int):
        b_repo = BookRepository(self.db_path)
        book = b_repo.get_by_id(book_id)
        if not book:
            return

        batches = b_repo.list_batches(book_id)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"تاریخچه خریدهای دسته‌ای (Batches): {book['title']}")
        dlg.resize(600, 350)
        vbox = QVBoxLayout(dlg)

        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["تاریخ خرید", "تعداد خریداری‌شده", "تعداد باقیمانده", "قیمت خرید", "قیمت فروش"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vbox.addWidget(tbl)

        tbl.setRowCount(len(batches))
        for r, b in enumerate(batches):
            tbl.setItem(r, 0, QTableWidgetItem(gregorian_to_shamsi(b["purchase_date"])))
            tbl.setItem(r, 1, QTableWidgetItem(to_persian_digits(b["quantity_purchased"])))
            tbl.setItem(r, 2, QTableWidgetItem(to_persian_digits(b["quantity_remaining"])))
            tbl.setItem(r, 3, QTableWidgetItem(format_currency(b["purchase_price"])))
            tbl.setItem(r, 4, QTableWidgetItem(format_currency(b["sale_price"])))

        btn_close = QPushButton("بستن")
        btn_close.clicked.connect(dlg.accept)
        vbox.addWidget(btn_close, alignment=Qt.AlignLeft)

        dlg.exec()

    def edit_book_dialog(self, book_id: int):
        b_repo = BookRepository(self.db_path)
        book = b_repo.get_by_id(book_id)
        if not book:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"ویرایش عنوان / اصلاح اطلاعات کتاب: {book['title']}")
        form = QFormLayout(dlg)

        txt_title = QLineEdit(book["title"])
        spn_purchase = QDoubleSpinBox()
        spn_purchase.setRange(0, 50000000)
        spn_purchase.setValue(book["purchase_price"])
        spn_purchase.setSingleStep(5000)
        spn_purchase.setDecimals(0)

        spn_sale = QDoubleSpinBox()
        spn_sale.setRange(0, 50000000)
        spn_sale.setValue(book["sale_price"])
        spn_sale.setSingleStep(5000)
        spn_sale.setDecimals(0)

        spn_stock = QDoubleSpinBox()
        spn_stock.setRange(-10000, 100000)
        spn_stock.setValue(book["stock_quantity"])
        spn_stock.setDecimals(0)

        form.addRow("عنوان کتاب:", txt_title)
        form.addRow("قیمت خرید جاری (تومان):", spn_purchase)
        form.addRow("قیمت فروش جاری (تومان):", spn_sale)
        form.addRow("موجودی انبار:", spn_stock)

        btn_save = QPushButton("ذخیره تغییرات")
        btn_save.setProperty("accent", "true")
        form.addRow(btn_save)

        def save():
            title = txt_title.text().strip()
            if title:
                new_stock = int(spn_stock.value())
                old_stock = book["stock_quantity"]
                if new_stock > old_stock:
                    diff = new_stock - old_stock
                    b_repo.restock_book(book_id, diff, spn_purchase.value(), spn_sale.value())
                    b_repo.update_book(book_id, title, spn_purchase.value(), spn_sale.value(), new_stock)
                else:
                    b_repo.update_book(book_id, title, spn_purchase.value(), spn_sale.value(), new_stock)
                dlg.accept()
                self.load_books()

        btn_save.clicked.connect(save)
        dlg.exec()

    def add_book_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("افزودن کتاب جدید به انبار")
        form = QFormLayout(dlg)

        txt_title = QLineEdit()
        spn_purchase = QDoubleSpinBox()
        spn_purchase.setRange(0, 50000000)
        spn_purchase.setSingleStep(5000)
        spn_purchase.setDecimals(0)

        spn_sale = QDoubleSpinBox()
        spn_sale.setRange(0, 50000000)
        spn_sale.setSingleStep(5000)
        spn_sale.setDecimals(0)

        spn_stock = QDoubleSpinBox()
        spn_stock.setRange(0, 100000)
        spn_stock.setValue(100)
        spn_stock.setDecimals(0)

        form.addRow("عنوان کتاب:", txt_title)
        form.addRow("قیمت خرید (تومان):", spn_purchase)
        form.addRow("قیمت فروش (تومان):", spn_sale)
        form.addRow("موجودی اولیه انبار:", spn_stock)

        btn_save = QPushButton("ذخیره کتاب")
        btn_save.setProperty("accent", "true")
        form.addRow(btn_save)

        def save():
            title = txt_title.text().strip()
            if title:
                b_repo = BookRepository(self.db_path)
                b_repo.add_book(title, spn_purchase.value(), spn_sale.value(), int(spn_stock.value()))
                dlg.accept()
                self.load_books()

        btn_save.clicked.connect(save)
        dlg.exec()

    def load_terms(self):
        terms = self.term_repo.list_terms()
        self.tbl_terms.setRowCount(len(terms))
        for r, t in enumerate(terms):
            self.tbl_terms.setItem(r, 0, QTableWidgetItem(t["name"]))
            self.tbl_terms.setItem(r, 1, QTableWidgetItem(gregorian_to_shamsi(t.get("start_date"))))
            self.tbl_terms.setItem(r, 2, QTableWidgetItem(gregorian_to_shamsi(t.get("end_date")) or "-"))

            st_text = "باز" if t["status"] == "open" else "بسته"
            self.tbl_terms.setItem(r, 3, QTableWidgetItem(st_text))

            btn_toggle = QPushButton("بستن ترم" if t["status"] == "open" else "باز کردن ترم")
            tid = t["id"]
            btn_toggle.clicked.connect(lambda _, id=tid: self.toggle_term(id))
            self.tbl_terms.setCellWidget(r, 4, btn_toggle)

    def toggle_term(self, term_id):
        self.term_repo.toggle_term_status(term_id)
        self.load_terms()

    def load_classes(self):
        classes = self.class_repo.list_classes()
        self.tbl_classes.setRowCount(len(classes))
        for r, c in enumerate(classes):
            self.tbl_classes.setItem(r, 0, QTableWidgetItem(c["code"]))
            self.tbl_classes.setItem(r, 1, QTableWidgetItem(c["name"]))
            self.tbl_classes.setItem(r, 2, QTableWidgetItem(c.get("teacher_name") or "-"))

            st_text = "درحال برگزاری" if c.get("status") == "active" else "بسته‌شده / خاتمه‌یافته"
            st_item = QTableWidgetItem(st_text)
            if c.get("status") == "active":
                st_item.setForeground(Qt.blue)
            else:
                st_item.setForeground(Qt.gray)
            self.tbl_classes.setItem(r, 3, st_item)

            self.tbl_classes.setItem(r, 4, QTableWidgetItem(format_currency(c.get("tuition_fee", 0))))
            self.tbl_classes.setItem(r, 5, QTableWidgetItem(format_currency(c.get("book_fee", 0))))

            cap_str = f"{c['enrolled_count']} / {c['capacity']}"
            self.tbl_classes.setItem(r, 6, QTableWidgetItem(to_persian_digits(cap_str)))

            # Management action buttons: Edit, Close/Open, Delete
            c_id = c["id"]
            btn_pnl = QWidget()
            btn_lay = QHBoxLayout(btn_pnl)
            btn_lay.setContentsMargins(0, 0, 0, 0)

            btn_edit = QPushButton("ویرایش")
            btn_toggle = QPushButton("بستن کلاس" if c.get("status") == "active" else "باز کردن")
            btn_del = QPushButton("حذف")
            btn_del.setStyleSheet("color: #C0392B; font-weight: bold;")

            btn_edit.clicked.connect(lambda _, id=c_id: self.edit_class_dialog(id))
            btn_toggle.clicked.connect(lambda _, id=c_id: self.toggle_class_status(id))
            btn_del.clicked.connect(lambda _, id=c_id: self.delete_class_dialog(id))

            btn_lay.addWidget(btn_edit)
            btn_lay.addWidget(btn_toggle)
            btn_lay.addWidget(btn_del)
            self.tbl_classes.setCellWidget(r, 7, btn_pnl)

            # Roster button
            btn_roster = QPushButton("لیست دانش‌آموزان")
            btn_roster.clicked.connect(lambda _, id=c_id: self.open_roster(id))
            self.tbl_classes.setCellWidget(r, 8, btn_roster)

    def toggle_class_status(self, class_id: int):
        self.class_repo.toggle_class_status(class_id)
        self.load_classes()

    def delete_class_dialog(self, class_id: int):
        cls = self.class_repo.get_by_id(class_id)
        if not cls:
            return
        if QMessageBox.question(self, "تأیید حذف کلاس", f"آیا از حذف کامل کلاس '{cls['name']}' اطمینان دارید؟") == QMessageBox.Yes:
            self.class_repo.delete_class(class_id)
            self.load_classes()

    def add_term(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("افزودن ترم جدید")
        layout = QFormLayout(dlg)
        txt_name = QLineEdit()
        txt_start_date = QLineEdit()
        txt_start_date.setPlaceholderText("مثال: 1403/01/15 (پیش‌فرض امروز)")

        layout.addRow("نام ترم:", txt_name)
        layout.addRow("تاریخ شروع ترم:", txt_start_date)
        btn = QPushButton("ذخیره ترم")
        layout.addRow(btn)

        def save():
            if txt_name.text().strip():
                s_date = txt_start_date.text().strip()
                self.term_repo.create_term(txt_name.text().strip(), start_date=s_date)
                dlg.accept()
                self.load_terms()

        btn.clicked.connect(save)
        dlg.exec()

    def edit_class_dialog(self, class_id: int):
        cls = self.class_repo.get_by_id(class_id)
        if not cls:
            return

        terms = self.term_repo.list_terms()
        if not terms:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"ویرایش کلاس: {cls['name']} ({cls['code']})")
        dlg.setWindowState(dlg.windowState() | Qt.WindowMaximized)
        layout = QVBoxLayout(dlg)

        form = QFormLayout()
        txt_code = QLineEdit(cls["code"])
        txt_name = QLineEdit(cls["name"])
        txt_teacher = QLineEdit(cls.get("teacher_name") or "")

        cmb_term = QComboBox()
        for t in terms:
            cmb_term.addItem(t["name"], t["id"])
        idx_t = cmb_term.findData(cls["term_id"])
        if idx_t >= 0:
            cmb_term.setCurrentIndex(idx_t)

        spn_tuition = QDoubleSpinBox()
        spn_tuition.setRange(0, 100000000)
        spn_tuition.setValue(cls.get("tuition_fee", 0))
        spn_tuition.setSingleStep(50000)
        spn_tuition.setDecimals(0)

        txt_cap = QLineEdit(str(cls.get("capacity", 30)))

        form.addRow("کد کلاس:", txt_code)
        form.addRow("نام کلاس:", txt_name)
        form.addRow("استاد:", txt_teacher)
        form.addRow("ترم مربوطه:", cmb_term)
        form.addRow("مبلغ شهریه ثابت (تومان):", spn_tuition)
        form.addRow("ظرفیت:", txt_cap)
        layout.addLayout(form)

        # Multi-book selection table with search filter
        b_hdr_lay = QHBoxLayout()
        lbl_b = QLabel("مدیریت کتاب‌های اختصاص‌یافته از انبار به این کلاس:")
        lbl_b.setStyleSheet("font-weight: bold; margin-top: 5px;")

        txt_book_srch = QLineEdit()
        txt_book_srch.setPlaceholderText("جستجو در کتاب‌ها و وسایل انبار...")

        b_hdr_lay.addWidget(lbl_b, 2)
        b_hdr_lay.addWidget(txt_book_srch, 2)
        layout.addLayout(b_hdr_lay)

        tbl_books_sel = QTableWidget()
        tbl_books_sel.setColumnCount(3)
        tbl_books_sel.setHorizontalHeaderLabels(["عنوان کتاب", "قیمت فروش (تومان)", "موجود در کلاس"])
        tbl_books_sel.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        b_repo = BookRepository(self.db_path)
        existing_class_books = self.class_repo.get_class_books(class_id)
        selected_class_book_ids = {b["id"] for b in existing_class_books}

        def load_class_books_tbl(q=""):
            tbl_books_sel.setRowCount(0)
            current_bks = b_repo.list_books()
            filtered_bks = [bk for bk in current_bks if q.strip() in bk["title"]] if q.strip() else current_bks
            tbl_books_sel.setRowCount(len(filtered_bks))

            for r, bk in enumerate(filtered_bks):
                tbl_books_sel.setItem(r, 0, QTableWidgetItem(bk["title"]))
                tbl_books_sel.setItem(r, 1, QTableWidgetItem(format_currency(bk["sale_price"])))

                bid = bk["id"]
                chk = QCheckBox("افزودن")
                if bid in selected_class_book_ids:
                    chk.setChecked(True)

                def make_class_book_handler(book_id):
                    return lambda state: selected_class_book_ids.add(book_id) if state else selected_class_book_ids.discard(book_id)

                chk.toggled.connect(make_class_book_handler(bid))

                chk_widget = QWidget()
                chk_lay = QHBoxLayout(chk_widget)
                chk_lay.addWidget(chk)
                chk_lay.setAlignment(Qt.AlignCenter)
                chk_lay.setContentsMargins(0, 0, 0, 0)
                tbl_books_sel.setCellWidget(r, 2, chk_widget)

        txt_book_srch.textChanged.connect(load_class_books_tbl)
        load_class_books_tbl()

        layout.addWidget(tbl_books_sel)

        form_other = QFormLayout()
        spn_other = QDoubleSpinBox()
        spn_other.setRange(0, 50000000)
        spn_other.setValue(cls.get("other_fee", 0))
        spn_other.setDecimals(0)
        txt_other_title = QLineEdit(cls.get("other_fee_title") or "هزینه جانبی")

        form_other.addRow("عنوان سایر هزینه‌ها:", txt_other_title)
        form_other.addRow("مبلغ سایر هزینه‌ها (تومان):", spn_other)
        layout.addLayout(form_other)

        btn = QPushButton("ذخیره تغییرات کلاس")
        btn.setProperty("accent", "true")
        layout.addWidget(btn)

        def save():
            code = txt_code.text().strip()
            name = txt_name.text().strip()
            if code and name:
                try:
                    cap = int(to_latin_digits(txt_cap.text()))
                except ValueError:
                    cap = 30

                all_books_map = {b["id"]: b for b in b_repo.list_books()}
                selected_books = [all_books_map[bid] for bid in selected_class_book_ids if bid in all_books_map]
                total_book_fee = sum(bk["sale_price"] for bk in selected_books)

                self.class_repo.update_class(
                    class_id=class_id, code=code, name=name,
                    teacher_name=txt_teacher.text().strip(),
                    capacity=cap, start_date=cls.get("start_date", ""),
                    status=cls.get("status", "active"),
                    tuition_fee=spn_tuition.value(), book_fee=total_book_fee,
                    other_fee=spn_other.value(), other_fee_title=txt_other_title.text().strip(),
                    book_ids=list(selected_class_book_ids)
                )
                dlg.accept()
                self.load_classes()

        btn.clicked.connect(save)
        dlg.exec()

    def add_class(self):
        terms = self.term_repo.list_terms()
        if not terms:
            term_id = self.term_repo.create_term("ترم جاری 1403", status="open")
        else:
            term_id = terms[0]["id"]

        dlg = QDialog(self)
        dlg.setWindowTitle("تشکیل کلاس جدید با انتخاب کتاب‌های مربوطه از انبار")
        dlg.setWindowState(dlg.windowState() | Qt.WindowMaximized)
        layout = QVBoxLayout(dlg)

        form = QFormLayout()
        txt_code = QLineEdit()
        txt_name = QLineEdit()
        txt_teacher = QLineEdit()

        spn_tuition = QDoubleSpinBox()
        spn_tuition.setRange(0, 100000000)
        spn_tuition.setSingleStep(50000)
        spn_tuition.setDecimals(0)

        txt_cap = QLineEdit("30")

        form.addRow("کد کلاس:", txt_code)
        form.addRow("نام کلاس:", txt_name)
        form.addRow("استاد:", txt_teacher)
        form.addRow("مبلغ شهریه ثابت (تومان):", spn_tuition)
        form.addRow("ظرفیت:", txt_cap)
        layout.addLayout(form)

        # Multi-book selection table with search filter
        b_hdr_lay = QHBoxLayout()
        lbl_b = QLabel("انتخاب کتاب‌ها / وسایل آموزشی از انبار برای این کلاس:")
        lbl_b.setStyleSheet("font-weight: bold; margin-top: 5px;")

        txt_book_srch = QLineEdit()
        txt_book_srch.setPlaceholderText("جستجو در کتاب‌ها و وسایل انبار...")

        b_hdr_lay.addWidget(lbl_b, 2)
        b_hdr_lay.addWidget(txt_book_srch, 2)
        layout.addLayout(b_hdr_lay)

        tbl_books_sel = QTableWidget()
        tbl_books_sel.setColumnCount(3)
        tbl_books_sel.setHorizontalHeaderLabels(["عنوان کتاب", "قیمت فروش (تومان)", "موجود در کلاس"])
        tbl_books_sel.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        b_repo = BookRepository(self.db_path)
        selected_class_book_ids = set()

        def load_class_books_tbl(q=""):
            tbl_books_sel.setRowCount(0)
            current_bks = b_repo.list_books()
            filtered_bks = [bk for bk in current_bks if q.strip() in bk["title"]] if q.strip() else current_bks
            tbl_books_sel.setRowCount(len(filtered_bks))

            for r, bk in enumerate(filtered_bks):
                tbl_books_sel.setItem(r, 0, QTableWidgetItem(bk["title"]))
                tbl_books_sel.setItem(r, 1, QTableWidgetItem(format_currency(bk["sale_price"])))

                bid = bk["id"]
                chk = QCheckBox("افزودن")
                if bid in selected_class_book_ids:
                    chk.setChecked(True)

                def make_class_book_handler(book_id):
                    return lambda state: selected_class_book_ids.add(book_id) if state else selected_class_book_ids.discard(book_id)

                chk.toggled.connect(make_class_book_handler(bid))

                chk_widget = QWidget()
                chk_lay = QHBoxLayout(chk_widget)
                chk_lay.addWidget(chk)
                chk_lay.setAlignment(Qt.AlignCenter)
                chk_lay.setContentsMargins(0, 0, 0, 0)
                tbl_books_sel.setCellWidget(r, 2, chk_widget)

        txt_book_srch.textChanged.connect(load_class_books_tbl)
        load_class_books_tbl()

        layout.addWidget(tbl_books_sel)

        form_other = QFormLayout()
        spn_other = QDoubleSpinBox()
        spn_other.setRange(0, 50000000)
        spn_other.setDecimals(0)
        txt_other_title = QLineEdit("هزینه جانبی")

        form_other.addRow("عنوان سایر هزینه‌ها:", txt_other_title)
        form_other.addRow("مبلغ سایر هزینه‌ها (تومان):", spn_other)
        layout.addLayout(form_other)

        btn = QPushButton("ذخیره کلاس")
        btn.setProperty("accent", "true")
        layout.addWidget(btn)

        def save():
            code = txt_code.text().strip()
            name = txt_name.text().strip()
            if code and name:
                try:
                    cap = int(to_latin_digits(txt_cap.text()))
                except ValueError:
                    cap = 30

                all_books_map = {b["id"]: b for b in b_repo.list_books()}
                selected_books = [all_books_map[bid] for bid in selected_class_book_ids if bid in all_books_map]
                total_book_fee = sum(bk["sale_price"] for bk in selected_books)

                self.class_repo.create_class(
                    code=code, name=name, teacher_name=txt_teacher.text().strip(),
                    term_id=term_id, capacity=cap,
                    tuition_fee=spn_tuition.value(), book_fee=total_book_fee,
                    other_fee=spn_other.value(), other_fee_title=txt_other_title.text().strip(),
                    book_ids=list(selected_class_book_ids)
                )
                dlg.accept()
                self.load_classes()

        btn.clicked.connect(save)
        dlg.exec()

    def open_roster(self, class_id):
        cls = self.class_repo.get_by_id(class_id)
        if not cls:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"لیست کلاس: {cls['name']} ({cls['code']})")
        dlg.resize(750, 450)
        vbox = QVBoxLayout(dlg)

        top_h = QHBoxLayout()
        btn_enroll = QPushButton("جستجو و افزودن دانش‌آموز به کلاس +")
        btn_enroll.setProperty("accent", "true")

        top_h.addWidget(btn_enroll)
        top_h.addStretch()
        vbox.addLayout(top_h)

        tbl = QTableWidget()
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(["کد دانش‌آموزی", "نام و نام خانوادگی", "شماره تماس", "وضعیت ثبت‌نام", "عملیات"])
        for col in range(3):
            tbl.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        vbox.addWidget(tbl)

        def refresh_roster():
            roster = self.class_repo.get_class_roster(class_id)
            tbl.setRowCount(len(roster))
            for row, s in enumerate(roster):
                tbl.setItem(row, 0, QTableWidgetItem(s["unique_code"]))
                tbl.setItem(row, 1, QTableWidgetItem(f"{s['first_name']} {s['last_name']}"))
                tbl.setItem(row, 2, QTableWidgetItem(to_persian_digits(s.get("primary_phone") or "-")))

                # Enrollment status combo box
                cmb_st = QComboBox()
                cmb_st.addItem("فعال / درحال یادگیری", "active")
                cmb_st.addItem("فارغ‌التحصیل", "graduated")
                cmb_st.addItem("حذف‌شده / انصرافی", "dropped_out")
                cmb_st.addItem("منتقل‌شده", "transferred_out")

                curr_status = s.get("enrollment_status", "active")
                idx = cmb_st.findData(curr_status)

                eid = s.get("enrollment_id")

                def make_status_handler(enroll_id, combo_widget):
                    def on_status_changed(index):
                        new_st = combo_widget.itemData(index)
                        if enroll_id and new_st:
                            try:
                                self.class_repo.update_enrollment_status(enroll_id, new_st)
                            except Exception as e:
                                QMessageBox.critical(dlg, "خطا در بروزرسانی وضعیت", f"امکان ذخیره وضعیت وجود ندارد:\n{e}")
                    return on_status_changed

                if idx >= 0:
                    cmb_st.setCurrentIndex(idx)

                cmb_st.currentIndexChanged.connect(make_status_handler(eid, cmb_st))
                tbl.setCellWidget(row, 3, cmb_st)

                btn_pnl = QWidget()
                btn_lay = QHBoxLayout(btn_pnl)
                btn_lay.setContentsMargins(0, 0, 0, 0)

                btn_rem = QPushButton("حذف از این کلاس")
                btn_rem.setStyleSheet("color: #C0392B; font-weight: bold;")
                s_id = s["id"]
                btn_rem.clicked.connect(lambda _, id=s_id: remove_st(id))

                btn_lay.addWidget(btn_rem)
                tbl.setCellWidget(row, 4, btn_pnl)

        def enroll_st():
            picker = StudentPickerDialog(db_path=self.db_path, parent=dlg)
            if picker.exec() == QDialog.Accepted and picker.selected_student:
                st = picker.selected_student
                current_roster = self.class_repo.get_class_roster(class_id)
                if len(current_roster) >= cls["capacity"]:
                    QMessageBox.warning(dlg, "تکمیل ظرفیت", "ظرفیت کلاس تکمیل شده است!")
                    return

                # Display enrollment inventory dialog with class-assigned books pre-checked and clearly labeled
                b_repo = BookRepository(self.db_path)
                class_assigned_books = self.class_repo.get_class_books(class_id)
                class_assigned_book_ids = {cb["id"] for cb in class_assigned_books}

                opt_dlg = QDialog(dlg)
                opt_dlg.setWindowTitle(f"انتخاب کتاب‌ها و وسایل انبار برای ثبت‌نام {st['first_name']} {st['last_name']}")
                opt_dlg.resize(620, 480)
                v_opt = QVBoxLayout(opt_dlg)

                top_srch_h = QHBoxLayout()
                txt_srch = QLineEdit()
                txt_srch.setPlaceholderText("جستجو در وسایل و کتاب‌های انبار...")

                btn_ref_inv = QPushButton("بروزرسانی انبار")
                top_srch_h.addWidget(txt_srch, 3)
                top_srch_h.addWidget(btn_ref_inv, 1)
                v_opt.addLayout(top_srch_h)

                tbl_inv = QTableWidget()
                tbl_inv.setColumnCount(5)
                tbl_inv.setHorizontalHeaderLabels(["عنوان وسیله / کتاب", "نوع اختصاص", "قیمت (تومان)", "موجودی انبار", "تحویل به دانش‌آموز"])
                tbl_inv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                v_opt.addWidget(tbl_inv)

                # Pre-check all class-assigned books
                selected_book_ids = set(class_assigned_book_ids)

                def load_inv_tbl(q=""):
                    current_books = b_repo.list_books()
                    filtered = [b for b in current_books if q.strip() in b["title"]] if q.strip() else current_books
                    tbl_inv.setRowCount(len(filtered))

                    for r, bk in enumerate(filtered):
                        bid = bk["id"]
                        tbl_inv.setItem(r, 0, QTableWidgetItem(bk["title"]))

                        is_class_book = bid in class_assigned_book_ids
                        tag_text = "اختصاص‌یافته به کلاس" if is_class_book else "سایر موارد انبار"
                        tag_item = QTableWidgetItem(tag_text)
                        if is_class_book:
                            tag_item.setForeground(Qt.blue)
                        tbl_inv.setItem(r, 1, tag_item)

                        tbl_inv.setItem(r, 2, QTableWidgetItem(format_currency(bk["sale_price"])))
                        tbl_inv.setItem(r, 3, QTableWidgetItem(to_persian_digits(bk["stock_quantity"])))

                        chk = QCheckBox("تحویل دادن")
                        if bid in selected_book_ids:
                            chk.setChecked(True)

                        def make_toggle_handler(book_id):
                            return lambda state: selected_book_ids.add(book_id) if state else selected_book_ids.discard(book_id)

                        chk.toggled.connect(make_toggle_handler(bid))

                        chk_w = QWidget()
                        c_lay = QHBoxLayout(chk_w)
                        c_lay.addWidget(chk)
                        c_lay.setAlignment(Qt.AlignCenter)
                        c_lay.setContentsMargins(0, 0, 0, 0)
                        tbl_inv.setCellWidget(r, 4, chk_w)

                txt_srch.textChanged.connect(load_inv_tbl)
                btn_ref_inv.clicked.connect(lambda: load_inv_tbl(txt_srch.text()))
                load_inv_tbl()

                btn_confirm = QPushButton("تأیید و نهایی‌سازی ثبت‌نام دانش‌آموز")
                btn_confirm.setProperty("accent", "true")
                v_opt.addWidget(btn_confirm)

                def confirm_enroll_and_extra():
                    all_books_map = {b["id"]: b for b in b_repo.list_books()}
                    chosen_items = [all_books_map[bid] for bid in selected_book_ids if bid in all_books_map]

                    # Check out-of-stock items and prompt confirmation
                    out_of_stock = [bk for bk in chosen_items if bk["stock_quantity"] <= 0]
                    if out_of_stock:
                        titles = " - ".join(bk["title"] for bk in out_of_stock)
                        if QMessageBox.question(opt_dlg, "هشدار اتمام موجودی انبار", f"موجودی آیتم‌های زیر در انبار صفر یا منفی است:\n{titles}\n\nآیا مایلید دانش‌آموز ثبت‌نام شده و موجودی انبار منفی گردد؟") != QMessageBox.Yes:
                            return

                    # Perform Enrollment passing selected_book_ids and handle active class constraint
                    try:
                        self.class_repo.add_enrollment(class_id, st["id"], selected_book_ids=list(selected_book_ids))
                    except ValueError as err:
                        QMessageBox.warning(opt_dlg, "خطای ثبت‌نام همزمان در دو کلاس", str(err))
                        return

                    QMessageBox.information(opt_dlg, "موفقیت", "دانش‌آموز با موفقیت در کلاس ثبت‌نام گردید و کالا/کتاب‌های انتخابی کسر شد.")
                    opt_dlg.accept()

                btn_confirm.clicked.connect(confirm_enroll_and_extra)
                opt_dlg.exec()

                refresh_roster()
                self.load_classes()


        def remove_st(student_id):
            if QMessageBox.question(dlg, "تأیید حذف", "آیا از حذف دانش‌آموز از این کلاس اطمینان دارید؟ (بدهی‌های قبلی در حساب دانش‌آموز باقی می‌ماند)") == QMessageBox.Yes:
                self.class_repo.remove_enrollment(class_id, student_id)
                refresh_roster()
                self.load_classes()

        btn_enroll.clicked.connect(enroll_st)
        refresh_roster()
        dlg.exec()
