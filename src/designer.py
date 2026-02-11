import re
import json
import pandas as pd  # <--- NEW IMPORT
from pathlib import Path
from fpdf import FPDF
from rich.console import Console

console = Console()

# --- CONFIG ---
DATA_DIR = Path("data")
JSON_PATH = DATA_DIR / "result" / "enriched_report.json"
PARQUET_PATH = DATA_DIR / "result" / "candidates_reranked.parquet" # <--- NEW PATH
PDF_PATH = DATA_DIR / "result" / "Shortlist_Dossier.pdf"

class PDFReport(FPDF):
    def header(self):
        # Header appears on all pages
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, 'COLOSSEUM: AI AUDIT', 0, 1, 'C')

    def footer(self):
        self.set_y(-10)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Confidential Report - Page {self.page_no()}', 0, 0, 'C')

    def clean_text(self, text):
        if not text: return ""
        text = str(text)
        replacements = {'\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'", 
                        '\u201c': '"', '\u201d': '"', '\u2022': '*', '…': '...'}
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text.encode('latin-1', 'replace').decode('latin-1')

    def section_header(self, title, r=50, g=50, b=100):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(r, g, b)
        self.set_fill_color(240, 240, 245)
        self.cell(180, 8, f"  {title}", 0, 1, 'L', 1)
        self.ln(3)
        self.set_x(15)

    def candidate_card(self, cand):
        self.add_page()
        
        # --- BACKGROUND & BORDER ---
        self.set_fill_color(250, 250, 252)
        self.rect(5, 5, 200, 287, 'F') 
        self.set_draw_color(40, 40, 60)
        self.rect(10, 10, 190, 277, 'D')

        # --- HEADER ---
        rank = str(cand.get('Rank', '?'))
        name = self.clean_text(cand.get('Name', 'N/A'))
        
        self.set_fill_color(40, 40, 60)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 32)
        self.set_xy(15, 15)
        self.cell(25, 25, f"#{rank}", 0, 0, 'C', 1)

        self.set_text_color(0, 0, 0)
        self.set_xy(45, 15)
        self.set_font('Helvetica', 'B', 22)
        self.cell(100, 12, name, 0, 1, 'L')
        
        self.set_x(45)
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(120, 120, 120)
        source = self.clean_text(cand.get('file_name', 'Source Unknown'))
        self.cell(100, 6, f"File: {source}", 0, 1, 'L')

        # ==========================================================
        #                 THE TWO-COLUMN LAYOUT
        # ==========================================================
        
        self.set_xy(15, 48)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(60, 60, 60)
        
        yoe = str(cand.get('Years Exp', '0'))
        loc = self.clean_text(cand.get('Location', 'Not Disclosed'))
        curr_co = self.clean_text(cand.get('Current Company', 'N/A'))
        notice = (cand.get('Notice Period', 'N/A'))

        if len(curr_co) > 28: curr_co = curr_co[:25] + "..."
        if len(notice) > 28: notice = notice[:25] + "..."
        
        self.cell(90, 6, f"EXPERIENCE: {yoe} YRS", 0, 1, 'L')
        self.set_x(15)
        self.cell(90, 6, f"LOCATION: {loc}", 0, 1, 'L')
        self.set_x(15)
        self.cell(90, 6, f"CURRENT CO: {curr_co}", 0, 1, 'L')
        self.set_x(15)
        self.cell(90, 6, f"NOTICE: {notice}", 0, 1, 'L')
        
        self.ln(4) 
        self.set_x(15)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(50, 50, 150)
        
        email = self.clean_text(str(cand.get('Email', 'N/A'))).strip("[]'")
        phone = self.clean_text(str(cand.get('Phone', 'N/A'))).strip("[]'")
        
        if len(email) > 32: email = email[:29] + "..."
        
        self.cell(90, 6, f"EMAIL: {email}", 0, 1, 'L')
        self.set_x(15)
        self.cell(90, 6, f"PHONE: {phone}", 0, 1, 'L')

        # --- RIGHT COLUMN: LINKS ---
        raw_input = cand.get('Links', cand.get('links', []))
        links_text = str(raw_input)
        url_pattern = r'(https?://[^\s,\'\"\]\[<>|]+|www\.[^\s,\'\"\]\[<>|]+)'
        found_links = re.findall(url_pattern, links_text)
        
        clean_links = []
        for link in found_links:
            link = link.strip(".,'\"").replace("%20", "")
            if link not in clean_links and len(link) > 5:
                clean_links.append(link)

        self.set_xy(115, 48)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(100, 100, 100)
        self.cell(80, 6, "LINKS:", 0, 1, 'L')
        
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(30, 100, 200)
        
        for i, link in enumerate(clean_links[:4]): 
            self.set_xy(115, 54 + (i * 6))
            display_text = link.replace("https://", "").replace("www.", "")
            if len(display_text) > 35:
                display_text = display_text[:32] + "..."
            
            self.write(6, f">> {display_text}", link)

        # ==========================================================
        #                      RISK BOX
        # ==========================================================
        
        risk = str(cand.get('Risk Level', 'Low'))
        if "High" in risk: r, g, b = 180, 0, 0
        elif "Medium" in risk: r, g, b = 200, 140, 10
        else: r, g, b = 0, 120, 0
        
        self.set_xy(15, 95)
        self.set_draw_color(r, g, b)
        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 12)
        self.cell(180, 9, f"  RISK EVALUATION: {risk.upper()}", 0, 1, 'L', 1)
        
        self.set_text_color(r, g, b)
        self.set_font('Helvetica', '', 11)
        reason = self.clean_text(cand.get('Reason', 'No specific flags.'))
        
        start_y = self.get_y()
        self.set_x(15)
        self.multi_cell(180, 6, f"Analysis: {reason}")
        end_y = self.get_y()
        self.rect(15, start_y, 180, max(6, end_y - start_y), 'D')
        
        self.ln(8)

        # --- NARRATIVES ---
        self.section_header("EXECUTIVE SUMMARY & BIO")
        bio = self.clean_text(cand.get('Professional Summary') or cand.get('Bio') or '...')
        self.set_font('Helvetica', '', 11)
        self.set_text_color(0, 0, 0)
        self.multi_cell(180, 6, bio)
        self.ln(6)
        
        raw_verdict = cand.get('Battle Narrative') or cand.get('Verdict') or ''
        verdict = self.clean_text(str(raw_verdict))
        
        if len(verdict) > 5:
            self.section_header("AUDITOR VERDICT")
            self.multi_cell(180, 6, verdict, 0, 'L')
            self.ln(6)

        self.section_header("CORE COMPETENCIES")
        skills = self.clean_text(cand.get('Key Skills', 'N/A'))
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(70, 70, 130)
        self.multi_cell(180, 6, skills)

    def add_executive_summary(self, candidates):
        self.add_page()
        self.set_font('Helvetica', 'B', 20)
        self.cell(0, 20, "SHORTLISTED CANDIDATES", 0, 1, 'C')
        self.ln(5)
        
        self.set_fill_color(40, 40, 60)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 10)
        
        self.cell(12, 12, "RANK", 1, 0, 'C', 1)
        self.cell(75, 12, "CANDIDATE NAME", 1, 0, 'L', 1)
        self.cell(15, 12, "EXP", 1, 0, 'C', 1)
        self.cell(38, 12, "NOTICE", 1, 0, 'C', 1)
        self.cell(50, 12, "RISK EVALUATION", 1, 1, 'C', 1)
        
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', '', 10)
        
        for cand in candidates[:20]:
            raw_notice = str(cand.get('Notice Period', 'N/A'))
            short_notice = raw_notice.split('(')[0].strip()[:15]

            if "-1" in short_notice:
                short_notice = "Unknown"
            
            self.cell(12, 12, str(cand.get('Rank')), 1, 0, 'C')
            self.cell(75, 12, self.clean_text(str(cand.get('Name')))[:35], 1, 0, 'L')
            self.cell(15, 12, f"{cand.get('Years Exp')}Y", 1, 0, 'C')
            self.cell(38, 12, short_notice, 1, 0, 'C')
            
            risk = str(cand.get('Risk Level', 'Low'))
            if "High" in risk: self.set_text_color(180, 0, 0)
            elif "Medium" in risk: self.set_text_color(200, 140, 10)
            else: self.set_text_color(0, 120, 0)
            
            self.cell(50, 12, risk, 1, 1, 'C')
            self.set_text_color(0, 0, 0)

def safety_sort_key(candidate):
    try:
        val = candidate.get('Rank', 999)
        return int(val) if val is not None and str(val).strip() != "" else 999
    except: return 999

# --- 🚀 NEW FALLBACK LOGIC ---
def generate_design_pdf():
    # 1. Try Loading Enriched Audit Data (Phase 7)
    if JSON_PATH.exists():
        console.print(f"[green]✨ Found Enriched Audit Data (JSON). Generating full report...[/green]")
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            candidates = json.load(f)
            
    # 2. Fallback: Try Loading Raw Re-Ranker Data (Phase 4)
    elif PARQUET_PATH.exists():
        console.print(f"[yellow]⚠️ Enriched data missing. Generating preliminary report from Re-Ranker...[/yellow]")
        try:
            df = pd.read_parquet(PARQUET_PATH)
            candidates = []
            
            # Convert Parquet Rows to "Candidate Cards"
            for i, row in df.iterrows():
                # Parse metadata (it might be a string or a dict)
                meta_raw = row.get('metadata', '{}')
                meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
                if not meta: meta = {}
                
                # Retrieve contact info safely
                contact = meta.get('contact', {})
                
                # Map Parquet/Meta fields to PDF fields
                cand = {
                    'Rank': i + 1,
                    'Name': meta.get('full_name', f'Candidate_{i+1}'),
                    'file_name': row.get('file_name', 'N/A'),
                    'Years Exp': meta.get('yoe', 0),
                    'Location': contact.get('city') or meta.get('location', 'N/A'),
                    'Current Company': meta.get('current_company', 'N/A'),
                    'Notice Period': f"{meta.get('notice_period', {}).get('days', '?')} Days",
                    'Email': contact.get('email') or str(row.get('emails', 'N/A')),
                    'Phone': contact.get('phone') or str(row.get('phones', 'N/A')),
                    'Links': contact.get('links') or str(row.get('links', '')),
                    'Risk Level': meta.get('risk_audit', {}).get('level', 'Low'),
                    'Reason': meta.get('risk_audit', {}).get('reason', 'Preliminary Scan Only'),
                    'Professional Summary': meta.get('summary', 'Summary not available yet.'),
                    'Battle Narrative': f"Ranked #{i+1} by AI Scout based on keyword density and vector similarity.",
                    'Key Skills': row.get('regex_skills', '')
                }
                candidates.append(cand)
            
            # Save this converted list as the JSON file so other tools can use it
            with open(JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(candidates, f, indent=4)
            console.print(f"[cyan]💾 Saved fallback JSON to {JSON_PATH}[/cyan]")
            
        except Exception as e:
            console.print(f"[red]❌ Error reading parquet: {e}[/red]")
            return
            
    else:
        console.print("[red]❌ No candidate data found. Run Phase 4 (Re-Ranker) or Phase 7 (Auditor) first.[/red]")
        return

    # Sort and Generate
    candidates.sort(key=safety_sort_key)

    pdf = PDFReport()
    pdf.add_executive_summary(candidates)
    for cand in candidates:
        pdf.candidate_card(cand)
                
    pdf.output(str(PDF_PATH))
    console.print(f"[bold green]🎨 Audit Dossier Generated: {PDF_PATH}[/bold green]")
        
if __name__ == "__main__":
    generate_design_pdf()