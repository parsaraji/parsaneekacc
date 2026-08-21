from typing import List, Dict, Any, Tuple
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
        Computes total payments paid, total discount given, total pending/debt for a student.
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

        # Total discounts
        cursor.execute(
            "SELECT SUM(discount_amount + (amount * discount_percent / 100.0)) FROM payments WHERE student_id = ?",
            (student_id,)
        )
        total_discount = cursor.fetchone()[0] or 0.0

        conn.close()

        # Balance convention: negative means debt, positive means credit.
        # Pending payment entries represent expected balance / debt.
        return {
            "student_id": student_id,
            "total_paid": total_paid,
            "total_pending_debt": total_pending,
            "total_discount": total_discount,
            "net_balance": total_paid - total_pending
        }

    def get_institute_financial_summary(self, date_from: str = "", date_to: str = "") -> Dict[str, Any]:
        """
        Computes total income by payment method, total expenses, and net profit.
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

        # Expenses
        sql_exp = "SELECT SUM(amount) FROM expenses WHERE 1=1"
        params_exp = []
        if date_from:
            sql_exp += " AND date >= ?"
            params_exp.append(date_from)
        if date_to:
            sql_exp += " AND date <= ?"
            params_exp.append(date_to)

        cursor.execute(sql_exp, params_exp)
        total_expenses = cursor.fetchone()[0] or 0.0

        # Total outstanding debt
        cursor.execute("SELECT SUM(amount) FROM payments WHERE status IN ('pending', 'partial')")
        total_outstanding_debt = cursor.fetchone()[0] or 0.0

        conn.close()

        return {
            "total_income": total_income,
            "income_cash": income_by_method["cash"],
            "income_pos": income_by_method["pos"],
            "income_card_to_card": income_by_method["card_to_card"],
            "total_expenses": total_expenses,
            "net_income": total_income - total_expenses,
            "total_outstanding_debt": total_outstanding_debt
        }
