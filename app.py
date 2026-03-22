import os
import io
import json
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from scraper.maps_scraper import PlaywrightMapsScraper
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def search():
    data        = request.get_json()
    keyword     = data.get("keyword", "").strip()
    location    = data.get("location", "").strip()
    max_results = int(data.get("max_results", os.getenv("MAX_RESULTS", 20)))

    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400

    query = f"{keyword} {location}".strip()

    try:
        scraper = PlaywrightMapsScraper(
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            max_results=max_results,
            timeout=int(os.getenv("SCRAPE_TIMEOUT", 60)),
        )
        results = scraper.search(query)
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export/excel", methods=["POST"])
def export_excel():
    data    = request.get_json()
    results = data.get("results", [])
    keyword = data.get("keyword", "results")

    if not results:
        return jsonify({"error": "No data to export"}), 400

    df = pd.DataFrame(results)
    col_order = ["name", "category", "rating", "reviews", "phone", "address", "website"]
    df = df.reindex(columns=[c for c in col_order if c in df.columns])
    df.columns = [c.title() for c in df.columns]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
        wb = writer.book
        ws = writer.sheets["Results"]

        hdr_fmt = wb.add_format({
            "bold": True, "font_color": "#FFFFFF",
            "bg_color": "#1a1a2e", "border": 1,
            "font_size": 11, "align": "center", "valign": "vcenter"
        })
        cell_fmt = wb.add_format({"font_size": 10, "border": 1, "valign": "vcenter", "text_wrap": True})
        alt_fmt  = wb.add_format({"font_size": 10, "border": 1, "valign": "vcenter", "text_wrap": True, "bg_color": "#f0f4ff"})

        for col_num, col_name in enumerate(df.columns):
            ws.write(0, col_num, col_name, hdr_fmt)

        for row_num in range(1, len(df) + 1):
            fmt = alt_fmt if row_num % 2 == 0 else cell_fmt
            for col_num in range(len(df.columns)):
                val = df.iloc[row_num - 1, col_num]
                ws.write(row_num, col_num, str(val) if pd.notna(val) else "", fmt)

        for i, w in enumerate([30, 20, 8, 10, 15, 40, 30]):
            if i < len(df.columns):
                ws.set_column(i, i, w)
        ws.set_row(0, 25)
        ws.freeze_panes(1, 0)

    output.seek(0)
    fname = f"{keyword.replace(' ', '_')}_results.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fname
    )


@app.route("/api/export/pdf", methods=["POST"])
def export_pdf():
    data    = request.get_json()
    results = data.get("results", [])
    keyword = data.get("keyword", "results")

    if not results:
        return jsonify({"error": "No data to export"}), 400

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4),
        rightMargin=0.5*inch, leftMargin=0.5*inch,
        topMargin=0.6*inch, bottomMargin=0.5*inch
    )
    styles    = getSampleStyleSheet()
    title_sty = ParagraphStyle("T", parent=styles["Heading1"], fontSize=16,
                               textColor=colors.HexColor("#1a1a2e"), spaceAfter=12)
    cell_sty  = ParagraphStyle("C", parent=styles["Normal"], fontSize=8, leading=10)
    hdr_sty   = ParagraphStyle("H", fontSize=9, textColor=colors.white, fontName="Helvetica-Bold")

    elements = [Paragraph(f"Google Maps Results — {keyword}", title_sty), Spacer(1, 0.1*inch)]
    headers  = ["Name", "Category", "Rating", "Reviews", "Phone", "Address"]
    col_widths = [2.2*inch, 1.4*inch, 0.7*inch, 0.8*inch, 1.3*inch, 3.2*inch]

    table_data = [[Paragraph(h, hdr_sty) for h in headers]]
    for r in results:
        table_data.append([
            Paragraph(str(r.get("name", "")),     cell_sty),
            Paragraph(str(r.get("category", "")), cell_sty),
            Paragraph(str(r.get("rating", "")),   cell_sty),
            Paragraph(str(r.get("reviews", "")),  cell_sty),
            Paragraph(str(r.get("phone", "")),    cell_sty),
            Paragraph(str(r.get("address", "")),  cell_sty),
        ])

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#1a1a2e")),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, colors.HexColor("#eef2ff")]),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    elements.append(tbl)
    doc.build(elements)
    output.seek(0)
    fname = f"{keyword.replace(' ', '_')}_results.pdf"
    return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=fname)


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "True") == "True"
    )
