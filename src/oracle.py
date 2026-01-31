import sys
import os
import json
import time
import datetime
import fitz  # PyMuPDF
import pandas as pd
from google import genai
from google.genai import types
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from PIL import Image

# Import configuration from your main Engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine import API_KEY, MODEL_NAME, Requests_Per_Minute, USAGE_FILE, DAILY_LIMIT

# --- CONFIG ---
DATA_DIR = Path("data")
QUARANTINE_DIR = DATA_DIR / "quarantine"
RESUMES_DIR = DATA_DIR / "resumes"  # <--- Target for .txt files
RECOVERED_DIR = DATA_DIR / "result"
MAIN_DB_PATH = RECOVERED_DIR / "candidates.parquet"
BATTLE_SHEET_PATH = DATA_DIR / "job_data" / "battle_sheet.json"

console = Console()

class VisionOracle:
    def __init__(self):
        self.api_key = API_KEY
        self.model_name = MODEL_NAME
        self.usage = self._load_usage()
        
        # Configure Google AI
        if not self.api_key or "AIza" not in self.api_key:
            console.print("[red]⚠️ VisionOracle: Invalid API Key.[/red]")
            self.is_alive = False
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self.is_alive = True
            except Exception as e:
                console.print(f"[red]⚠️ VisionOracle Init Failed: {e}[/red]")
                self.is_alive = False

    def _load_usage(self):
        """Reads the shared log file."""
        today_str = datetime.date.today().isoformat()
        default_data = {"date": today_str, "count": 0}

        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not USAGE_FILE.exists():
            self._save_usage(default_data)
            return default_data

        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            if data.get("date") != today_str:
                self._save_usage(default_data)
                return default_data
            return data
        except:
            return default_data

    def _save_usage(self, data):
        """Writes to the shared log file."""
        try:
            with open(USAGE_FILE, 'w') as f:
                json.dump(data, f)
        except: pass

    def convert_pdf_to_image(self, pdf_path):
        """Converts the first page of a PDF to a PIL Image (Temp File)."""
        try:
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0)  # First page only
            # Zoom x2 for better OCR clarity
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
            
            # Save temp file
            temp_path = QUARANTINE_DIR / f"{pdf_path.stem}_temp.jpg"
            pix.save(str(temp_path))
            doc.close()
            return temp_path
        except Exception as e:
            console.print(f" ❌ PDF Conversion Failed: {e}")
            return None

    def analyze_image(self, image_path, criteria):
        if not self.is_alive: return None

        # Check Limits
        if self.usage['count'] >= DAILY_LIMIT:
            console.print(f"[bold red]🛑 Daily Limit Reached. Stopping.[/bold red]")
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                pil_image = Image.open(image_path)
                
                # --- PROMPT ---
                prompt = f"""
                You are a Recruitment Officer. Look at this visual resume.
                Extract factual data strictly.
                
                JOB CRITERIA (For Context):
                {json.dumps(criteria, indent=2)}
                
                TASK:
                Extract details.
                - "skills": List of technical skills found.
                - "contact": Extract email/phone/links if visible.
                
                RETURN JSON ONLY with this structure:
                {{
                    "name": "Candidate Name",
                    "email": "email string or null",
                    "phone": "phone string or null",
                    "links": ["list", "of", "urls"],
                    "current_role": "Most recent job title",
                    "previous_roles": ["Job Title A", "Job Title B"],
                    "years_experience": "Total Years (Int)",
                    "location": "City, Country",
                    "skills": ["List of skills"],
                    "summary": "Professional summary text"
                }}
                """

                # Pacing
                time.sleep(4) 
                
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, pil_image],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                self.usage['count'] += 1
                self._save_usage(self.usage)
                
                text = response.text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1]
                
                return json.loads(text.strip())

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    wait = 30 * (attempt + 1)
                    console.print(f"[yellow]⏳ Rate Limit. Waiting {wait}s...[/yellow]")
                    time.sleep(wait)
                    continue
                else:
                    console.print(f" ⚠️ Vision Error: {e}")
                    return None
        return None

def run_oracle_rescue():
    """Main execution loop: Extract -> Save .txt to Resumes -> Delete PDF."""
    if not QUARANTINE_DIR.exists(): return

    # 1. Load Battle Sheet
    criteria = {"role": "General", "must_haves": []}
    if BATTLE_SHEET_PATH.exists():
        with open(BATTLE_SHEET_PATH, 'r') as f:
            data = json.load(f)
            criteria = data[0] if isinstance(data, list) else data
    
    # 2. Scan Files
    valid_exts = {'.png', '.jpg', '.jpeg', '.pdf'}
    files = [f for f in QUARANTINE_DIR.iterdir() if f.suffix.lower() in valid_exts and "_temp" not in f.name]

    if not files:
        console.print("[dim]✅ Quarantine is empty.[/dim]")
        return

    console.print(Panel(f"🔮 Oracle Activated. Rescuing {len(files)} files...", border_style="purple"))
    
    oracle = VisionOracle()
    rescued_candidates = []

    for f in track(files, description="Analyzing Visual Resumes..."):
        image_to_process = f
        is_temp = False
        result = None

        # A. Convert PDF to Image (Temp)
        if f.suffix.lower() == '.pdf':
            image_to_process = oracle.convert_pdf_to_image(f)
            is_temp = True
        
        # B. Analyze
        if image_to_process:
            result = oracle.analyze_image(image_to_process, criteria)

        # C. Cleanup Temp Image
        if is_temp and image_to_process and image_to_process.exists():
            image_to_process.unlink()

        # D. Success? Process & Delete
        if result:
            console.print(f"   ✨ Rescued: {f.name} ({result.get('name')})")
            
            # --- CREATE FORMATTED TEXT CONTENT ---
            roles_str = ", ".join(result.get('previous_roles') or [])
            skills_str = ", ".join(result.get('skills') or [])
            links_str = ", ".join(result.get('links') or [])
            
            # This format mimics a good clean resume
            resume_text = (
                f"Candidate Name: {result.get('name')}\n"
                f"Location: {result.get('location')}\n"
                f"Email: {result.get('email', 'N/A')}\n"
                f"Phone: {result.get('phone', 'N/A')}\n"
                f"Links: {links_str}\n\n"
                f"--- PROFESSIONAL SUMMARY ---\n"
                f"{result.get('summary')}\n\n"
                f"--- EXPERIENCE ---\n"
                f"Current Role: {result.get('current_role')}\n"
                f"Years of Experience: {result.get('years_experience')}\n"
                f"Previous Roles: {roles_str}\n\n"
                f"--- SKILLS ---\n"
                f"{skills_str}"
            )

            # --- 1. SAVE AS .TXT TO RESUMES FOLDER ---
            txt_filename = f"{f.stem}_RESCUED.txt"
            txt_path = RESUMES_DIR / txt_filename
            try:
                with open(txt_path, 'w', encoding='utf-8') as txt_file:
                    txt_file.write(resume_text)
                console.print(f"   📝 Saved text version to: {txt_filename}")
                
                # --- 2. DELETE ORIGINAL PDF ---
                f.unlink()
                
                # --- 3. (OPTIONAL) ADD TO DB FOR IMMEDIATE USE ---
                # We still add it to the DB so you don't HAVE to re-run extractor immediately
                flat_record = {
                    "id": f.stem,
                    "file_name": txt_filename, # Point to new txt file
                    "name": result.get("name", "Unknown"),
                    "safe_text": resume_text,
                    "extraction_method": "vision_gemini",
                    "contact_info": {
                        "emails": [result.get('email')] if result.get('email') else [],
                        "phones": [result.get('phone')] if result.get('phone') else [],
                        "links": result.get('links', [])
                    },
                    "meta_role": result.get('current_role'),
                    "meta_yoe": result.get('years_experience')
                }
                rescued_candidates.append(flat_record)

            except Exception as e:
                console.print(f"   ❌ Failed to save text file: {e}")

        else:
            console.print(f"   ☠️ Could not rescue: {f.name} (Staying in Quarantine)")

    # 4. UPDATE DB (So they appear in reports immediately)
    if rescued_candidates:
        new_df = pd.DataFrame(rescued_candidates)
        if MAIN_DB_PATH.exists():
            try:
                existing_df = pd.read_parquet(MAIN_DB_PATH)
                console.print(f"   📥 Merging {len(new_df)} rescued files into existing DB...")
                final_df = pd.concat([existing_df, new_df], ignore_index=True)
            except:
                final_df = new_df
        else:
            final_df = new_df

        RECOVERED_DIR.mkdir(parents=True, exist_ok=True)
        final_df.to_parquet(MAIN_DB_PATH, index=False)
        
        console.print(f"[bold green]✅ Oracle Complete. {len(rescued_candidates)} resumes converted to text and merged.[/bold green]")
        Console.print(f"Current Count: {self.usage['count']}")

    else:
        console.print("[yellow]⚠️ Oracle finished. No files were rescued.[/yellow]")

if __name__ == "__main__":
    run_oracle_rescue()