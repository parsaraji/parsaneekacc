from typing import Dict, Any, List, Optional
from business_logic.formatters import to_persian_digits, gregorian_to_shamsi, format_currency

class InvoiceTemplateRenderer:
    def __init__(self, currency_unit: str = "toman", use_persian_digits: bool = True, page_size: str = "A4"):
        self.currency_unit = currency_unit
        self.use_persian_digits = use_persian_digits
        self.page_size = page_size.upper()

    def render_batch_html(self, invoice_data_list: List[Dict[str, Any]]) -> str:
        """
        Renders a multi-page HTML document containing up to 5 invoices per page.
        Each row uses HTML <table> for 2-column side-by-side rendering in QTextDocument:
          - Right/Wider column (68%): Student's Copy (رسید دانش‌آموز)
          - Left/Narrower column (30%): Institute's Archive Stub (بایگانی آموزشگاه)
        Rows are separated by horizontal dashed cut lines.
        """
        pages_html = []
        chunk_size = 5

        for page_idx in range(0, len(invoice_data_list), chunk_size):
            page_items = invoice_data_list[page_idx:page_idx + chunk_size]
            pages_html.append(self._render_single_page(page_items))

        page_break_css = "<div style='page-break-after: always;'></div>"
        full_body = page_break_css.join(pages_html)

        font_base = "11px" if self.page_size == "A4" else "9px"
        row_height = "160px" if self.page_size == "A4" else "120px"

        html_doc = f"""
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Shabnam', 'Tahoma', 'Arial', sans-serif;
                margin: 0;
                padding: 0;
                font-size: {font_base};
                color: #000000;
                background-color: #ffffff;
            }}
            .invoice-page {{
                width: 100%;
            }}
            .invoice-table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 2px;
            }}
            .invoice-row-td {{
                height: {row_height};
                border-bottom: 1px dashed #7f8c8d;
                vertical-align: top;
                padding: 4px;
            }}
            .student-td {{
                width: 68%;
                border-left: 1px dashed #7f8c8d;
                padding-left: 8px;
                vertical-align: top;
            }}
            .archive-td {{
                width: 30%;
                padding-right: 8px;
                vertical-align: top;
            }}
            .title {{
                font-weight: bold;
                font-size: 1.1em;
                color: #1a5276;
                margin-bottom: 4px;
            }}
            .inner-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .inner-table td {{
                padding: 2px 4px;
                vertical-align: top;
            }}
            .stamp-box {{
                margin-top: 6px;
                border: 1px dotted #bdc3c7;
                height: 30px;
                text-align: center;
                line-height: 30px;
                color: #7f8c8d;
                font-size: 0.85em;
            }}
        </style>
        </head>
        <body>
        {full_body}
        </body>
        </html>
        """
        return html_doc

    def _render_single_page(self, items: List[Dict[str, Any]]) -> str:
        rows_html = []
        for item in items:
            rows_html.append(self._render_single_row(item))

        while len(rows_html) < 5:
            rows_html.append("""
            <table class="invoice-table">
                <tr>
                    <td class="invoice-row-td">
                        <table class="inner-table">
                            <tr>
                                <td class="student-td">&nbsp;</td>
                                <td class="archive-td">&nbsp;</td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
            """)

        return f"<div class='invoice-page'>{''.join(rows_html)}</div>"

    def _render_single_row(self, data: Dict[str, Any]) -> str:
        inv_code = data.get("invoice_code") or data.get("unique_code", "")
        student_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or data.get("student_name", "")
        father_name = data.get("father_name", "-")
        term_name = data.get("term_name", "-")
        payment_type = data.get("payment_type_name", "شهریه")
        amount = data.get("amount", 0.0)
        method = data.get("method", "cash")

        method_map = {"cash": "نقد", "pos": "کارت‌خوان", "card_to_card": "کارت به کارت"}
        method_str = method_map.get(method, method)
        if method == "pos" and data.get("pos_device_label"):
            method_str += f" ({data.get('pos_device_label')})"
        elif method == "card_to_card" and data.get("card_number"):
            method_str += f" ({data.get('card_number')})"

        paid_date = gregorian_to_shamsi(data.get("paid_date", ""))
        paid_time = data.get("paid_time", "")

        fmt_amount = format_currency(amount, self.currency_unit, self.use_persian_digits)

        if self.use_persian_digits:
            inv_code = to_persian_digits(inv_code)
            paid_time = to_persian_digits(paid_time)

        # Student Copy HTML
        student_html = f"""
        <td class="student-td">
            <div class="title">آموزشگاه پارسانیک - رسید پرداخت دانش‌آموز <span style="font-size:0.85em;">(کد رسید: {inv_code})</span></div>
            <table class="inner-table">
                <tr>
                    <td><b>نام دانش‌آموز:</b> {student_name}</td>
                    <td><b>نام پدر:</b> {father_name}</td>
                    <td><b>ترم:</b> {term_name}</td>
                </tr>
                <tr>
                    <td><b>بابت:</b> {payment_type}</td>
                    <td><b>روش پرداخت:</b> {method_str}</td>
                    <td><b>مبلغ:</b> {fmt_amount}</td>
                </tr>
                <tr>
                    <td colspan="2"><b>تاریخ و زمان:</b> {paid_date} - {paid_time}</td>
                    <td><b>کد پیگیری:</b> {to_persian_digits(data.get('card_tracking_code') or data.get('bank_reference_number') or '-')}</td>
                </tr>
            </table>
            <div class="stamp-box">محل امضاء مدیر و مهر آموزشگاه</div>
        </td>
        """

        # Archive Stub HTML
        archive_html = f"""
        <td class="archive-td">
            <div class="title" style="font-size:0.95em;">بایگانی آموزشگاه</div>
            <table class="inner-table" style="font-size:0.9em;">
                <tr><td><b>کد رسید:</b> {inv_code}</td></tr>
                <tr><td><b>نام:</b> {student_name}</td></tr>
                <tr><td><b>بابت:</b> {payment_type} ({term_name})</td></tr>
                <tr><td><b>مبلغ:</b> {fmt_amount}</td></tr>
                <tr><td><b>تاریخ:</b> {paid_date}</td></tr>
            </table>
        </td>
        """

        return f"""
        <table class="invoice-table">
            <tr>
                <td class="invoice-row-td">
                    <table class="inner-table">
                        <tr>
                            {student_html}
                            {archive_html}
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        """
