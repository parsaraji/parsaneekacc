import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QDialog, QFormLayout, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from database.db import init_db, DEFAULT_DB_PATH
from business_logic.auth import AuthService
from theme.theme import apply_theme
from ui.student_views import StudentManagementWidget, TermClassManagementWidget
from ui.payment_views import PaymentsAndInvoicingWidget
from ui.dashboard_and_settings import DashboardWidget, ExpensesWidget, ReportsWidget, SettingsWidget

class LoginDialog(QDialog):
    def __init__(self, auth_service: AuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.user = None

        self.setWindowTitle("ورود به سیستم - آموزشگاه پارسانیک")
        self.setFixedSize(380, 240)

        layout = QVBoxLayout(self)

        title = QLabel("سیستم مدیریت مالی و آموزشی پارسانیک")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2980B9; margin-bottom: 10px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("نام کاربری")
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("کلمه عبور")

        form.addRow("نام کاربری:", self.txt_username)
        form.addRow("کلمه عبور:", self.txt_password)
        layout.addLayout(form)

        btn_login = QPushButton("ورود")
        btn_login.setProperty("accent", "true")
        btn_login.clicked.connect(self.attempt_login)
        layout.addWidget(btn_login)

    def attempt_login(self):
        username = self.txt_username.text().strip()
        password = self.txt_password.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "خطا", "لطفاً نام کاربری و کلمه عبور را وارد کنید.")
            return

        user = self.auth_service.login(username, password)
        if user:
            self.user = user
            self.accept()
        else:
            QMessageBox.critical(self, "خطای ورود", "نام کاربری یا کلمه عبور اشتباه است.")


class MainWindow(QMainWindow):
    def __init__(self, db_path: str, user: dict, auth_service: AuthService):
        super().__init__()
        self.db_path = db_path
        self.user = user
        self.auth_service = auth_service

        self.setWindowTitle("سیستم جامع مدیریت دانش‌آموزان و حسابداری - آموزشگاه پارسانیک")
        self.resize(1100, 700)

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Right Navigation Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #E4E9F0;
                border-left: 1px solid #D0D7DE;
            }
            QPushButton {
                text-align: right;
                padding: 10px 14px;
                font-size: 11px;
                margin-bottom: 4px;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(5, 10, 5, 10)

        lbl_app = QLabel("آموزشگاه پارسانیک")
        lbl_app.setStyleSheet("font-size: 15px; font-weight: bold; color: #2980B9; margin-bottom: 15px;")
        lbl_app.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(lbl_app)

        # Nav buttons
        self.btn_dash = QPushButton("داشبورد")
        self.btn_students = QPushButton("دانش‌آموزان")
        self.btn_terms = QPushButton("کلاس‌ها و ترم‌ها")
        self.btn_payments = QPushButton("تراکنش‌ها و فاکتورها")
        self.btn_expenses = QPushButton("هزینه‌ها")
        self.btn_reports = QPushButton("گزارشات و اکسل")
        self.btn_settings = QPushButton("تنظیمات سیستم")

        self.btn_dash.clicked.connect(lambda: self.switch_view(0))
        self.btn_students.clicked.connect(lambda: self.switch_view(1))
        self.btn_terms.clicked.connect(lambda: self.switch_view(2))
        self.btn_payments.clicked.connect(lambda: self.switch_view(3))
        self.btn_expenses.clicked.connect(lambda: self.switch_view(4))
        self.btn_reports.clicked.connect(lambda: self.switch_view(5))
        self.btn_settings.clicked.connect(lambda: self.switch_view(6))

        sidebar_layout.addWidget(self.btn_dash)
        sidebar_layout.addWidget(self.btn_students)
        sidebar_layout.addWidget(self.btn_terms)
        sidebar_layout.addWidget(self.btn_payments)

        # Permission check for secretary
        if self.auth_service.can_view_full_financial_reports():
            sidebar_layout.addWidget(self.btn_expenses)
            sidebar_layout.addWidget(self.btn_reports)

        if self.auth_service.can_manage_users():
            sidebar_layout.addWidget(self.btn_settings)

        sidebar_layout.addStretch()

        # User Profile Footer in Sidebar
        lbl_user = QLabel(f"کاربر: {self.user['full_name']}\nنقش: {self.user['role']}")
        lbl_user.setStyleSheet("font-size: 10px; color: #7F8C8D; border-top: 1px solid #D0D7DE; padding-top: 8px;")
        sidebar_layout.addWidget(lbl_user)

        main_layout.addWidget(sidebar)

        # Stacked Views Container
        self.stacked_widget = QStackedWidget()

        self.view_dash = DashboardWidget(db_path=self.db_path)
        self.view_students = StudentManagementWidget(db_path=self.db_path)
        self.view_terms = TermClassManagementWidget(db_path=self.db_path)
        self.view_payments = PaymentsAndInvoicingWidget(db_path=self.db_path)
        self.view_expenses = ExpensesWidget(db_path=self.db_path)
        self.view_reports = ReportsWidget(db_path=self.db_path)
        self.view_settings = SettingsWidget(db_path=self.db_path)

        self.stacked_widget.addWidget(self.view_dash)
        self.stacked_widget.addWidget(self.view_students)
        self.stacked_widget.addWidget(self.view_terms)
        self.stacked_widget.addWidget(self.view_payments)
        self.stacked_widget.addWidget(self.view_expenses)
        self.stacked_widget.addWidget(self.view_reports)
        self.stacked_widget.addWidget(self.view_settings)

        main_layout.addWidget(self.stacked_widget, 1)

    def switch_view(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        if index == 0:
            self.view_dash.refresh_dashboard()

def main():
    app = QApplication(sys.argv)
    apply_theme(app)

    db_path = DEFAULT_DB_PATH
    init_db(db_path)

    auth_service = AuthService(db_path)
    auth_service.create_initial_manager()

    login_dlg = LoginDialog(auth_service)
    if login_dlg.exec() == QDialog.Accepted:
        win = MainWindow(db_path, login_dlg.user, auth_service)
        win.show()
        sys.exit(app.exec())

if __name__ == "__main__":
    main()
