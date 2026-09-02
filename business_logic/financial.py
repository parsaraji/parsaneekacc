from typing import List, Dict, Any, Tuple, Optional
from database.db import get_connection

class FinancialEngine:
    def __init__(self, db_path: str = None):
        self.db_path = db_path

    @staticmethod
    def calculate_discounted_amount(base_amount: float, discount_percent: float = 0, discount_amount: float = 0, late_fee_amount: float = 0) -> float:
        """
        Calculates final amount after percent discount, fixed discount, and late fee.
        Formula: (base_amount - (base_amount * discount_percent / 100) - discount_amount) + late_fee_amount
        """
        pct_discount = base_amount * (discount_percent / 100.0) if discount_percent else 0.0
        net = base_amount - pct_discount - discount_amount
        if net < 0:
            net = 0.0
        return net + late_fee_amount

    @staticmethod
    def generate_installment_schedule(total_amount: float, num_installments: int, start_due_date: str = "") -> List[Dict[str, Any]]:
        """
        Splits total_amount into N installments.
        """
        if num_installments <= 0:
            return []

        base_inst_amount = round(total_amount / num_installments, 2)
        schedule = []
        accumulated = 0.0

        for i in range(1, num_installments + 1):
            if i == num_installments:
                inst_amount = round(total_amount - accumulated, 2)
            else:
                inst_amount = base_inst_amount
                accumulated += inst_amount

            schedule.append({
                "installment_no": i,
                "installment_total": num_installments,
                "amount": inst_amount,
                "status": "pending",
                "due_date": start_due_date
            })

        return schedule

    def get_student_financial_summary(self, student_id: int) -> Dict[str, Any]:
        """
        Computes total payments paid, total pending/debt for a student.
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Total paid payments
        cursor.execute(
            "SELECT SUM(amount) FROM payments WHERE student_id = ? AND status = 'paid'",
            (student_id,)
        )
        total_paid = cursor.fetchone()[0] or 0.0

        # Total pending/partial installments or payments
        cursor.execute(
            "SELECT SUM(amount) FROM payments WHERE student_id = ? AND status IN ('pending', 'partial')",
            (student_id,)
        )
        total_pending = cursor.fetchone()[0] or 0.0

        # Total discounts = SUM(COALESCE(original_amount, amount + discount_amount) - amount)
        cursor.execute(
            "SELECT SUM(COALESCE(original_amount, amount + discount_amount) - amount) FROM payments WHERE student_id = ?",
            (student_id,)
        )
        total_discount = cursor.fetchone()[0] or 0.0

        conn.close()

        return {
            "student_id": student_id,
            "total_paid": total_paid,
            "total_pending_debt": total_pending,
            "total_discount": total_discount,
            "net_balance": 0.0 if total_pending == 0 else -total_pending,
            "is_creditor": False
        }

    def get_institute_financial_summary(self, date_from: str = "", date_to: str = "") -> Dict[str, Any]:
        """
        Computes total income by payment method, total expenses, book sales, book costs, and net profit.
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Income by method
        sql_inc = "SELECT method, SUM(amount) FROM payments WHERE status = 'paid'"
        params_inc = []
        if date_from:
            sql_inc += " AND paid_date >= ?"
            params_inc.append(date_from)
        if date_to:
            sql_inc += " AND paid_date <= ?"
            params_inc.append(date_to)
        sql_inc += " GROUP BY method"

        cursor.execute(sql_inc, params_inc)
        rows_inc = cursor.fetchall()
        income_by_method = {"cash": 0.0, "pos": 0.0, "card_to_card": 0.0}
        for method, amt in rows_inc:
            if method in income_by_method:
                income_by_method[method] = amt or 0.0

        total_income = sum(income_by_method.values())

        # Category breakdowns for revenue
        cursor.execute(
            """SELECT pt.name, SUM(p.amount) FROM payments p
               JOIN payment_types pt ON p.payment_type_id = pt.id
               WHERE p.status = 'paid' GROUP BY pt.name"""
        )
        cat_income = {row[0]: row[1] or 0.0 for row in cursor.fetchall()}

        # Calculate Book COGS Purchase Cost (sum of book purchase price for sold books)
        # 1. New style: payments with book_unit_cost recorded directly
        sql_new_cogs = "SELECT SUM(book_unit_cost) FROM payments WHERE status = 'paid' AND book_id IS NOT NULL"
        params_new_cogs = []
        if date_from:
            sql_new_cogs += " AND paid_date >= ?"
            params_new_cogs.append(date_from)
        if date_to:
            sql_new_cogs += " AND paid_date <= ?"
            params_new_cogs.append(date_to)
        cursor.execute(sql_new_cogs, params_new_cogs)
        new_cogs = cursor.fetchone()[0] or 0.0

        # 2. Legacy fallback: historical payments recorded before batch migration (book_id IS NULL)
        sql_legacy_cogs = """SELECT SUM(b.purchase_price) FROM payments p
                             JOIN payment_types pt ON p.payment_type_id = pt.id
                             JOIN books b ON p.description LIKE '%' || b.title || '%'
                             WHERE p.status = 'paid' AND pt.name = 'کتاب' AND p.book_id IS NULL"""
        params_leg_cogs = []
        if date_from:
            sql_legacy_cogs += " AND p.paid_date >= ?"
            params_leg_cogs.append(date_from)
        if date_to:
            sql_legacy_cogs += " AND p.paid_date <= ?"
            params_leg_cogs.append(date_to)
        cursor.execute(sql_legacy_cogs, params_leg_cogs)
        legacy_cogs = cursor.fetchone()[0] or 0.0

        book_cogs_cost = new_cogs + legacy_cogs

        # Expenses breakdown by category
        sql_exp = "SELECT category, SUM(amount) FROM expenses WHERE 1=1"
        params_exp = []
        if date_from:
            sql_exp += " AND date >= ?"
            params_exp.append(date_from)
        if date_to:
            sql_exp += " AND date <= ?"
            params_exp.append(date_to)
        sql_exp += " GROUP BY category"

        cursor.execute(sql_exp, params_exp)
        exp_by_cat = {row[0]: row[1] or 0.0 for row in cursor.fetchall()}

        total_expenses = sum(exp_by_cat.values())

        # Total outstanding debt
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status IN ('pending', 'partial')")
        total_outstanding_debt = cursor.fetchone()[0] or 0.0

        conn.close()

        total_book_sales = cat_income.get("کتاب", 0.0)
        book_gross_profit = total_book_sales - book_cogs_cost

        return {
            "total_income": total_income,
            "income_cash": income_by_method["cash"],
            "income_pos": income_by_method["pos"],
            "income_card_to_card": income_by_method["card_to_card"],
            "income_tuition": cat_income.get("شهریه", 0.0),
            "total_book_sales": total_book_sales,
            "book_cogs_cost": book_cogs_cost,
            "book_gross_profit": book_gross_profit,
            "income_other": cat_income.get("هزینه‌های جانبی", 0.0),
            "total_expenses": total_expenses,
            "expenses_breakdown": exp_by_cat,
            "net_income": total_income - total_expenses,
            "total_outstanding_debt": total_outstanding_debt
        }

    def get_book_inventory_financial_report(self, date_from: str = "", date_to: str = "", book_id: Optional[int] = None, status_filter: str = "") -> Dict[str, Any]:
        """
        Calculates book accounting metrics:
        1. Purchase Cost in period
        2. Book Sales Revenue (paid)
        3. COGS for sold books
        4. Gross Profit (Revenue - COGS)
        5. Total Discounts on books
        6. Outstanding Book Receivables (pending/partial)
        7. Current Inventory Value (quantity_remaining * purchase_price)
        Plus detailed purchase batches and sales transactions lists.
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # 1. Purchases in period
        sql_purchases = """
        SELECT bb.*, b.title as book_title
        FROM book_batches bb
        JOIN books b ON bb.book_id = b.id
        WHERE 1=1
        """
        params_pur = []
        if date_from:
            sql_purchases += " AND bb.purchase_date >= ?"
            params_pur.append(date_from)
        if date_to:
            sql_purchases += " AND bb.purchase_date <= ?"
            params_pur.append(date_to)
        if book_id:
            sql_purchases += " AND bb.book_id = ?"
            params_pur.append(book_id)

        sql_purchases += " ORDER BY bb.id DESC"
        cursor.execute(sql_purchases, params_pur)
        purchase_rows = [dict(r) for r in cursor.fetchall()]

        total_purchase_cost = sum(r["quantity_purchased"] * r["purchase_price"] for r in purchase_rows)

        # 2, 3, 4, 5, 6: Book Payments & Sales
        sql_sales = """
        SELECT p.*,
               s.first_name || ' ' || s.last_name as student_name,
               COALESCE(b.title, p.description) as book_title
        FROM payments p
        JOIN students s ON p.student_id = s.id
        LEFT JOIN books b ON p.book_id = b.id
        JOIN payment_types pt ON p.payment_type_id = pt.id
        WHERE (p.book_id IS NOT NULL OR pt.name = 'کتاب')
        """
        params_sales = []
        if date_from:
            sql_sales += " AND p.paid_date >= ?"
            params_sales.append(date_from)
        if date_to:
            sql_sales += " AND p.paid_date <= ?"
            params_sales.append(date_to)
        if book_id:
            sql_sales += " AND p.book_id = ?"
            params_sales.append(book_id)
        if status_filter:
            if status_filter == "paid":
                sql_sales += " AND p.status = 'paid'"
            elif status_filter in ("pending", "partial", "unpaid"):
                sql_sales += " AND p.status IN ('pending', 'partial')"

        sql_sales += " ORDER BY p.paid_date DESC, p.paid_time DESC"
        cursor.execute(sql_sales, params_sales)
        sales_rows = [dict(r) for r in cursor.fetchall()]

        total_book_sales_revenue = 0.0
        total_cogs = 0.0
        total_discounts = 0.0
        total_outstanding_receivables = 0.0

        for r in sales_rows:
            st = r["status"]
            amt = r.get("amount", 0.0) or 0.0
            orig_amt = r.get("original_amount")
            if orig_amt is None:
                orig_amt = amt + (r.get("discount_amount") or 0.0)
            disc_amt = max(0.0, orig_amt - amt)
            unit_cost = r.get("book_unit_cost") if r.get("book_unit_cost") is not None else 0.0

            r["discount_total"] = disc_amt
            r["unit_cost"] = unit_cost
            r["transaction_profit"] = (amt - unit_cost) if st == "paid" else 0.0

            if st == "paid":
                total_book_sales_revenue += amt
                total_cogs += unit_cost
                total_discounts += disc_amt
            else:
                total_outstanding_receivables += amt

        book_gross_profit = total_book_sales_revenue - total_cogs

        # 7. Current Remaining Inventory Value (current state, un-filtered by date)
        sql_val = """
        SELECT SUM(quantity_remaining * purchase_price)
        FROM book_batches
        WHERE 1=1
        """
        params_val = []
        if book_id:
            sql_val += " AND book_id = ?"
            params_val.append(book_id)
        cursor.execute(sql_val, params_val)
        current_inventory_value = cursor.fetchone()[0] or 0.0

        conn.close()

        return {
            "total_purchase_cost": total_purchase_cost,
            "total_book_sales_revenue": total_book_sales_revenue,
            "total_cogs": total_cogs,
            "book_gross_profit": book_gross_profit,
            "total_discounts": total_discounts,
            "total_outstanding_receivables": total_outstanding_receivables,
            "current_inventory_value": current_inventory_value,
            "purchase_batches": purchase_rows,
            "sales_transactions": sales_rows
        }
