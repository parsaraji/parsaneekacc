import os
import shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QTextEdit,
    QDialog, QFormLayout, QMessageBox, QTabWidget, QFileDialog, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from database.repositories import StudentRepository, TermRepository, ClassRepository, AuditRepository, AttachmentRepository
from business_logic.formatters import to_persian_digits, to_latin_digits, gregorian_to_shamsi, format_currency
from business_logic.financial import FinancialEngine

class StudentDialog(QDialog):
    """Dialog for creating or editing a student."""
    def __init__(self, parent=None, db_path=None, student_id=None, user_id=None):
        super().__init__(parent)
        self.db_path = db_path
        self.student_id = student_id
        self.user_id = user_id
        self.student_repo = StudentRepository(db_path)

        self.setWindowTitle("ویرایش دانش‌آموز" if student_id else "افزودن دانش‌آموز جدید")
        self.resize(450, 400)
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

        self.txt_notes = QTextEdit()
        self.txt_notes.setMaximumHeight(80)

        form.addRow("نام:", self.txt_first_name)
        form.addRow("نام خانوادگی:", self.txt_last_name)
        form.addRow("نام پدر:", self.txt_father_name)
        form.addRow("شماره همراه اصلی:", self.txt_phone)
        form.addRow("آدرس:", self.txt_address)
        form.addRow("وضعیت:", self.cmb_status)
        form.addRow("یادداشت خصوصی:", self.txt_notes)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("ذخیره")
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

        self.accept()


class StudentProfileDialog(QDialog):
    """Full Student Profile Dialog with Tabs (Details, Phones, Terms, Financial, Attachments, Audit Log)."""
    def __init__(self, student_id, db_path=None, parent=None):
        super().__init__(parent)
        self.student_id = student_id
        self.db_path = db_path
        self.student_repo = StudentRepository(db_path)
        self.term_repo = TermRepository(db_path)
        self.financial_engine = FinancialEngine(db_path)
        self.audit_repo = AuditRepository(db_path)
        self.attachment_repo = AttachmentRepository(db_path)

        self.setWindowTitle("شناسنامه کامل دانش‌آموز")
        self.resize(700, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        student = self.student_repo.get_by_id(self.student_id)
        if not student:
            layout.addWidget(QLabel("دانش‌آموز یافت نشد."))
            return

        header = QLabel(f"پروفایل: {student['first_name']} {student['last_name']} ({student['unique_code']})")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2980B9;")
        layout.addWidget(header)

        tabs = QTabWidget()

        # Tab 1: Financial & Basic Summary
        tab_summary = QWidget()
        sum_layout = QVBoxLayout(tab_summary)
        fin = self.financial_engine.get_student_financial_summary(self.student_id)

        sum_layout.addWidget(QLabel(f"کد دانش‌آموزی: {student['unique_code']}"))
        sum_layout.addWidget(QLabel(f"نام پدر: {student.get('father_name', '-')}") )
        sum_layout.addWidget(QLabel(f"آدرس: {student.get('address', '-')}") )
        sum_layout.addWidget(QLabel(f"مجموع پرداختی: {format_currency(fin['total_paid'])}"))
        sum_layout.addWidget(QLabel(f"بدهی معوق / مانده: {format_currency(fin['total_pending_debt'])}"))
        sum_layout.addWidget(QLabel(f"مجموع تخفیفات: {format_currency(fin['total_discount'])}"))
        sum_layout.addStretch()
        tabs.addTab(tab_summary, "خلاصه مالی و مشخصات")

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

        # Tab 3: Terms History
        tab_terms = QWidget()
        t_layout = QVBoxLayout(tab_terms)
        self.tbl_terms = QTableWidget()
        self.tbl_terms.setColumnCount(2)
        self.tbl_terms.setHorizontalHeaderLabels(["عنوان ترم", "تاریخ ثبت‌نام"])
        self.tbl_terms.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t_layout.addWidget(self.tbl_terms)
        self.load_terms()
        tabs.addTab(tab_terms, "سابقه ترم‌ها")

        # Tab 4: Attachments
        tab_att = QWidget()
        att_lay = QVBoxLayout(tab_att)
        self.list_att = QListWidget()
        btn_add_att = QPushButton("افزودن پیوست جدید +")
        btn_add_att.clicked.connect(self.upload_attachment)
        att_lay.addWidget(self.list_att)
        att_lay.addWidget(btn_add_att)
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

    def load_phones(self):
        phones = self.student_repo.get_phones(self.student_id)
        self.tbl_phones.setRowCount(len(phones))
        for row, p in enumerate(phones):
            self.tbl_phones.setItem(row, 0, QTableWidgetItem(to_persian_digits(p["phone_number"])))
            self.tbl_phones.setItem(row, 1, QTableWidgetItem(p.get("label", "")))
            self.tbl_phones.setItem(row, 2, QTableWidgetItem("بله" if p.get("is_primary") else "خیر"))

    def load_terms(self):
        terms = self.term_repo.get_student_terms(self.student_id)
        self.tbl_terms.setRowCount(len(terms))
        for row, t in enumerate(terms):
            self.tbl_terms.setItem(row, 0, QTableWidgetItem(t["name"]))
            self.tbl_terms.setItem(row, 1, QTableWidgetItem(gregorian_to_shamsi(t["enrolled_at"])))

    def load_attachments(self):
        self.list_att.clear()
        atts = self.attachment_repo.list_attachments(self.student_id)
        for a in atts:
            fname = os.path.basename(a["file_path"])
            item = QListWidgetItem(f"{fname} ({gregorian_to_shamsi(a['uploaded_at'])})")
            self.list_att.addItem(item)

    def upload_attachment(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل پیوست", "", "All Files (*.*)")
        if fpath:
            self.attachment_repo.add_attachment(self.student_id, fpath)
            self.load_attachments()

    def load_audit_trail(self):
        logs = self.audit_repo.get_logs_for_entity("student", self.student_id)
        self.tbl_audit.setRowCount(len(logs))
        for row, l in enumerate(logs):
            self.tbl_audit.setItem(row, 0, QTableWidgetItem(l["field_name"]))
            self.tbl_audit.setItem(row, 1, QTableWidgetItem(str(l.get("old_value", ""))))
            self.tbl_audit.setItem(row, 2, QTableWidgetItem(str(l.get("new_value", ""))))
            self.tbl_audit.setItem(row, 3, QTableWidgetItem(gregorian_to_shamsi(l["changed_at"])))


class StudentManagementWidget(QWidget):
    """Main Student Management View."""
    def __init__(self, db_path=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.student_repo = StudentRepository(db_path)
        self.term_repo = TermRepository(db_path)
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

        self.btn_add = QPushButton(" دانش‌آموز جدید +")
        self.btn_add.setProperty("accent", "true")
        self.btn_add.clicked.connect(self.add_student)

        top_bar.addWidget(QLabel("جستجو:"))
        top_bar.addWidget(self.txt_search, 2)
        top_bar.addWidget(QLabel("فیلتر وضعیت:"))
        top_bar.addWidget(self.cmb_status_filter, 1)
        top_bar.addWidget(self.btn_add)

        layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["کد", "نام و نام خانوادگی", "نام پدر", "شماره تماس اصلی", "وضعیت", "عملیات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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

            st_text = status_map.get(s["status"], s["status"])
            self.table.setItem(row, 4, QTableWidgetItem(st_text))

            btn_panel = QWidget()
            btn_lay = QHBoxLayout(btn_panel)
            btn_lay.setContentsMargins(2, 2, 2, 2)

            btn_edit = QPushButton("ویرایش")
            s_id = s["id"]
            btn_edit.clicked.connect(lambda _, id=s_id: self.edit_student(id))

            btn_prof = QPushButton("پروفایل")
            btn_prof.clicked.connect(lambda _, id=s_id: self.view_profile_by_id(id))

            btn_lay.addWidget(btn_edit)
            btn_lay.addWidget(btn_prof)

            self.table.setCellWidget(row, 5, btn_panel)

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


class TermClassManagementWidget(QWidget):
    """Terms and Classes Management View."""
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
        self.btn_new_term = QPushButton("ترم جدید +")
        self.btn_new_term.clicked.connect(self.add_term)

        self.btn_new_class = QPushButton("کلاس جدید +")
        self.btn_new_class.setProperty("accent", "true")
        self.btn_new_class.clicked.connect(self.add_class)

        top_bar.addWidget(self.btn_new_term)
        top_bar.addWidget(self.btn_new_class)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        tabs = QTabWidget()

        self.tab_classes = QWidget()
        c_layout = QVBoxLayout(self.tab_classes)
        self.tbl_classes = QTableWidget()
        self.tbl_classes.setColumnCount(7)
        self.tbl_classes.setHorizontalHeaderLabels(["کد", "نام کلاس", "استاد", "ترم", "ظرفیت / ثبت‌نام", "وضعیت", "عملیات"])
        self.tbl_classes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        c_layout.addWidget(self.tbl_classes)
        tabs.addTab(self.tab_classes, "لیست کلاس‌ها")

        self.tab_terms = QWidget()
        t_layout = QVBoxLayout(self.tab_terms)
        self.tbl_terms = QTableWidget()
        self.tbl_terms.setColumnCount(4)
        self.tbl_terms.setHorizontalHeaderLabels(["نام ترم", "تاریخ شروع", "تاریخ پایان", "وضعیت"])
        self.tbl_terms.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t_layout.addWidget(self.tbl_terms)
        tabs.addTab(self.tab_terms, "لیست ترم‌ها")

        layout.addWidget(tabs)

        self.load_terms()
        self.load_classes()

    def load_terms(self):
        terms = self.term_repo.list_terms()
        self.tbl_terms.setRowCount(len(terms))
        for r, t in enumerate(terms):
            self.tbl_terms.setItem(r, 0, QTableWidgetItem(t["name"]))
            self.tbl_terms.setItem(r, 1, QTableWidgetItem(gregorian_to_shamsi(t.get("start_date"))))
            self.tbl_terms.setItem(r, 2, QTableWidgetItem(gregorian_to_shamsi(t.get("end_date"))))
            self.tbl_terms.setItem(r, 3, QTableWidgetItem("باز" if t["status"] == "open" else "بسته"))

    def load_classes(self):
        classes = self.class_repo.list_classes()
        self.tbl_classes.setRowCount(len(classes))
        for r, c in enumerate(classes):
            self.tbl_classes.setItem(r, 0, QTableWidgetItem(c["code"]))
            self.tbl_classes.setItem(r, 1, QTableWidgetItem(c["name"]))
            self.tbl_classes.setItem(r, 2, QTableWidgetItem(c.get("teacher_name") or "-"))
            self.tbl_classes.setItem(r, 3, QTableWidgetItem(c.get("term_name") or "-"))

            cap_str = f"{c['enrolled_count']} / {c['capacity']}"
            self.tbl_classes.setItem(r, 4, QTableWidgetItem(to_persian_digits(cap_str)))
            self.tbl_classes.setItem(r, 5, QTableWidgetItem("فعال" if c["status"] == "active" else "بسته"))

            btn_roster = QPushButton("لیست کلاس / انتقال")
            c_id = c["id"]
            btn_roster.clicked.connect(lambda _, id=c_id: self.open_roster(id))
            self.tbl_classes.setCellWidget(r, 6, btn_roster)

    def add_term(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("افزودن ترم جدید")
        layout = QFormLayout(dlg)
        txt_name = QLineEdit()
        layout.addRow("نام ترم:", txt_name)
        btn = QPushButton("ذخیره")
        layout.addRow(btn)

        def save():
            if txt_name.text().strip():
                self.term_repo.create_term(txt_name.text().strip())
                dlg.accept()
                self.load_terms()

        btn.clicked.connect(save)
        dlg.exec()

    def add_class(self):
        terms = self.term_repo.list_terms()
        if not terms:
            QMessageBox.warning(self, "خطا", "ابتدا یک ترم ایجاد کنید.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("افزودن کلاس جدید")
        layout = QFormLayout(dlg)

        txt_code = QLineEdit()
        txt_name = QLineEdit()
        txt_teacher = QLineEdit()
        cmb_term = QComboBox()
        for t in terms:
            cmb_term.addItem(t["name"], t["id"])

        txt_cap = QLineEdit("30")

        layout.addRow("کد کلاس:", txt_code)
        layout.addRow("نام کلاس:", txt_name)
        layout.addRow("استاد:", txt_teacher)
        layout.addRow("ترم مربوطه:", cmb_term)
        layout.addRow("ظرفیت:", txt_cap)

        btn = QPushButton("ذخیره")
        layout.addRow(btn)

        def save():
            code = txt_code.text().strip()
            name = txt_name.text().strip()
            if code and name:
                try:
                    cap = int(to_latin_digits(txt_cap.text()))
                except ValueError:
                    cap = 30
                self.class_repo.create_class(code, name, txt_teacher.text().strip(), cmb_term.currentData(), cap)
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
        dlg.resize(650, 450)
        vbox = QVBoxLayout(dlg)

        top_h = QHBoxLayout()
        txt_st_search = QLineEdit()
        txt_st_search.setPlaceholderText("جستجوی کد یا نام دانش‌آموز برای افزودن...")
        btn_enroll = QPushButton("افزودن به کلاس")
        btn_enroll.setProperty("accent", "true")

        top_h.addWidget(txt_st_search)
        top_h.addWidget(btn_enroll)
        vbox.addLayout(top_h)

        tbl = QTableWidget()
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["کد دانش‌آموزی", "نام و نام خانوادگی", "شماره تماس", "عملیات"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vbox.addWidget(tbl)

        def refresh_roster():
            roster = self.class_repo.get_class_roster(class_id)
            tbl.setRowCount(len(roster))
            for row, s in enumerate(roster):
                tbl.setItem(row, 0, QTableWidgetItem(s["unique_code"]))
                tbl.setItem(row, 1, QTableWidgetItem(f"{s['first_name']} {s['last_name']}"))
                tbl.setItem(row, 2, QTableWidgetItem(to_persian_digits(s.get("primary_phone") or "-")))

                btn_pnl = QWidget()
                btn_lay = QHBoxLayout(btn_pnl)
                btn_lay.setContentsMargins(0, 0, 0, 0)

                btn_transfer = QPushButton("انتقال")
                btn_rem = QPushButton("حذف")
                s_id = s["id"]
                btn_transfer.clicked.connect(lambda _, id=s_id: transfer_st(id))
                btn_rem.clicked.connect(lambda _, id=s_id: remove_st(id))

                btn_lay.addWidget(btn_transfer)
                btn_lay.addWidget(btn_rem)
                tbl.setCellWidget(row, 3, btn_pnl)

        def enroll_st():
            q = to_latin_digits(txt_st_search.text().strip())
            if not q:
                return
            st_list = self.student_repo.search_students(query=q)
            if not st_list:
                QMessageBox.warning(dlg, "خطا", "دانش‌آموزی یافت نشد.")
                return

            st = st_list[0]
            current_roster = self.class_repo.get_class_roster(class_id)
            if len(current_roster) >= cls["capacity"]:
                QMessageBox.warning(dlg, "تکمیل ظرفیت", "ظرفیت کلاس تکمیل شده است!")
                return

            self.class_repo.add_enrollment(class_id, st["id"])
            txt_st_search.clear()
            refresh_roster()
            self.load_classes()

        def transfer_st(student_id):
            all_cls = self.class_repo.list_classes(status="active")
            target_cls = [c for c in all_cls if c["id"] != class_id]
            if not target_cls:
                QMessageBox.warning(dlg, "خطا", "کلاس مقصد دیگری یافت نشد.")
                return

            tdlg = QDialog(dlg)
            tdlg.setWindowTitle("انتقال دانش‌آموز به کلاس جدید")
            tform = QFormLayout(tdlg)
            cmb_target = QComboBox()
            for c in target_cls:
                cmb_target.addItem(f"{c['name']} ({c['code']})", c["id"])

            tform.addRow("کلاس مقصد:", cmb_target)
            btn_ok = QPushButton("انتقال")
            tform.addRow(btn_ok)

            def do_transfer():
                to_cid = cmb_target.currentData()
                self.class_repo.transfer_student(class_id, to_cid, student_id)
                tdlg.accept()
                refresh_roster()
                self.load_classes()

            btn_ok.clicked.connect(do_transfer)
            tdlg.exec()

        def remove_st(student_id):
            self.class_repo.remove_enrollment(class_id, student_id)
            refresh_roster()
            self.load_classes()

        btn_enroll.clicked.connect(enroll_st)
        refresh_roster()
        dlg.exec()
