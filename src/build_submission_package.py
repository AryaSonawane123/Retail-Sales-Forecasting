"""
src/build_submission_package.py
-------------------------------
Creates a complete, ready-to-upload Project Submission Package containing:
1. Executive Project Report (PDF)
2. Comprehensive Technical Documentation (PDF + Markdown)
3. Jupyter Notebook (.ipynb)
4. Project Submission Summary & Form Template (TXT)
5. Zip archive for one-click upload to Google Drive
"""

import os
import shutil
import zipfile
from fpdf import FPDF
from fpdf.enums import XPos, YPos

def generate_documentation_pdf(md_path, pdf_path):
    class DocPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(100, 116, 139)
            self.cell(0, 8, "VAIDSYS INTERNSHIP - PROJECT 1: RETAIL SALES FORECASTING", new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
            self.cell(0, 8, f"Page {self.page_no()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
            self.set_draw_color(203, 213, 225)
            self.line(10, 18, 200, 18)
            self.ln(4)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 10, "Vaidsys Technologies - Project Submission Documentation", align="C")

    pdf = DocPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "Retail Sales Forecasting", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(59, 130, 246)
    pdf.cell(0, 7, "Comprehensive Technical Documentation & Project Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, "Author / Intern: Arya Sonawane | Organization: Vaidsys Technologies | Date: September 2026", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    pdf.set_text_color(30, 41, 59)
    in_code_block = False

    def sanitize(t):
        return (t.replace("≥", ">=")
                 .replace("≤", "<=")
                 .replace("≈", "~=")
                 .replace("²", "2")
                 .replace("—", "-")
                 .replace("–", "-")
                 .replace("’", "'")
                 .replace("‘", "'")
                 .replace('“', '"')
                 .replace('”', '"')
                 .replace("•", "-")
                 .replace("✅", "[x]")
                 .replace("📊", "[data]")
                 .replace("💡", "[tip]")
                 .replace("🎯", "[goal]")
                 .replace("🧠", "[ml]")
                 .replace("🏗", "[arch]")
                 .replace("⚡", "[fast]")
                 .replace("▶", ">")
                 .encode("latin-1", "replace")
                 .decode("latin-1"))

    for line in lines:
        raw = sanitize(line.rstrip())
        if not raw:
            pdf.ln(2)
            continue
        
        # Skip top markdown h1 / h2 already rendered
        if raw.startswith("# Retail Sales Forecasting") or raw.startswith("## Comprehensive Project Report"):
            continue
        if raw.startswith("**Author") or raw.startswith("**Project:") or raw.startswith("**Date:") or raw.startswith("**Status:"):
            continue
        if raw.startswith("---"):
            pdf.set_draw_color(226, 232, 240)
            pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
            pdf.ln(4)
            continue

        # Headers
        if raw.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(0, 7, raw[3:].strip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
        elif raw.startswith("### "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 6, raw[4:].strip(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 41, 59)
        elif raw.startswith("|"):
            # Table formatting
            cells = [c.strip() for c in raw.split("|")[1:-1]]
            if not cells or all(c.startswith("-") or c.startswith(":") for c in cells):
                continue
            pdf.set_font("Helvetica", "B" if "Product" in raw or "Objective" in raw or "Metric" in raw else "", 7.5)
            w = 190 / len(cells)
            for c in cells:
                clean_txt = c.replace("**", "").replace("$", "").replace("\\ge", ">=").replace("\\le", "<=").replace("\\text{", "").replace("}", "")
                pdf.cell(w, 5, clean_txt[:28], 1, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")
            pdf.ln()
            pdf.set_font("Helvetica", "", 9)
        elif raw.startswith("- ") or raw.startswith("* "):
            bullet = raw[2:].replace("**", "").replace("`", "")
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(5, 5, "-", 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align="R")
            pdf.multi_cell(185, 4.5, bullet)
        elif raw.startswith("1. ") or raw.startswith("2. ") or raw.startswith("3. ") or raw.startswith("4. "):
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(6, 5, raw[:3], 0, new_x=XPos.RIGHT, new_y=YPos.TOP, align="L")
            pdf.multi_cell(184, 4.5, raw[3:].replace("**", "").replace("`", ""))
        else:
            clean_line = raw.replace("**", "").replace("`", "").replace("$$", "").replace("$", "")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(190, 4.5, clean_line)

    pdf.output(pdf_path)
    print(f"[package] Generated Documentation PDF -> {pdf_path}")

def build_package():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sub_dir = os.path.join(root, "Project_Submission_Documentation")
    os.makedirs(sub_dir, exist_ok=True)

    # 1. Compile Documentation PDF from Markdown
    md_report = os.path.join(root, "reports", "FINAL_PROJECT_REPORT.md")
    doc_pdf = os.path.join(sub_dir, "Retail_Sales_Forecasting_Comprehensive_Documentation.pdf")
    generate_documentation_pdf(md_report, doc_pdf)

    # 2. Copy Executive PDF Report
    exec_pdf = os.path.join(root, "reports", "Retail_Sales_Forecasting_Executive_Report.pdf")
    if os.path.exists(exec_pdf):
        shutil.copy2(exec_pdf, os.path.join(sub_dir, "Retail_Sales_Forecasting_Executive_Report.pdf"))

    # 3. Copy Markdown Report
    shutil.copy2(md_report, os.path.join(sub_dir, "Retail_Sales_Forecasting_Project_Report.md"))

    # 4. Copy Jupyter Notebook
    nb_file = os.path.join(root, "notebooks", "retail_sales_forecasting.ipynb")
    if os.path.exists(nb_file):
        shutil.copy2(nb_file, os.path.join(sub_dir, "Retail_Sales_Forecasting_Analysis.ipynb"))

    # 5. Copy Readme
    readme_file = os.path.join(root, "README.md")
    if os.path.exists(readme_file):
        shutil.copy2(readme_file, os.path.join(sub_dir, "README.md"))

    # 6. Copy High-res Visualizations
    charts_dir = os.path.join(sub_dir, "Visualizations")
    os.makedirs(charts_dir, exist_ok=True)
    assets_dir = os.path.join(root, "reports", "assets")
    if os.path.exists(assets_dir):
        for f in os.listdir(assets_dir):
            if f.endswith(".png"):
                shutil.copy2(os.path.join(assets_dir, f), os.path.join(charts_dir, f))

    # 7. Write Submission Metadata / Form Text
    meta_txt = os.path.join(sub_dir, "PROJECT_SUBMISSION_DETAILS.txt")
    with open(meta_txt, "w", encoding="utf-8") as f:
        f.write("""================================================================================
VAIDSYS TECHNOLOGIES INTERNSHIP - PROJECT SUBMISSION FORM DETAILS
================================================================================

PROJECT DETAILS:
----------------
Project Title: Project 1: Retail Sales Forecasting & Inventory Optimization
Candidate Name: Arya Sonawane
Email: aryasonawane751@gmail.com
Submission Date: September 2026
GitHub Repository: https://github.com/AryaSonawane123/Retail-Sales-Forecasting

PROJECT DESCRIPTION & PROBLEM STATEMENT:
----------------------------------------
A retail company wanted to optimize inventory management by accurately forecasting 
sales for its multi-category products to prevent costly stockouts and overstocking. 
This project designed and deployed an end-to-end Machine Learning pipeline utilizing 
a hybrid ensemble of XGBoost and SARIMA models, achieving 90.28% overall accuracy 
and delivering dynamic Safety Stock and Reorder Point policies.

KEY ACHIEVEMENTS & METRICS:
---------------------------
- Forecasting Accuracy: 90.28% (Exceeded target of >= 90%)
- Overall MAPE: 9.72%
- Overall R2 Score: 0.9753
- Stockout Risk Reduction: 59.3% relative reduction (down to 12.2% average across products)
- Overstock Risk Mitigation: Controlled via dynamic Safety Stock (SS) and Reorder Point (ROP) rules
- Visualizations & Dashboard: Real-time interactive dark-mode analytics console (dashboard/index.html)

INCLUDED SUBMISSION ASSETS:
---------------------------
1. Retail_Sales_Forecasting_Executive_Report.pdf (Formal 3-Page Executive PDF)
2. Retail_Sales_Forecasting_Comprehensive_Documentation.pdf (Full Technical PDF)
3. Retail_Sales_Forecasting_Project_Report.md (Complete Markdown Documentation)
4. Retail_Sales_Forecasting_Analysis.ipynb (Interactive Jupyter Notebook)
5. Visualizations/ (High-resolution accuracy, risk, and feature importance figures)
6. README.md (Setup & architecture instructions)

HOW TO ACCESS DASHBOARD & CODE:
--------------------------------
- GitHub Repo: https://github.com/AryaSonawane123/Retail-Sales-Forecasting
- Dashboard: Simply open `dashboard/index.html` in any web browser.

================================================================================
""")

    # 8. Create Zip Archive for Google Drive Upload
    zip_path = os.path.join(root, "Retail_Sales_Forecasting_Submission_Package.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(sub_dir):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                rel_path = os.path.relpath(file_path, root)
                zipf.write(file_path, rel_path)

    print(f"[package] Created submission directory -> {sub_dir}")
    print(f"[package] Created Google Drive Zip Package -> {zip_path}")

if __name__ == "__main__":
    build_package()
