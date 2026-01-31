import json
from pathlib import Path
from fpdf import FPDF
from rich.console import Console

# --- CONFIG ---
DATA_DIR = Path("data")
JSON_PATH = DATA_DIR / "result" / "enriched_report.json"
PDF_PATH = DATA_DIR / "result" / "Agency_Shortlist_Dossier.pdf"

console = Console()

class PDFReport(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 15)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, 'AGENCY CONTROL TOWER: SHORTLIST DOSSIER', 0, 1, 'C')
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
        # --- CARD CONTAINER ---
        self.set_fill_color(252, 252, 252)
        self.set_draw_color(220, 220, 220)
        # Tall card (110mm) to fit Bio, Verdict, and Contact Info
        self.rect(self.get_x(), self.get_y(), 190, 110, 'FD') 
        
        start_y = self.get_y()
        
        # --- ROW 1: RANK & NAME ---
        rank = str(cand.get('Rank', '?'))
        self.set_font('Helvetica', 'B', 24)
        if rank == "1":
            self.set_text_color(218, 165, 32) # Gold
        else:
            self.set_text_color(100, 100, 100)
        self.cell(20, 15, f"#{rank}", 0, 0, 'C')
        
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', 'B', 14)
        name = self.clean_text(cand.get('Name', 'Unknown'))
        
        # Calculate Score (Clamp negative scores to 0 for visuals)
        try:
            raw_score = float(cand.get('Match Score', 0)) * 100
            score_val = max(0, raw_score)
        except:
            score_val = 0
        
        self.cell(110, 15, f"{name}", 0, 0, 'L')
        
        self.set_font('Helvetica', 'B', 12)
        if score_val > 80: self.set_text_color(0, 128, 0)
        elif score_val > 50: self.set_text_color(200, 140, 0)
        else: self.set_text_color(128, 0, 0)
        
        self.cell(60, 15, f"Match: {score_val:.1f}%", 0, 1, 'R')
        
        # --- ROW 2: LOCATION & EXP & RISK ---
        self.set_y(start_y + 14)
        self.set_x(30)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(80, 80, 80)
        
        loc = self.clean_text(cand.get('Location', 'Unknown'))
        yoe = cand.get('Years Exp', '0')
        risk = cand.get('Risk Level', 'Low')
        
        self.cell(60, 6, f"Loc: {loc}", 0, 0)
        self.cell(40, 6, f"Exp: {yoe} Yrs", 0, 0)
        
        risk_color = (0, 128, 0) if "Low" in risk else (200, 0, 0)
        self.set_text_color(*risk_color)
        self.cell(50, 6, f"Risk: {risk}", 0, 1)

        # Risk Reason
        risk_reason = self.clean_text(cand.get('Risk Reason', ''))
        if risk_reason and risk_reason != "N/A" and "High" in risk:
            self.set_x(30)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(200, 0, 0)
            self.cell(0, 4, f"Flag: {risk_reason}", 0, 1)

        # --- ROW 3: CONTACT INFO ---
        self.set_y(start_y + 24)
        self.set_x(30)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(50, 50, 150) # Blueish
        
        email = self.clean_text(cand.get('Email', 'N/A'))
        phone = self.clean_text(cand.get('Phone', 'N/A'))
        
        # Clean up list string artifacts
        email = email.replace("['", "").replace("']", "").replace("[]", "N/A")
        phone = phone.replace("['", "").replace("']", "").replace("[]", "N/A")
        
        self.cell(0, 5, f"E: {email}   P: {phone}", 0, 1)

        # --- ROW 4: BIO ---
        self.ln(2)
        self.set_x(15)
        self.set_text_color(50, 50, 50)
        self.set_font('Helvetica', 'I', 9)
        self.write(5, "Bio: ")
        self.set_font('Helvetica', '', 9)
        bio = self.clean_text(cand.get('Professional Summary', ''))
        self.multi_cell(175, 5, bio)
        
        # --- ROW 5: VERDICT ---
        self.ln(1)
        self.set_x(15)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(0, 0, 0)
        self.write(5, "Verdict: ")
        self.set_font('Helvetica', '', 9)
        narrative = self.clean_text(cand.get('Battle Narrative', ''))
        self.multi_cell(175, 5, narrative)
        
        # --- ROW 6: SKILLS ---
        self.set_y(start_y + 92) # Anchor near bottom
        self.set_x(15)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(0, 50, 100)
        skills = self.clean_text(cand.get('Key Skills', ''))[:140]
        self.cell(180, 4, f"SKILLS: {skills}", 0, 1)

        # --- ROW 7: LINKS ---
        self.set_x(15)
        self.set_font('Helvetica', 'U', 8)
        self.set_text_color(0, 0, 255) # Link Blue
        links = self.clean_text(cand.get('Links', ''))
        
        # Clean list artifacts
        links = links.replace("[", "").replace("]", "").replace("'", "")
        
        if links and links != "N/A":
            self.cell(180, 4, f"LINKS: {links[:100]}", 0, 0)
        
        # Move cursor for next card (Card Height 110 + Margin 5)
        self.set_y(start_y + 115)

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

def generate_design_pdf():
    if not JSON_PATH.exists():
        console.print("[red]❌ No enriched JSON found. Run Auditor (Option 6) first.[/red]")
        return

    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            candidates = json.load(f)
        
        # --- SAFETY SORTING LOGIC ---
        # 1. Low Risk (Safe) candidates go to the TOP.
        # 2. Within groups, maintain Tournament Rank order.
        def safety_sort_key(c):
            risk = c.get('Risk Level', 'High').lower()
            # 0 = Low (Best), 1 = Medium, 2 = High
            risk_score = 0 if 'low' in risk else (1 if 'medium' in risk else 2)
            # Tuple Sort: (Risk Score ASC, Rank ASC)
            return (risk_score, c.get('Rank', 999))
            
        candidates.sort(key=safety_sort_key)
        
    except Exception as e:
        console.print(f"[red]❌ Error loading JSON: {e}[/red]")
        return

    pdf = PDFReport()
    pdf.add_executive_summary(candidates)
    
    pdf.add_page()
    count = 0
    for cand in candidates:
        pdf.candidate_card(cand)
        count += 1
        # 2 Cards per page strictly
        if count % 2 == 0 and count < len(candidates):
             pdf.add_page()
            
    try:
        pdf.output(str(PDF_PATH))
        console.print(f"[bold green]🎨 Designed PDF Report Generated: {PDF_PATH}[/bold green]")
    except Exception as e:
        console.print(f"[red]❌ PDF Generation Failed: {e}[/red]")

if __name__ == "__main__":
    generate_design_pdf()