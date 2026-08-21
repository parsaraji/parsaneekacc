import os
import sqlite3
from typing import Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "parsanik.db")

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('manager', 'secretary', 'accountant')),
        is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unique_code TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        father_name TEXT,
        address TEXT,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'dropped_out', 'graduated')),
        private_notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS student_phones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        phone_number TEXT NOT NULL,
        label TEXT,
        is_primary INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed'))
    );

    CREATE TABLE IF NOT EXISTS student_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        term_id INTEGER NOT NULL,
        enrolled_at TEXT NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (term_id) REFERENCES terms(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        teacher_name TEXT,
        term_id INTEGER NOT NULL,
        start_date TEXT,
        capacity INTEGER NOT NULL DEFAULT 30,
        tuition_fee REAL NOT NULL DEFAULT 0,
        book_fee REAL NOT NULL DEFAULT 0,
        other_fee REAL NOT NULL DEFAULT 0,
        other_fee_title TEXT DEFAULT 'هزینه جانبی',
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'closed')),
        FOREIGN KEY (term_id) REFERENCES terms(id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS class_enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        enrolled_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'transferred_out')),
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS pos_devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT UNIQUE NOT NULL,
        bank_name TEXT,
        is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS card_destinations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_number TEXT NOT NULL,
        owner_label TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS payment_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        is_system_default INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unique_code TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        term_id INTEGER,
        payment_type_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        discount_percent REAL DEFAULT 0,
        discount_amount REAL DEFAULT 0,
        late_fee_amount REAL DEFAULT 0,
        method TEXT NOT NULL CHECK(method IN ('cash', 'pos', 'card_to_card')),
        pos_device_id INTEGER,
        card_destination_id INTEGER,
        bank_reference_number TEXT,
        card_tracking_code TEXT,
        description TEXT,
        due_date TEXT,
        paid_date TEXT,
        paid_time TEXT,
        is_installment INTEGER NOT NULL DEFAULT 0,
        installment_no INTEGER DEFAULT 1,
        installment_total INTEGER DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'paid' CHECK(status IN ('paid', 'partial', 'pending')),
        recorded_by_user_id INTEGER,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
        FOREIGN KEY (term_id) REFERENCES terms(id) ON DELETE SET NULL,
        FOREIGN KEY (payment_type_id) REFERENCES payment_types(id) ON DELETE RESTRICT,
        FOREIGN KEY (pos_device_id) REFERENCES pos_devices(id) ON DELETE SET NULL,
        FOREIGN KEY (card_destination_id) REFERENCES card_destinations(id) ON DELETE SET NULL,
        FOREIGN KEY (recorded_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unique_code TEXT UNIQUE NOT NULL,
        payment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        issued_at TEXT NOT NULL,
        printed INTEGER NOT NULL DEFAULT 0,
        sheet_row_position INTEGER DEFAULT 1,
        FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        description TEXT,
        recorded_by_user_id INTEGER,
        FOREIGN KEY (recorded_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS daily_closings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE NOT NULL,
        total_cash REAL NOT NULL DEFAULT 0,
        total_pos REAL NOT NULL DEFAULT 0,
        total_card_to_card REAL NOT NULL DEFAULT 0,
        total_amount REAL NOT NULL DEFAULT 0,
        closed_by_user_id INTEGER,
        closed_at TEXT NOT NULL,
        FOREIGN KEY (closed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        field_name TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        changed_by_user_id INTEGER,
        changed_at TEXT NOT NULL,
        FOREIGN KEY (changed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_students_name ON students(first_name, last_name);
    CREATE INDEX IF NOT EXISTS idx_students_code ON students(unique_code);
    CREATE INDEX IF NOT EXISTS idx_students_status ON students(status);
    CREATE INDEX IF NOT EXISTS idx_phones_student ON student_phones(student_id);
    CREATE INDEX IF NOT EXISTS idx_phones_number ON student_phones(phone_number);
    CREATE INDEX IF NOT EXISTS idx_payments_student ON payments(student_id);
    CREATE INDEX IF NOT EXISTS idx_payments_term ON payments(term_id);
    CREATE INDEX IF NOT EXISTS idx_payments_paid_date ON payments(paid_date);
    CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
    CREATE INDEX IF NOT EXISTS idx_classes_term ON classes(term_id);
    CREATE INDEX IF NOT EXISTS idx_enrollments_class ON class_enrollments(class_id);
    CREATE INDEX IF NOT EXISTS idx_enrollments_student ON class_enrollments(student_id);
    CREATE INDEX IF NOT EXISTS idx_invoices_payment ON invoices(payment_id);
    CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
    """)

    # Populate or sync default payment types
    default_types = ["شهریه", "کتاب", "هزینه‌های جانبی", "ثبت‌نام اولیه", "کلاس خصوصی"]
    for dt in default_types:
        cursor.execute("SELECT id FROM payment_types WHERE name = ?", (dt,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO payment_types (name, is_system_default) VALUES (?, 1)", (dt,))

    # Populate default settings if empty
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            [
                ("numeral_format", "persian"),
                ("currency_unit", "toman"),
                ("invoice_page_size", "A4"),
                ("auto_backup_on_close", "true"),
                ("backup_keep_count", "10")
            ]
        )

    conn.commit()
    conn.close()
