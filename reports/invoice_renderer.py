from typing import Dict, Any, List, Optional
from business_logic.formatters import to_persian_digits, gregorian_to_shamsi, format_currency

class InvoiceTemplateRenderer:
    def __init__(self, currency_unit: str = "toman", use_persian_digits: bool = True, page_size: str = "A4"):
        self.currency_unit = currency_unit
        self.use_persian_digits = use_persian_digits
        self.page_size = page_size.upper()

    def render_batch_html(self, invoice_data_list: List[Dict[str, Any]]) -> str:
        """
        Renders a multi-page HTML document containing exactly 5 invoices per page.
        Dimensioned precisely for print accuracy:
          - A4 Portrait (210 x 297 mm): 5 equal rows (~53mm height each)
          - A5 Portrait (148 x 210 mm): 5 equal rows (~38mm height each)
        """
        pages_html = []
        chunk_size = 5

        for page_idx in range(0, len(invoice_data_list), chunk_size):
            page_items = invoice_data_list[page_idx:page_idx + chunk_size]
            pages_html.append(self._render_single_page(page_items))

        page_break_css = "<div style='page-break-after: always; clear: both;'></div>"
        full_body = page_break_css.join(pages_html)

        if self.page_size == "A5":
            font_base = "8.5pt"
            title_font = "9.5pt"
            row_height = "38mm"
            stamp_height = "16px"
            page_css = "@page { size: A5 portrait; margin: 5mm; }"
        else:
            font_base = "10pt"
            title_font = "11pt"
            row_height = "52mm"
            stamp_height = "24px"
            page_css = "@page { size: A4 portrait; margin: 8mm; }"

        html_doc = f"""
        <!DOCTYPE html>
        <html dir="rtl">
        <head>
        <meta charset="utf-8">
        <style>
            {page_css}
            * {{
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Shabnam', 'Tahoma', 'Arial', sans-serif;
                margin: 0;
                padding: 0;
                font-size: {font_base};
                color: #111111;
                background-color: #ffffff;
                direction: rtl;
            }}
            .invoice-page {{
                width: 100%;
                margin: 0 auto;
            }}
            .invoice-table {{
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
            }}
            .invoice-row-td {{
                height: {row_height};
                border-bottom: 1px dashed #555555;
                vertical-align: top;
                padding: 3mm 1mm;
            }}
            .student-td {{
                width: 70%;
                border-left: 1px dashed #555555;
                padding-left: 4mm;
                padding-right: 1mm;
                vertical-align: top;
            }}
            .archive-td {{
                width: 30%;
                padding-right: 4mm;
                padding-left: 1mm;
                vertical-align: top;
            }}
            .header-title {{
                font-weight: bold;
                font-size: {title_font};
                color: #0f3654;
                margin-bottom: 2mm;
                border-bottom: 1px solid #d0d7de;
                padding-bottom: 1mm;
            }}
            .data-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .data-table td {{
                padding: 1.5mm 1mm;
                vertical-align: middle;
            }}
            .stamp-box {{
                margin-top: 2mm;
                border: 1px dotted #888888;
                height: {stamp_height};
                text-align: center;
                line-height: {stamp_height};
                color: #666666;
                font-size: 0.8em;
                border-radius: 3px;
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
                        <table class="data-table">
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
        father_name = data.get("father_name") or "-"
        term_name = data.get("term_name") or "-"
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
        ref_code = data.get('card_tracking_code') or data.get('bank_reference_number') or '-'

        fmt_amount = format_currency(amount, self.currency_unit, self.use_persian_digits)

        if self.use_persian_digits:
            inv_code = to_persian_digits(inv_code)
            paid_time = to_persian_digits(paid_time)
            ref_code = to_persian_digits(ref_code)

        # Student Copy HTML (70% width)
        student_html = f"""
        <td class="student-td">
            <div class="header-title">
                آموزشگاه پارسانیک - رسید پرداخت دانش‌آموز
                <span style="font-size:0.85em; float:left;">شماره: {inv_code}</span>
            </div>
            <table class="data-table">
                <tr>
                    <td style="width:36%;"><b>نام دانش‌آموز:</b> {student_name}</td>
                    <td style="width:30%;"><b>نام پدر:</b> {father_name}</td>
                    <td style="width:34%;"><b>ترم:</b> {term_name}</td>
                </tr>
                <tr>
                    <td><b>بابت:</b> {payment_type}</td>
                    <td><b>روش:</b> {method_str}</td>
                    <td><b>مبلغ:</b> {fmt_amount}</td>
                </tr>
                <tr>
                    <td colspan="2"><b>تاریخ و زمان:</b> {paid_date} - {paid_time}</td>
                    <td><b>کد پیگیری:</b> {ref_code}</td>
                </tr>
            </table>
            <div class="stamp-box">محل امضاء مدیر و مهر آموزشگاه پارسانیک</div>
        </td>
        """

        # Archive Stub HTML (30% width)
        archive_html = f"""
        <td class="archive-td">
            <div class="header-title" style="font-size:0.9em;">بایگانی آموزشگاه</div>
            <table class="data-table" style="font-size:0.88em;">
                <tr><td><b>شماره رسید:</b> {inv_code}</td></tr>
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
                    <table class="data-table">
                        <tr>
                            {student_html}
                            {archive_html}
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        """
