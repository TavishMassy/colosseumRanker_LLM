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
        self.set_font('Helvetica', 'B', 15)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, 'SHORTLIST DOSSIER', 0, 1, 'C')
        self.ln(5)
        self.set_draw_color(200, 200, 200)
        self.line(10, 25, 200, 25)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Confidential Internal Report - Page {self.page_no()}', 0, 0, 'C')

    def clean_text(self, text):
        """Sanitizes text for FPDF (Latin-1)"""
        if not text: return ""
        text = str(text)
        replacements = {
            '\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'", 
            '\u201c': '"', '\u201d': '"', '\u2022': '*', '…': '...'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        # Encode/Decode to strip unsupported characters
        return text.encode('latin-1', 'replace').decode('latin-1')

    def candidate_card(self, cand):
        self.set_fill_color(252, 252, 252)
        self.set_draw_color(220, 220, 220)
        
        start_y = self.get_y()
        # We start with a placeholder rectangle that we'll draw properly later
        # or use a flexible approach. For simplicity, we keep the box logic 
        # but let the internal text flow.
        
        # --- HEADER (Rank and Name) ---
        rank = str(cand.get('Rank', '?'))
        self.set_font('Helvetica', 'B', 24)
        self.set_text_color(218, 165, 32) if rank == "1" else self.set_text_color(100, 100, 100)
        self.set_xy(12, start_y + 5)
        self.cell(20, 15, f"#{rank}", 0, 0, 'C')
        
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', 'B', 14)
        name = self.clean_text(cand.get('Name', 'N/A'))
        self.cell(110, 15, f"{name}", 0, 1, 'L')
        
        # --- NEW: VISION RESCUE BADGE ---
        # Check the 'Is Rescued' flag we added in Auditor Phase 2
        if cand.get('Is Rescued', False):
            self.set_font('Helvetica', 'B', 8)
            self.set_text_color(255, 255, 255) # White text
            self.set_fill_color(100, 50, 200)   # Purple "Vision" brand color
            self.set_xy(150, start_y + 8)
            self.cell(40, 6, "AI VISION RESCUED", 0, 1, 'C', 1)
            # Reset text color for subsequent fields
            self.set_text_color(0, 0, 0)
        else:
            self.ln(15) # Maintain spacing if no badge is present

        # --- ROW 2: STATS ---
        self.set_x(30)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(80, 80, 80)
        loc = self.clean_text(cand.get('Location', 'Unknown'))
        yoe = cand.get('Years Exp', cand.get('Exp', '0'))
        self.cell(40, 6, f"Loc: {loc}", 0, 0)
        self.cell(40, 6, f"Exp: {yoe} Yrs", 0, 0)
        self.write(6, "Risk: ")
        risk = str(cand.get('Risk Level', cand.get('Risk', 'Low')))
        # Color coding risk [cite: 3, 9, 20]
        if "Low" in risk: self.set_text_color(0, 128, 0)
        elif "Medium" in risk: self.set_text_color(218, 165, 32)
        else: self.set_text_color(200, 0, 0)
        self.cell(30, 6, risk, 0, 1)

        # --- ROW 3: FLAG (Dynamic Height) ---
        self.set_x(30)
        self.set_font('Helvetica', 'B', 8)
        if "Low" in risk: self.set_text_color(0, 128, 0)
        elif "Medium" in risk: self.set_text_color(218, 165, 32)
        else: self.set_text_color(200, 0, 0)
        self.write(5, "Flag: ")
        risk_reason = self.clean_text(cand.get('Risk Reason', 'N/A'))
        self.set_font('Helvetica', 'I', 8)
        self.multi_cell(160, 4, risk_reason)
        
        # --- ROW 4: CONTACT INFO ---
        self.ln(2)
        self.set_x(30)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(50, 50, 150)
        email = self.clean_text(cand.get('Email', 'N/A')).replace("['", "").replace("']", "")
        phone = self.clean_text(cand.get('Phone', 'N/A')).replace("['", "").replace("']", "")
        
        # Display contact and filename on the same row
        contact_str = f"E: {email}   P: {phone}"
        self.cell(100, 5, contact_str, 0, 0)
        
        # Filename highlighted in italics
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(120, 120, 120)
        fname = self.clean_text(cand.get('file_name', 'N/A'))
        self.cell(0, 5, f"Source: {fname}", 0, 1, 'R')

        # --- ROW 5: BIO (Dynamic) ---
        self.ln(2)
        self.set_x(15)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(50, 50, 50)
        self.write(5, "Bio: ")
        self.set_font('Helvetica', '', 9)
        bio = self.clean_text(cand.get('Professional Summary', cand.get('Bio', '')))
        self.multi_cell(175, 4.5, bio)

        # --- ROW 6: VERDICT (Dynamic - No fixed Y!) ---
        self.ln(3) # Small dynamic gap
        self.set_x(15)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(0, 0, 0)
        self.write(5, "Verdict: ")
        self.set_font('Helvetica', '', 9)
        narrative = self.clean_text(str(cand.get('Battle Narrative', cand.get('Verdict', ''))))
        self.multi_cell(175, 4.5, narrative.strip())

        # --- ROW 7: SKILLS ---
        self.ln(2)
        self.set_x(15)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(0, 50, 100)
        skills = self.clean_text(cand.get('Key Skills', cand.get('SKILLS', '')))[:140]
        self.cell(180, 4, f"SKILLS: {skills}", 0, 1)

        # Draw the card boundary based on the final Y position
        end_y = self.get_y() + 5
        self.rect(10, start_y, 190, (end_y - start_y), 'D') 
        
        # Reset Y for the next card with a margin
        self.set_y(end_y + 10)

    def add_executive_summary(self, candidates):
        self.add_page()
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, "EXECUTIVE SUMMARY", 0, 1, 'L')
        self.ln(2)
        
        self.set_fill_color(230, 230, 230)
        self.set_font('Helvetica', 'B', 9)
        self.cell(10, 8, "#", 1, 0, 'C', 1)
        self.cell(50, 8, "Name", 1, 0, 'L', 1)
        self.cell(60, 8, "Contact (Email/Phone)", 1, 0, 'L', 1)
        self.cell(20, 8, "Score", 1, 0, 'C', 1)
        self.cell(20, 8, "Exp", 1, 0, 'C', 1)
        self.cell(30, 8, "Risk", 1, 1, 'C', 1)
        
        self.set_font('Helvetica', '', 8)
        for cand in candidates[:15]: 
            self.cell(10, 8, str(cand.get('Rank')), 1, 0, 'C')
            self.cell(50, 8, self.clean_text(str(cand.get('Name')))[:28], 1, 0, 'L')
            
            # Show Contact in summary
            email = self.clean_text(str(cand.get('Email', '')))
            if not email or email == "N/A" or email == "[]": 
                email = self.clean_text(str(cand.get('Phone', '')))
            
            # Clean list artifacts
            email = email.replace("['", "").replace("']", "").replace("[]", "")
            self.cell(60, 8, email[:35], 1, 0, 'L')
            
            try:
                raw_score = float(cand.get('Match Score', 0)) * 100
                score_txt = f"{max(0, raw_score):.0f}%"
            except: score_txt = "0%"
                
            self.cell(20, 8, score_txt, 1, 0, 'C')
            self.cell(20, 8, str(cand.get('Years Exp')), 1, 0, 'C')
            
            risk = str(cand.get('Risk Level', 'Low'))
            self.set_text_color(200, 0, 0) if "High" in risk else self.set_text_color(0, 0, 0)
            self.cell(30, 8, risk, 1, 1, 'C')
            self.set_text_color(0, 0, 0)

def safety_sort_key(candidate):
    """
    Handles sorting of ranks ensuring 999 (unranked) stays at the bottom.
    Converts string ranks to integers safely.
    """
    try:
        val = candidate.get('Rank', 999)
        # Convert to int in case it's a string, default to 999 if None or empty
        return int(val) if val is not None and str(val).strip() != "" else 999
    except (ValueError, TypeError):
        return 999

def generate_design_pdf():
    if not JSON_PATH.exists():
        console.print("[red]❌ No enriched JSON found. Run Auditor first.[/red]")
        return

    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            candidates = json.load(f)
        
        # FIXED: Multi-sort logic
        candidates.sort(key=safety_sort_key)
        
    except Exception as e:
        console.print(f"[red]❌ Error loading JSON: {e}[/red]")
        return

    pdf = PDFReport()
    # Executive Summary page
    pdf.add_executive_summary(candidates)
    
    # Candidate Detail Pages
    count = 0
    for cand in candidates:
        if count % 2 == 0:
            pdf.add_page()
        pdf.candidate_card(cand)
        count += 1
                
    try:
        pdf.output(str(PDF_PATH))
        console.print(f"[bold green]🎨 Designed PDF Report Generated: {PDF_PATH}[/bold green]")
    except Exception as e:
        console.print(f"[red]❌ PDF Generation Failed: {e}[/red]")
        
if __name__ == "__main__":
    generate_design_pdf()