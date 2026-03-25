"""
app.py
──────
Flask backend — multi-keyword search, SQLite dedup, 200 results
"""

import os
import io
import json
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from scraper.maps_scraper import PlaywrightMapsScraper
from database.db import filter_and_store, get_all_records, clear_db, init_db
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

load_dotenv()
init_db()   # ensure DB + tables exist on startup

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")


# ── Home ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ── Multi-keyword search ─────────────────────────────────────────────
@app.route("/api/search", methods=["POST"])
def search():
    data        = request.get_json()
    # keywords: list of strings e.g. ["CA in Vaishali Nagar", "CA in Mansarovar"]
    keywords    = data.get("keywords", [])
    max_results = int(data.get("max_results", os.getenv("MAX_RESULTS", 40)))
    max_results = min(max_results, 200)

    # Support legacy single keyword too
    if not keywords:
        kw       = data.get("keyword", "").strip()
        location = data.get("location", "").strip()
        if kw:
            keywords = [f"{kw} {location}".strip()]

    keywords = [k.strip() for k in keywords if k.strip()]

    if not keywords:
        return jsonify({"error": "At least one keyword is required"}), 400

    all_unique   = []
    all_dup      = 0
    all_scraped  = 0
    query_stats  = []

    try:
        scraper = PlaywrightMapsScraper(
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            max_results=max_results,
            timeout=int(os.getenv("SCRAPE_TIMEOUT", 120)),
        )

        for query in keywords:
            raw     = scraper.search(query)
            stats   = filter_and_store(raw, query)

            all_unique  += stats["unique"]
            all_dup     += stats["duplicates_skipped"]
            all_scraped += stats["total_scraped"]

            query_stats.append({
                "query":    query,
                "scraped":  stats["total_scraped"],
                "new":      len(stats["unique"]),
                "skipped":  stats["duplicates_skipped"],
            })

        return jsonify({
            "results":           all_unique,
            "count":             len(all_unique),
            "total_scraped":     all_scraped,
            "duplicates_skipped":all_dup,
            "total_in_db":       all_scraped - all_dup,
            "query_stats":       query_stats,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── DB stats ─────────────────────────────────────────────────────────
@app.route("/api/db/stats")
def db_stats():
    records = get_all_records()
    return jsonify({"total_in_db": len(records)})


# ── Clear DB ─────────────────────────────────────────────────────────
@app.route("/api/db/clear", methods=["POST"])
def db_clear():
    clear_db()
    return jsonify({"message": "Database cleared successfully"})


# ── Export all DB records ─────────────────────────────────────────────
@app.route("/api/export/all/excel", methods=["GET"])
def export_all_excel():
    results = get_all_records()
    if not results:
        return jsonify({"error": "No data in database"}), 400
    return _build_excel(results, "all_results")


@app.route("/api/export/all/pdf", methods=["GET"])
def export_all_pdf():
    results = get_all_records()
    if not results:
        return jsonify({"error": "No data in database"}), 400
    return _build_pdf(results, "all_results")


# ── Export current search results ────────────────────────────────────
@app.route("/api/export/excel", methods=["POST"])
def export_excel():
    data    = request.get_json()
    results = data.get("results", [])
    keyword = data.get("keyword", "results")
    if not results:
        return jsonify({"error": "No data to export"}), 400
    return _build_excel(results, keyword)


@app.route("/api/export/pdf", methods=["POST"])
def export_pdf():
    data    = request.get_json()
    results = data.get("results", [])
    keyword = data.get("keyword", "results")
    if not results:
        return jsonify({"error": "No data to export"}), 400
    return _build_pdf(results, keyword)


# ── Excel builder ─────────────────────────────────────────────────────
def _build_excel(results, label):
    df = pd.DataFrame(results)
    col_order = ["name", "category", "rating", "reviews", "phone", "address", "website", "query", "scraped_at"]
    df = df.reindex(columns=[c for c in col_order if c in df.columns])
    df.columns = [c.replace("_", " ").title() for c in df.columns]

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

        widths = [30, 20, 8, 10, 15, 40, 30, 25, 20]
        for i, w in enumerate(widths[:len(df.columns)]):
            ws.set_column(i, i, w)
        ws.set_row(0, 25)
        ws.freeze_panes(1, 0)

    output.seek(0)
    fname = f"{label.replace(' ', '_')}_results.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=fname
    )


# ── PDF builder ───────────────────────────────────────────────────────
def _build_pdf(results, label):
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4),
        rightMargin=0.4*inch, leftMargin=0.4*inch,
        topMargin=0.5*inch, bottomMargin=0.4*inch
    )
    styles    = getSampleStyleSheet()
    title_sty = ParagraphStyle("T", parent=styles["Heading1"], fontSize=14,
                               textColor=colors.HexColor("#1a1a2e"), spaceAfter=10)
    cell_sty  = ParagraphStyle("C", parent=styles["Normal"], fontSize=7, leading=9)
    hdr_sty   = ParagraphStyle("H", fontSize=8, textColor=colors.white, fontName="Helvetica-Bold")

    elements = [Paragraph(f"Google Maps Results — {label}", title_sty), Spacer(1, 0.1*inch)]
    headers    = ["Name", "Category", "Rating", "Reviews", "Phone", "Address"]
    col_widths = [2.0*inch, 1.3*inch, 0.65*inch, 0.75*inch, 1.3*inch, 3.3*inch]

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
        ("BACKGROUND",     (0,0), (-1,0),  colors.HexColor("#1a1a2e")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#eef2ff")]),
        ("GRID",           (0,0), (-1,-1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",     (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 4),
    ]))
    elements.append(tbl)
    doc.build(elements)
    output.seek(0)
    fname = f"{label.replace(' ', '_')}_results.pdf"
    return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=fname)


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "True") == "True"
    ) 