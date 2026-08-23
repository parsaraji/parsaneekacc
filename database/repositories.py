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
        now_date = start_date or datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            "INSERT INTO terms (name, start_date, end_date, status) VALUES (?, ?, ?, ?)",
            (name, now_date, end_date, status)
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

    def toggle_term_status(self, term_id: int) -> str:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM terms WHERE id = ?", (term_id,))
        row = cursor.fetchone()
        if row:
            new_status = "closed" if row["status"] == "open" else "open"
            cursor.execute("UPDATE terms SET status = ? WHERE id = ?", (new_status, term_id))
            conn.commit()
            conn.close()
            return new_status
        conn.close()
        return "open"

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
                     capacity: int = 30, start_date: str = "", tuition_fee: float = 0,
                     book_fee: float = 0, other_fee: float = 0, other_fee_title: str = "هزینه جانبی",
                     book_ids: Optional[List[int]] = None) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO classes (code, name, teacher_name, term_id, start_date, capacity, tuition_fee, book_fee, other_fee, other_fee_title, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
            (code, name, teacher_name, term_id, start_date, capacity, tuition_fee, book_fee, other_fee, other_fee_title)
        )
        class_id = cursor.lastrowid
        if book_ids:
            for bid in book_ids:
                cursor.execute(
                    "INSERT OR IGNORE INTO class_books (class_id, book_id) VALUES (?, ?)",
                    (class_id, bid)
                )
        conn.commit()
        conn.close()
        return class_id

    def update_class(self, class_id: int, code: str, name: str, teacher_name: str,
                     capacity: int, start_date: str, status: str, tuition_fee: float = 0,
                     book_fee: float = 0, other_fee: float = 0, other_fee_title: str = "هزینه جانبی",
                     book_ids: Optional[List[int]] = None) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE classes SET code=?, name=?, teacher_name=?, capacity=?, start_date=?, status=?,
               tuition_fee=?, book_fee=?, other_fee=?, other_fee_title=?
               WHERE id=?""",
            (code, name, teacher_name, capacity, start_date, status, tuition_fee, book_fee, other_fee, other_fee_title, class_id)
        )
        if book_ids is not None:
            cursor.execute("DELETE FROM class_books WHERE class_id = ?", (class_id,))
            for bid in book_ids:
                cursor.execute("INSERT OR IGNORE INTO class_books (class_id, book_id) VALUES (?, ?)", (class_id, bid))
        conn.commit()
        conn.close()

    def toggle_class_status(self, class_id: int) -> str:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM classes WHERE id = ?", (class_id,))
        row = cursor.fetchone()
        if row:
            new_status = "closed" if row["status"] == "active" else "active"
            cursor.execute("UPDATE classes SET status = ? WHERE id = ?", (new_status, class_id))
            conn.commit()
            conn.close()
            return new_status
        conn.close()
        return "active"

    def delete_class(self, class_id: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM class_books WHERE class_id = ?", (class_id,))
        cursor.execute("DELETE FROM class_enrollments WHERE class_id = ?", (class_id,))
        cursor.execute("DELETE FROM classes WHERE id = ?", (class_id,))
        conn.commit()
        conn.close()

    def get_class_books(self, class_id: int) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT b.* FROM books b
               JOIN class_books cb ON b.id = cb.book_id
               WHERE cb.class_id = ?""",
            (class_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

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

    def add_enrollment(self, class_id: int, student_id: int, selected_book_ids: Optional[List[int]] = None) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check if student is currently enrolled in ANY active class
        cursor.execute(
            """SELECT c.name, c.code FROM class_enrollments ce
               JOIN classes c ON ce.class_id = c.id
               WHERE ce.student_id = ? AND ce.status = 'active'""",
            (student_id,)
        )
        active_enrollment = cursor.fetchone()
        if active_enrollment:
            conn.close()
            cls_info = f"{active_enrollment['name']} ({active_enrollment['code']})"
            raise ValueError(f"این دانش‌آموز درحال حاضر در کلاس فعال '{cls_info}' ثبت‌نام می‌باشد. برای ثبت‌نام در کلاس جدید، ابتدا وضعیت کلاس قبلی را فارغ‌التحصیل یا انصرافی قرار دهید.")

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

        cursor.execute("SELECT * FROM classes WHERE id = ?", (class_id,))
        cls = cursor.fetchone()
        term_id = cls["term_id"]

        cursor.execute(
            "INSERT OR IGNORE INTO student_terms (student_id, term_id, enrolled_at) VALUES (?, ?, ?)",
            (student_id, term_id, now)
        )

        # Determine books to charge and reduce stock on
        books_to_process = []
        if selected_book_ids is not None:
            if selected_book_ids:
                placeholders = ",".join("?" for _ in selected_book_ids)
                cursor.execute(f"SELECT * FROM books WHERE id IN ({placeholders})", selected_book_ids)
                books_to_process = [dict(r) for r in cursor.fetchall()]
        else:
            cursor.execute(
                """SELECT b.* FROM books b
                   JOIN class_books cb ON b.id = cb.book_id
                   WHERE cb.class_id = ?""",
                (class_id,)
            )
            books_to_process = [dict(r) for r in cursor.fetchall()]

        # Directly reduce stock using current connection cursor (avoids database is locked error)
        for bk in books_to_process:
            cursor.execute("UPDATE books SET stock_quantity = stock_quantity - 1 WHERE id = ?", (bk["id"],))

        def get_type_id(pt_name):
            cursor.execute("SELECT id FROM payment_types WHERE name = ?", (pt_name,))
            r = cursor.fetchone()
            return r["id"] if r else 1

        p_code_num = 1

        # Insert tuition debt
        if cls["tuition_fee"] > 0:
            cursor.execute("SELECT MAX(id) FROM payments")
            max_id = cursor.fetchone()[0] or 0
            p_code = f"PAY-{max_id + 1:06d}"
            cursor.execute(
                """INSERT INTO payments (
                    unique_code, student_id, term_id, payment_type_id, amount,
                    discount_percent, discount_amount, late_fee_amount, method,
                    description, due_date, paid_date, paid_time, is_installment,
                    installment_no, installment_total, status
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 'cash', ?, '', ?, ?, 0, 1, 1, 'pending')""",
                (p_code, student_id, term_id, get_type_id("شهریه"), cls["tuition_fee"],
                 f"شهریه کلاس {cls['name']} ({cls['code']})", now[:10], now[11:])
            )

        # Insert book debts for each processed book
        for bk in books_to_process:
            if bk["sale_price"] > 0:
                cursor.execute("SELECT MAX(id) FROM payments")
                max_id = cursor.fetchone()[0] or 0
                p_code = f"PAY-{max_id + 1:06d}"
                cursor.execute(
                    """INSERT INTO payments (
                        unique_code, student_id, term_id, payment_type_id, amount,
                        discount_percent, discount_amount, late_fee_amount, method,
                        description, due_date, paid_date, paid_time, is_installment,
                        installment_no, installment_total, status
                    ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 'cash', ?, '', ?, ?, 0, 1, 1, 'pending')""",
                    (p_code, student_id, term_id, get_type_id("کتاب"), bk["sale_price"],
                     f"کتاب کلاس {cls['name']}: {bk['title']}", now[:10], now[11:])
                )

        # Insert other fee debt
        if cls["other_fee"] > 0:
            cursor.execute("SELECT MAX(id) FROM payments")
            max_id = cursor.fetchone()[0] or 0
            p_code = f"PAY-{max_id + 1:06d}"
            cursor.execute(
                """INSERT INTO payments (
                    unique_code, student_id, term_id, payment_type_id, amount,
                    discount_percent, discount_amount, late_fee_amount, method,
                    description, due_date, paid_date, paid_time, is_installment,
                    installment_no, installment_total, status
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 'cash', ?, '', ?, ?, 0, 1, 1, 'pending')""",
                (p_code, student_id, term_id, get_type_id("هزینه‌های جانبی"), cls["other_fee"],
                 f"{cls['other_fee_title'] or 'هزینه جانبی'} - کلاس {cls['name']}", now[:10], now[11:])
            )

        conn.commit()
        conn.close()

    def update_enrollment_status(self, enrollment_id: int, new_status: str) -> None:
        """Updates enrollment status ('active', 'graduated', 'dropped_out', 'transferred_out')."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE class_enrollments SET status = ? WHERE id = ?", (new_status, enrollment_id))
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
        self.remove_enrollment(from_class_id, student_id)
        self.add_enrollment(to_class_id, student_id)

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

    def record_multi_item_payment(self, student_id: int, line_items: List[Dict[str, Any]], method: str,
                                  term_id: Optional[int] = None, pos_device_id: Optional[int] = None,
                                  card_destination_id: Optional[int] = None, bank_reference_number: str = "",
                                  card_tracking_code: str = "", description: str = "", status: str = "paid",
                                  recorded_by_user_id: Optional[int] = None) -> List[int]:
        created_ids = []
        for item in line_items:
            pt_id = item["payment_type_id"]
            amt = item["amount"]
            disc_pct = item.get("discount_percent", 0)
            disc_amt = item.get("discount_amount", 0)
            late_fee = item.get("late_fee_amount", 0)
            item_desc = f"{description} - {item.get('name_label', '')}".strip(" -")

            pid = self.record_payment(
                student_id=student_id,
                payment_type_id=pt_id,
                amount=amt,
                method=method,
                term_id=term_id,
                discount_percent=disc_pct,
                discount_amount=disc_amt,
                late_fee_amount=late_fee,
                pos_device_id=pos_device_id,
                card_destination_id=card_destination_id,
                bank_reference_number=bank_reference_number,
                card_tracking_code=card_tracking_code,
                description=item_desc,
                status=status,
                recorded_by_user_id=recorded_by_user_id,
                create_invoice=(status == "paid")
            )
            created_ids.append(pid)
        return created_ids

    def settle_and_record_transaction(self, student_id: int, debt_settlements: List[Dict[str, Any]],
                                       new_line_items: List[Dict[str, Any]], method: str,
                                       term_id: Optional[int] = None, pos_device_id: Optional[int] = None,
                                       card_destination_id: Optional[int] = None, bank_reference_number: str = "",
                                       card_tracking_code: str = "", description: str = "",
                                       recorded_by_user_id: Optional[int] = None) -> int:
        """
        Executes multi-debt settlements and new line-item charges inside a SINGLE atomic transaction.
        When a pending debt is fully settled, the pending debt record is removed or reduced, and
        ONE consolidated paid payment record is issued with ONE invoice. This guarantees zero double-counting
        and zero database locks.
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        now_date = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now().strftime("%H:%M:%S")

        total_settled_amount = 0.0
        settlement_descriptions = []

        # 1. Process Debt Settlements
        for debt_item in debt_settlements:
            debt_id = debt_item["debt_id"]
            pay_amt = debt_item["pay_amount"]
            debt_total = debt_item["total_debt_amount"]
            d_desc = debt_item.get("description", "بدهی")

            if pay_amt <= 0:
                continue

            if pay_amt >= debt_total:
                # Full settlement: delete pending debt row to avoid double-counting
                cursor.execute("DELETE FROM payments WHERE id = ?", (debt_id,))
                settlement_descriptions.append(f"تسویه کامل ({d_desc})")
                total_settled_amount += pay_amt
            else:
                # Partial settlement: reduce remaining pending debt
                rem_debt = debt_total - pay_amt
                cursor.execute("UPDATE payments SET amount = ? WHERE id = ?", (rem_debt, debt_id))
                settlement_descriptions.append(f"تسویه بخشی از ({d_desc}): {pay_amt}")
                total_settled_amount += pay_amt

        # 2. Process New Line Items
        new_items_amount = 0.0
        for nitem in new_line_items:
            n_amt = nitem["amount"]
            n_lbl = nitem.get("name_label", "آیتم جدید")
            new_items_amount += n_amt
            settlement_descriptions.append(f"{n_lbl}: {n_amt}")

        total_paid_overall = total_settled_amount + new_items_amount

        if total_paid_overall <= 0:
            conn.close()
            return 0

        # 3. Create ONE consolidated payment record for the full transaction amount
        p_code = self._generate_payment_code(cursor)
        combined_desc = f"{description} | " + " - ".join(settlement_descriptions) if description else " - ".join(settlement_descriptions)

        cursor.execute("SELECT id FROM payment_types WHERE name = 'شهریه'")
        r_pt = cursor.fetchone()
        pt_id = r_pt["id"] if r_pt else 1

        cursor.execute(
            """INSERT INTO payments (
                unique_code, student_id, term_id, payment_type_id, amount,
                discount_percent, discount_amount, late_fee_amount, method,
                pos_device_id, card_destination_id, bank_reference_number, card_tracking_code,
                description, due_date, paid_date, paid_time, is_installment,
                installment_no, installment_total, status, recorded_by_user_id
            ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 1, 'paid', ?)""",
            (
                p_code, student_id, term_id, pt_id, total_paid_overall, method,
                pos_device_id, card_destination_id, bank_reference_number, card_tracking_code,
                combined_desc, now_date, now_date, now_time, recorded_by_user_id
            )
        )
        final_payment_id = cursor.lastrowid

        # 4. Issue ONE consolidated invoice
        inv_code = self._generate_invoice_code(cursor)
        issued_at = f"{now_date} {now_time}"
        cursor.execute(
            "INSERT INTO invoices (unique_code, payment_id, student_id, issued_at, printed) VALUES (?, ?, ?, ?, 0)",
            (inv_code, final_payment_id, student_id, issued_at)
        )

        conn.commit()
        conn.close()
        return final_payment_id

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

    def get_term_debtors(self, term_id: int) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT s.unique_code, s.first_name, s.last_name, s.father_name,
                      (SELECT phone_number FROM student_phones WHERE student_id = s.id AND is_primary = 1 LIMIT 1) as primary_phone,
                      p.description, p.amount, p.paid_date
               FROM payments p
               JOIN students s ON p.student_id = s.id
               WHERE p.term_id = ? AND p.status IN ('pending', 'partial')
               ORDER BY s.last_name, s.first_name""",
            (term_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_payment(self, payment_id: int) -> None:
        """Deletes a payment/debt record by ID."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices WHERE payment_id = ?", (payment_id,))
        cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
        conn.commit()
        conn.close()

    def apply_discount_to_debt(self, payment_id: int, discount_amount: float = 0.0, discount_percent: float = 0.0) -> None:
        """Applies a discount to an existing pending debt record, updating discount fields and reducing remaining amount."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT amount, discount_amount FROM payments WHERE id = ?", (payment_id,))
        row = cursor.fetchone()
        if row:
            curr_amt = row["amount"]
            calc_disc = discount_amount
            if discount_percent > 0:
                calc_disc += (curr_amt * (discount_percent / 100.0))

            if calc_disc >= curr_amt:
                new_amt = 0.0
                status = "paid"
            else:
                new_amt = curr_amt - calc_disc
                status = "pending"

            cursor.execute(
                """UPDATE payments SET amount = ?, discount_amount = discount_amount + ?, discount_percent = discount_percent + ?, status = ?
                   WHERE id = ?""",
                (new_amt, calc_disc, discount_percent, status, payment_id)
            )
            conn.commit()
        conn.close()

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

    def add_attachment(self, student_id: int, file_path: str, category: str = "سایر مدارک", file_type: str = "doc") -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO attachments (student_id, category, file_path, file_type, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            (student_id, category, file_path, file_type, now)
        )
        att_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return att_id

    def list_attachments(self, student_id: int) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM attachments WHERE student_id = ? ORDER BY id ASC", (student_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            # Fallback if category column migration pending
            cursor.execute("SELECT * FROM attachments WHERE student_id = ? ORDER BY id ASC", (student_id,))
            rows = cursor.fetchall()
            res = []
            for r in rows:
                d = dict(r)
                if "category" not in d:
                    d["category"] = "سایر مدارک"
                res.append(d)
            return res
        finally:
            conn.close()

    def update_attachment(self, att_id: int, category: str, file_path: str) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE attachments SET category = ?, file_path = ? WHERE id = ?", (category, file_path, att_id))
        conn.commit()
        conn.close()

    def delete_attachment(self, att_id: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
        conn.commit()
        conn.close()


class BookRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def add_book(self, title: str, purchase_price: float, sale_price: float, stock_quantity: int = 0) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO books (title, purchase_price, sale_price, stock_quantity) VALUES (?, ?, ?, ?)",
            (title, purchase_price, sale_price, stock_quantity)
        )
        bid = cursor.lastrowid
        conn.commit()
        conn.close()
        return bid

    def list_books(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM books ORDER BY title ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_by_id(self, book_id: int) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_stock(self, book_id: int) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM books WHERE id = ?", (book_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0

    def reduce_stock(self, book_id: int, count: int = 1) -> int:
        """Reduces book stock by count. Stock can become negative if confirmed."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE books SET stock_quantity = stock_quantity - ? WHERE id = ?", (count, book_id))
        cursor.execute("SELECT stock_quantity FROM books WHERE id = ?", (book_id,))
        new_stock = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return new_stock

    def update_book(self, book_id: int, title: str, purchase_price: float, sale_price: float, stock_quantity: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE books SET title = ?, purchase_price = ?, sale_price = ?, stock_quantity = ? WHERE id = ?",
            (title, purchase_price, sale_price, stock_quantity, book_id)
        )
        conn.commit()
        conn.close()


class ExpenseRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def add_expense(self, category: str, amount: float, date: str, description: str = "",
                    method: str = "cash", pos_device_id: Optional[int] = None,
                    card_destination_id: Optional[int] = None, recorded_by_user_id: Optional[int] = None) -> int:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        now_date = date or datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            """INSERT INTO expenses (category, amount, date, method, pos_device_id, card_destination_id, description, recorded_by_user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (category, amount, now_date, method, pos_device_id, card_destination_id, description, recorded_by_user_id)
        )
        expense_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return expense_id

    def list_expenses(self, date_from: str = "", date_to: str = "", category: str = "") -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        sql = """
        SELECT e.*, u.full_name as recorded_by_name, pd.label as pos_label, cd.owner_label as card_label, cd.card_number
        FROM expenses e
        LEFT JOIN users u ON e.recorded_by_user_id = u.id
        LEFT JOIN pos_devices pd ON e.pos_device_id = pd.id
        LEFT JOIN card_destinations cd ON e.card_destination_id = cd.id
        WHERE 1=1
        """
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

    def update_pos_device(self, pos_id: int, label: str, bank_name: str) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE pos_devices SET label = ?, bank_name = ? WHERE id = ?", (label, bank_name, pos_id))
        conn.commit()
        conn.close()

    def delete_pos_device(self, pos_id: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE pos_devices SET is_active = 0 WHERE id = ?", (pos_id,))
        conn.commit()
        conn.close()

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

    def update_card_destination(self, card_id: int, card_number: str, owner_label: str) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE card_destinations SET card_number = ?, owner_label = ? WHERE id = ?", (card_number, owner_label, card_id))
        conn.commit()
        conn.close()

    def delete_card_destination(self, card_id: int) -> None:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE card_destinations SET is_active = 0 WHERE id = ?", (card_id,))
        conn.commit()
        conn.close()

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
