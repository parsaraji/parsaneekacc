import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from database.db import get_connection

class UserRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def create_user(self, username: str, password_hash: str, full_name: str, role: str) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, role, is_active) VALUES (?, ?, ?, ?, 1)",
            (username, password_hash, full_name, role)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_users(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, full_name, role, is_active FROM users ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_user(self, user_id: int, full_name: str, role: str, is_active: bool, password_hash: Optional[str] = None) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        if password_hash:
            cursor.execute(
                "UPDATE users SET full_name = ?, role = ?, is_active = ?, password_hash = ? WHERE id = ?",
                (full_name, role, 1 if is_active else 0, password_hash, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET full_name = ?, role = ?, is_active = ? WHERE id = ?",
                (full_name, role, 1 if is_active else 0, user_id)
            )
        conn.commit()
        conn.close()


class StudentRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _generate_unique_code(self, cursor: sqlite3.Cursor) -> str:
        cursor.execute("SELECT MAX(id) FROM students")
        max_id = cursor.fetchone()[0] or 0
        next_num = max_id + 1
        return f"PN-{next_num:05d}"

    def create_student(self, first_name: str, last_name: str, father_name: str = "",
                       address: str = "", private_notes: str = "", phones: Optional[List[Dict[str, Any]]] = None,
                       user_id: Optional[int] = None) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        code = self._generate_unique_code(cursor)

        cursor.execute(
            """INSERT INTO students (unique_code, first_name, last_name, father_name, address, status, private_notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
            (code, first_name, last_name, father_name, address, private_notes, now, now)
        )
        student_id = cursor.lastrowid

        if phones:
            for p in phones:
                cursor.execute(
                    "INSERT INTO student_phones (student_id, phone_number, label, is_primary) VALUES (?, ?, ?, ?)",
                    (student_id, p["phone_number"], p.get("label", "همراه"), 1 if p.get("is_primary") else 0)
                )

        # Audit log creation
        cursor.execute(
            """INSERT INTO audit_log (entity_type, entity_id, field_name, old_value, new_value, changed_by_user_id, changed_at)
               VALUES ('student', ?, 'created', '', ?, ?, ?)""",
            (student_id, f"{first_name} {last_name}", user_id, now)
        )

        conn.commit()
        conn.close()
        return student_id

    def update_student(self, student_id: int, first_name: str, last_name: str, father_name: str = "",
                       address: str = "", status: str = "active", private_notes: str = "",
                       user_id: Optional[int] = None) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get old values for audit
        cursor.execute("SELECT first_name, last_name, status FROM students WHERE id = ?", (student_id,))
        old = cursor.fetchone()

        cursor.execute(
            """UPDATE students SET first_name=?, last_name=?, father_name=?, address=?, status=?, private_notes=?, updated_at=?
               WHERE id=?""",
            (first_name, last_name, father_name, address, status, private_notes, now, student_id)
        )

        if old:
            if old["first_name"] != first_name or old["last_name"] != last_name:
                cursor.execute(
                    """INSERT INTO audit_log (entity_type, entity_id, field_name, old_value, new_value, changed_by_user_id, changed_at)
                       VALUES ('student', ?, 'full_name', ?, ?, ?, ?)""",
                    (student_id, f"{old['first_name']} {old['last_name']}", f"{first_name} {last_name}", user_id, now)
                )
            if old["status"] != status:
                cursor.execute(
                    """INSERT INTO audit_log (entity_type, entity_id, field_name, old_value, new_value, changed_by_user_id, changed_at)
                       VALUES ('student', ?, 'status', ?, ?, ?, ?)""",
                    (student_id, old["status"], status, user_id, now)
                )

        conn.commit()
        conn.close()

    def set_primary_phone(self, student_id: int, phone_number: str, label: str = "همراه") -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM student_phones WHERE student_id = ? AND is_primary = 1", (student_id,))
        primary_row = cursor.fetchone()

        if primary_row:
            cursor.execute(
                "UPDATE student_phones SET phone_number = ?, label = ? WHERE id = ?",
                (phone_number, label, primary_row["id"])
            )
        else:
            cursor.execute(
                "INSERT INTO student_phones (student_id, phone_number, label, is_primary) VALUES (?, ?, ?, 1)",
                (student_id, phone_number, label)
            )

        conn.commit()
        conn.close()

    def get_by_id(self, student_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_phones(self, student_id: int) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM student_phones WHERE student_id = ? ORDER BY is_primary DESC, id ASC", (student_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_phone(self, student_id: int, phone_number: str, label: str = "همراه", is_primary: bool = False) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        if is_primary:
            cursor.execute("UPDATE student_phones SET is_primary = 0 WHERE student_id = ?", (student_id,))
        cursor.execute(
            "INSERT INTO student_phones (student_id, phone_number, label, is_primary) VALUES (?, ?, ?, ?)",
            (student_id, phone_number, label, 1 if is_primary else 0)
        )
        phone_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return phone_id

    def delete_phone(self, phone_id: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM student_phones WHERE id = ?", (phone_id,))
        conn.commit()
        conn.close()

    def search_students(self, query: str = "", status: str = "", term_id: Optional[int] = None, class_id: Optional[int] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        sql = """
        SELECT DISTINCT s.*,
            (SELECT phone_number FROM student_phones WHERE student_id = s.id AND is_primary = 1 LIMIT 1) as primary_phone
        FROM students s
        LEFT JOIN student_phones sp ON s.id = sp.student_id
        LEFT JOIN student_terms st ON s.id = st.student_id
        LEFT JOIN class_enrollments ce ON s.id = ce.student_id
        WHERE 1=1
        """
        params = []

        if query:
            q = f"%{query.strip()}%"
            sql += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR (s.first_name || ' ' || s.last_name) LIKE ? OR s.unique_code LIKE ? OR sp.phone_number LIKE ?)"
            params.extend([q, q, q, q, q])

        if status:
            sql += " AND s.status = ?"
            params.append(status)

        if term_id:
            sql += " AND st.term_id = ?"
            params.append(term_id)

        if class_id:
            sql += " AND ce.class_id = ? AND ce.status = 'active'"
            params.append(class_id)

        sql += " ORDER BY s.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def count_students(self, query: str = "", status: str = "") -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        sql = "SELECT COUNT(DISTINCT s.id) FROM students s LEFT JOIN student_phones sp ON s.id = sp.student_id WHERE 1=1"
        params = []
        if query:
            q = f"%{query.strip()}%"
            sql += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR (s.first_name || ' ' || s.last_name) LIKE ? OR s.unique_code LIKE ? OR sp.phone_number LIKE ?)"
            params.extend([q, q, q, q, q])
        if status:
            sql += " AND s.status = ?"
            params.append(status)

        cursor.execute(sql, params)
        count = cursor.fetchone()[0]
        conn.close()
        return count


class TermRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def create_term(self, name: str, start_date: str = "", end_date: str = "", status: str = "open") -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO terms (name, start_date, end_date, status) VALUES (?, ?, ?, ?)",
            (name, start_date, end_date, status)
        )
        term_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return term_id

    def update_term(self, term_id: int, name: str, start_date: str, end_date: str, status: str) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE terms SET name=?, start_date=?, end_date=?, status=? WHERE id=?",
            (name, start_date, end_date, status, term_id)
        )
        conn.commit()
        conn.close()

    def get_by_id(self, term_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM terms WHERE id = ?", (term_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_terms(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM terms ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def enroll_student_in_term(self, student_id: int, term_id: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT OR IGNORE INTO student_terms (student_id, term_id, enrolled_at) VALUES (?, ?, ?)",
            (student_id, term_id, now)
        )
        conn.commit()
        conn.close()

    def get_student_terms(self, student_id: int) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT t.*, st.enrolled_at FROM terms t
               JOIN student_terms st ON t.id = st.term_id
               WHERE st.student_id = ? ORDER BY t.id DESC""",
            (student_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]


class ClassRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def create_class(self, code: str, name: str, teacher_name: str, term_id: int,
                     capacity: int = 30, start_date: str = "") -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO classes (code, name, teacher_name, term_id, start_date, capacity, status)
               VALUES (?, ?, ?, ?, ?, ?, 'active')""",
            (code, name, teacher_name, term_id, start_date, capacity)
        )
        class_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return class_id

    def update_class(self, class_id: int, code: str, name: str, teacher_name: str,
                     capacity: int, start_date: str, status: str) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE classes SET code=?, name=?, teacher_name=?, capacity=?, start_date=?, status=?
               WHERE id=?""",
            (code, name, teacher_name, capacity, start_date, status, class_id)
        )
        conn.commit()
        conn.close()

    def get_by_id(self, class_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT c.*, t.name as term_name FROM classes c JOIN terms t ON c.term_id = t.id WHERE c.id = ?", (class_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_classes(self, term_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        sql = """
        SELECT c.*, t.name as term_name,
               (SELECT COUNT(*) FROM class_enrollments ce WHERE ce.class_id = c.id AND ce.status = 'active') as enrolled_count
        FROM classes c
        JOIN terms t ON c.term_id = t.id
        WHERE 1=1
        """
        params = []
        if term_id:
            sql += " AND c.term_id = ?"
            params.append(term_id)
        if status:
            sql += " AND c.status = ?"
            params.append(status)

        sql += " ORDER BY c.id DESC"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_enrollment(self, class_id: int, student_id: int) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            "SELECT id FROM class_enrollments WHERE class_id = ? AND student_id = ? AND status = 'active'",
            (class_id, student_id)
        )
        if cursor.fetchone():
            conn.close()
            return 0

        cursor.execute(
            "INSERT INTO class_enrollments (class_id, student_id, enrolled_at, status) VALUES (?, ?, ?, 'active')",
            (class_id, student_id, now)
        )
        enrollment_id = cursor.lastrowid

        cursor.execute("SELECT term_id FROM classes WHERE id = ?", (class_id,))
        term_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT OR IGNORE INTO student_terms (student_id, term_id, enrolled_at) VALUES (?, ?, ?)",
            (student_id, term_id, now)
        )

        conn.commit()
        conn.close()
        return enrollment_id

    def remove_enrollment(self, class_id: int, student_id: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM class_enrollments WHERE class_id = ? AND student_id = ?",
            (class_id, student_id)
        )
        conn.commit()
        conn.close()

    def transfer_student(self, from_class_id: int, to_class_id: int, student_id: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE class_enrollments SET status = 'transferred_out' WHERE class_id = ? AND student_id = ?",
            (from_class_id, student_id)
        )
        cursor.execute(
            "INSERT INTO class_enrollments (class_id, student_id, enrolled_at, status) VALUES (?, ?, ?, 'active')",
            (to_class_id, student_id, now)
        )
        cursor.execute("SELECT term_id FROM classes WHERE id = ?", (to_class_id,))
        term_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT OR IGNORE INTO student_terms (student_id, term_id, enrolled_at) VALUES (?, ?, ?)",
            (student_id, term_id, now)
        )

        conn.commit()
        conn.close()

    def get_class_roster(self, class_id: int) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT s.*, ce.enrolled_at, ce.status as enrollment_status,
                      (SELECT phone_number FROM student_phones WHERE student_id = s.id AND is_primary = 1 LIMIT 1) as primary_phone
               FROM class_enrollments ce
               JOIN students s ON ce.student_id = s.id
               WHERE ce.class_id = ? AND ce.status = 'active'
               ORDER BY s.last_name, s.first_name""",
            (class_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]


class PaymentRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _generate_payment_code(self, cursor: sqlite3.Cursor) -> str:
        cursor.execute("SELECT MAX(id) FROM payments")
        max_id = cursor.fetchone()[0] or 0
        return f"PAY-{max_id + 1:06d}"

    def _generate_invoice_code(self, cursor: sqlite3.Cursor) -> str:
        cursor.execute("SELECT MAX(id) FROM invoices")
        max_id = cursor.fetchone()[0] or 0
        return f"INV-{max_id + 1:06d}"

    def record_payment(self, student_id: int, payment_type_id: int, amount: float,
                       method: str, term_id: Optional[int] = None, discount_percent: float = 0,
                       discount_amount: float = 0, late_fee_amount: float = 0,
                       pos_device_id: Optional[int] = None, card_destination_id: Optional[int] = None,
                       bank_reference_number: str = "", card_tracking_code: str = "",
                       description: str = "", due_date: str = "", paid_date: str = "", paid_time: str = "",
                       is_installment: bool = False, installment_no: int = 1, installment_total: int = 1,
                       status: str = "paid", recorded_by_user_id: Optional[int] = None, create_invoice: bool = True) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        now_date = paid_date or datetime.now().strftime("%Y-%m-%d")
        now_time = paid_time or datetime.now().strftime("%H:%M:%S")
        p_code = self._generate_payment_code(cursor)

        cursor.execute(
            """INSERT INTO payments (
                unique_code, student_id, term_id, payment_type_id, amount,
                discount_percent, discount_amount, late_fee_amount, method,
                pos_device_id, card_destination_id, bank_reference_number, card_tracking_code,
                description, due_date, paid_date, paid_time, is_installment,
                installment_no, installment_total, status, recorded_by_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p_code, student_id, term_id, payment_type_id, amount,
                discount_percent, discount_amount, late_fee_amount, method,
                pos_device_id, card_destination_id, bank_reference_number, card_tracking_code,
                description, due_date, now_date, now_time, 1 if is_installment else 0,
                installment_no, installment_total, status, recorded_by_user_id
            )
        )
        payment_id = cursor.lastrowid

        if create_invoice:
            inv_code = self._generate_invoice_code(cursor)
            issued_at = f"{now_date} {now_time}"
            cursor.execute(
                "INSERT INTO invoices (unique_code, payment_id, student_id, issued_at, printed) VALUES (?, ?, ?, ?, 0)",
                (inv_code, payment_id, student_id, issued_at)
            )

        cursor.execute(
            """INSERT INTO audit_log (entity_type, entity_id, field_name, old_value, new_value, changed_by_user_id, changed_at)
               VALUES ('payment', ?, 'created', '', ?, ?, ?)""",
            (payment_id, f"M: {amount}", recorded_by_user_id, f"{now_date} {now_time}")
        )

        conn.commit()
        conn.close()
        return payment_id

    def list_payments(self, student_id: Optional[int] = None, term_id: Optional[int] = None,
                      date_from: str = "", date_to: str = "", status: str = "",
                      payment_type_id: Optional[int] = None, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        sql = """
        SELECT p.*,
               s.first_name || ' ' || s.last_name as student_name, s.unique_code as student_code,
               pt.name as payment_type_name,
               pd.label as pos_device_label,
               cd.card_number as card_destination_number, cd.owner_label as card_destination_owner,
               inv.id as invoice_id, inv.unique_code as invoice_code, inv.printed as invoice_printed
        FROM payments p
        JOIN students s ON p.student_id = s.id
        JOIN payment_types pt ON p.payment_type_id = pt.id
        LEFT JOIN pos_devices pd ON p.pos_device_id = pd.id
        LEFT JOIN card_destinations cd ON p.card_destination_id = cd.id
        LEFT JOIN invoices inv ON p.id = inv.payment_id
        WHERE 1=1
        """
        params = []

        if student_id:
            sql += " AND p.student_id = ?"
            params.append(student_id)
        if term_id:
            sql += " AND p.term_id = ?"
            params.append(term_id)
        if date_from:
            sql += " AND p.paid_date >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND p.paid_date <= ?"
            params.append(date_to)
        if status:
            sql += " AND p.status = ?"
            params.append(status)
        if payment_type_id:
            sql += " AND p.payment_type_id = ?"
            params.append(payment_type_id)

        sql += " ORDER BY p.paid_date DESC, p.paid_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_payment_by_id(self, payment_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT p.*, s.first_name, s.last_name, s.father_name, s.unique_code as student_code,
                      pt.name as payment_type_name, t.name as term_name,
                      pd.label as pos_device_label, pd.bank_name as pos_bank_name,
                      cd.card_number, cd.owner_label as card_owner,
                      inv.unique_code as invoice_code
               FROM payments p
               JOIN students s ON p.student_id = s.id
               JOIN payment_types pt ON p.payment_type_id = pt.id
               LEFT JOIN terms t ON p.term_id = t.id
               LEFT JOIN pos_devices pd ON p.pos_device_id = pd.id
               LEFT JOIN card_destinations cd ON p.card_destination_id = cd.id
               LEFT JOIN invoices inv ON p.id = inv.payment_id
               WHERE p.id = ?""",
            (payment_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


class DailyClosingRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def perform_daily_closing(self, date_str: str, user_id: Optional[int] = None) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT method, SUM(amount) FROM payments WHERE paid_date = ? AND status = 'paid' GROUP BY method",
            (date_str,)
        )
        totals = {"cash": 0.0, "pos": 0.0, "card_to_card": 0.0}
        for method, amt in cursor.fetchall():
            if method in totals:
                totals[method] = amt or 0.0

        total_all = sum(totals.values())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """INSERT OR REPLACE INTO daily_closings (date, total_cash, total_pos, total_card_to_card, total_amount, closed_by_user_id, closed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date_str, totals["cash"], totals["pos"], totals["card_to_card"], total_all, user_id, now)
        )
        closing_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return closing_id

    def list_closings(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT dc.*, u.full_name as closed_by_name FROM daily_closings dc
               LEFT JOIN users u ON dc.closed_by_user_id = u.id
               ORDER BY dc.date DESC"""
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]


class AttachmentRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def add_attachment(self, student_id: int, file_path: str, file_type: str = "doc") -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO attachments (student_id, file_path, file_type, uploaded_at) VALUES (?, ?, ?, ?)",
            (student_id, file_path, file_type, now)
        )
        att_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return att_id

    def list_attachments(self, student_id: int) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attachments WHERE student_id = ? ORDER BY id DESC", (student_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]


class ExpenseRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def add_expense(self, category: str, amount: float, date: str, description: str = "", recorded_by_user_id: Optional[int] = None) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (category, amount, date, description, recorded_by_user_id) VALUES (?, ?, ?, ?, ?)",
            (category, amount, date, description, recorded_by_user_id)
        )
        expense_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return expense_id

    def list_expenses(self, date_from: str = "", date_to: str = "", category: str = "") -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        sql = "SELECT e.*, u.full_name as recorded_by_name FROM expenses e LEFT JOIN users u ON e.recorded_by_user_id = u.id WHERE 1=1"
        params = []
        if date_from:
            sql += " AND e.date >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND e.date <= ?"
            params.append(date_to)
        if category:
            sql += " AND e.category = ?"
            params.append(category)

        sql += " ORDER BY e.date DESC, e.id DESC"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]


class ConfigRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_setting(self, key: str, default: str = "") -> str:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()

    def list_pos_devices(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pos_devices WHERE is_active = 1 ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_pos_device(self, label: str, bank_name: str = "") -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pos_devices (label, bank_name, is_active) VALUES (?, ?, 1)", (label, bank_name))
        pos_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return pos_id

    def list_card_destinations(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM card_destinations WHERE is_active = 1 ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_card_destination(self, card_number: str, owner_label: str) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO card_destinations (card_number, owner_label, is_active) VALUES (?, ?, 1)", (card_number, owner_label))
        card_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return card_id

    def list_payment_types(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payment_types WHERE is_active = 1 ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_payment_type(self, name: str) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO payment_types (name, is_system_default, is_active) VALUES (?, 0, 1)", (name,))
        pt_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return pt_id


class AuditRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def log_change(self, entity_type: str, entity_id: int, field_name: str,
                   old_value: str, new_value: str, changed_by_user_id: Optional[int] = None) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """INSERT INTO audit_log (entity_type, entity_id, field_name, old_value, new_value, changed_by_user_id, changed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entity_type, entity_id, field_name, str(old_value), str(new_value), changed_by_user_id, now)
        )
        conn.commit()
        conn.close()

    def get_logs_for_entity(self, entity_type: str, entity_id: int) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT a.*, u.full_name as user_name FROM audit_log a
               LEFT JOIN users u ON a.changed_by_user_id = u.id
               WHERE a.entity_type = ? AND a.entity_id = ?
               ORDER BY a.changed_at DESC""",
            (entity_type, entity_id)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
