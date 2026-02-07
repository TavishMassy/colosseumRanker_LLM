import re
import json
from pathlib import Path
from fpdf import FPDF
from rich.console import Console

console = Console()

# --- CONFIG ---
DATA_DIR = Path("data")
JSON_PATH = DATA_DIR / "result" / "enriched_report.json"
PDF_PATH = DATA_DIR / "result" / "Shortlist_Dossier.pdf"

class PDFReport(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'B', 10)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, 'COLOSSEUM PROJECT: INTERNAL AUDIT', 0, 1, 'R')

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Confidential Internal Report - Page {self.page_no()}', 0, 0, 'C')

    def clean_text(self, text):
        if not text: return ""
        text = str(text)
        replacements = {'\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'", 
                        '\u201c': '"', '\u201d': '"', '\u2022': '*', '…': '...'}
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text.encode('latin-1', 'replace').decode('latin-1')

    def section_header(self, title, r=50, g=50, b=100):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(r, g, b)
        self.set_fill_color(240, 240, 245)
        self.cell(180, 8, f"  {title}", 0, 1, 'L', 1)
        self.ln(2)
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
        self.set_font('Helvetica', 'B', 28)
        self.set_xy(15, 15)
        self.cell(25, 25, f"#{rank}", 0, 0, 'C', 1)

        self.set_text_color(0, 0, 0)
        self.set_xy(45, 15)
        self.set_font('Helvetica', 'B', 20)
        self.cell(100, 12, name, 0, 1, 'L')
        
        self.set_x(45)
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(120, 120, 120)
        source = self.clean_text(cand.get('file_name', 'Source Unknown'))
        self.cell(100, 6, f"File: {source}", 0, 1, 'L')

        # ==========================================================
        #                 THE TWO-COLUMN LAYOUT
        # ==========================================================
        
        # --- LEFT COLUMN: VITALS (X=15) ---
        self.set_xy(15, 45)
        self.set_font('Helvetica', 'B', 9.5)
        self.set_text_color(60, 60, 60)
        
        yoe = str(cand.get('Years Exp', '0'))
        loc = self.clean_text(cand.get('Location', 'Not Disclosed'))
        
        # Vitals
        self.cell(90, 5, f"EXPERIENCE: {yoe} YRS", 0, 1, 'L')
        self.set_x(15)
        self.cell(90, 5, f"LOCATION: {loc}", 0, 1, 'L')
        
        # Contact
        self.ln(2)
        self.set_x(15)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(50, 50, 150)
        
        email = self.clean_text(str(cand.get('Email', 'N/A'))).strip("[]'")
        phone = self.clean_text(str(cand.get('Phone', 'N/A'))).strip("[]'")
        
        # Truncate extremely long emails to fit the column
        if len(email) > 35: email = email[:32] + "..."
        
        self.cell(90, 5, f"EMAIL: {email}", 0, 1, 'L')
        self.set_x(15)
        self.cell(90, 5, f"PHONE: {phone}", 0, 1, 'L')

        # --- RIGHT COLUMN: LINKS (X=110) ---
        # We process links first using the Regex Fix
        raw_input = cand.get('Links', cand.get('links', []))
        links_text = str(raw_input)
        url_pattern = r'(https?://[^\s,\'\"\]\[<>|]+|www\.[^\s,\'\"\]\[<>|]+)'
        found_links = re.findall(url_pattern, links_text)
        
        clean_links = []
        for link in found_links:
            link = link.strip(".,'\"").replace("%20", "")
            if link not in clean_links and len(link) > 5:
                clean_links.append(link)

        # Draw the Links Column
        # Start Y at same height as Vitals (45)
        current_y = 45 
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(30, 100, 200) # Blue
        
        # Header for Links
        self.set_xy(110, 45)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(100, 100, 100) # Grey Header
        self.cell(80, 5, "LINKS:", 0, 1, 'L')
        
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(30, 100, 200) # Back to Blue
        
        for i, link in enumerate(clean_links[:4]): # Show up to 4 links
            self.set_xy(110, 50 + (i * 5))
            # Truncate link text for display, but keep full link clickable
            display_text = link.replace("https://", "").replace("www.", "")
            if len(display_text) > 40:
                display_text = display_text[:37] + "..."
            
            self.write(5, f"{display_text}", link)

        # ==========================================================
        #                 RISK BOX (Below Columns)
        # ==========================================================
        
        risk = str(cand.get('Risk Level', 'Low'))
        if "High" in risk: r, g, b = 180, 0, 0
        elif "Medium" in risk: r, g, b = 200, 140, 10
        else: r, g, b = 0, 120, 0
        
        # Move down to Y=80 (safe clearance below columns)
        self.set_xy(15, 80)
        self.set_draw_color(r, g, b)
        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 11)
        self.cell(180, 8, f"  RISK EVALUATION: {risk.upper()}", 0, 1, 'L', 1)
        
        self.set_text_color(r, g, b)
        self.set_font('Helvetica', '', 10)
        reason = self.clean_text(cand.get('Reason', 'No specific flags.'))
        
        start_y = self.get_y()
        self.set_x(15)
        self.multi_cell(180, 5, f"Analysis: {reason}")
        end_y = self.get_y()
        self.rect(15, start_y, 180, max(5, end_y - start_y), 'D')
        
        self.ln(8)

        # --- NARRATIVES ---
        self.section_header("EXECUTIVE SUMMARY & BIO")
        bio = self.clean_text(cand.get('Professional Summary', cand.get('Bio', '...')))
        self.set_font('Helvetica', '', 10.5)
        self.set_text_color(0, 0, 0)
        self.multi_cell(180, 5.5, bio)
        self.ln(5)

        self.section_header("AUDITOR VERDICT")
        verdict = self.clean_text(str(cand.get('Battle Narrative', cand.get('Verdict', '...'))))
        self.multi_cell(180, 5.5, verdict)
        self.ln(5)

        self.section_header("CORE COMPETENCIES")
        skills = self.clean_text(cand.get('Key Skills', 'N/A'))
        self.set_font('Helvetica', 'B', 9.5)
        self.set_text_color(70, 70, 130)
        self.multi_cell(180, 5, skills)

    def add_executive_summary(self, candidates):
        self.add_page()
        self.set_font('Helvetica', 'B', 18)
        self.cell(0, 20, "COLOSSEUM EXECUTIVE SUMMARY", 0, 1, 'C')
        self.ln(5)
        
        # Header
        self.set_fill_color(40, 40, 60)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 10)
        self.cell(15, 10, "RANK", 1, 0, 'C', 1)
        self.cell(85, 10, "CANDIDATE NAME", 1, 0, 'L', 1)
        self.cell(20, 10, "EXP", 1, 0, 'C', 1)
        self.cell(60, 10, "RISK EVALUATION", 1, 1, 'C', 1)
        
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', '', 10)
        for cand in candidates[:20]:
            self.cell(15, 10, str(cand.get('Rank')), 1, 0, 'C')
            self.cell(85, 10, self.clean_text(str(cand.get('Name')))[:45], 1, 0, 'L')
            self.cell(20, 10, f"{cand.get('Years Exp')}Y", 1, 0, 'C')
            
            risk = str(cand.get('Risk Level', 'Low'))
            if "High" in risk: self.set_text_color(180, 0, 0)
            elif "Medium" in risk: r, g, b = 200, 140, 10
            else: r, g, b = 0, 120, 0
            self.cell(60, 10, risk, 1, 1, 'C')
            self.set_text_color(0, 0, 0)

def safety_sort_key(candidate):
    try:
        val = candidate.get('Rank', 999)
        return int(val) if val is not None and str(val).strip() != "" else 999
    except: return 999

def generate_design_pdf():
    if not JSON_PATH.exists(): return
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        candidates = json.load(f)
    candidates.sort(key=safety_sort_key)

    pdf = PDFReport()
    pdf.add_executive_summary(candidates)
    for cand in candidates:
        pdf.candidate_card(cand)
                
    pdf.output(str(PDF_PATH))
    console.print(f"[bold green]🎨 Audit Dossier Generated: {PDF_PATH}[/bold green]")
        
if __name__ == "__main__":
    generate_design_pdf()