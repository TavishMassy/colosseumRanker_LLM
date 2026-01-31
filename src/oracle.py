import sys
import os
import json
import time
import datetime
import fitz  
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
RECOVERED_DIR = DATA_DIR / "result"
MAIN_DB_PATH = RECOVERED_DIR / "candidates.parquet"
BATTLE_SHEET_PATH = DATA_DIR / "job_data" / "battle_sheet.json"

console = Console()

class VisionOracle:
    def __init__(self):
        self.api_key = API_KEY
        self.model_name = MODEL_NAME
        
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

        # Ensure directory exists
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)

        if not USAGE_FILE.exists():
            self._save_usage(default_data)
            return default_data

        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            
            # Reset if new day
            if data.get("date") != today_str:
                self._save_usage(default_data)
                return default_data
            
            return data
        except:
            return default_data

    def _save_usage(self, data):
        """Writes to the shared log file."""
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f)

    def convert_pdf_to_image(self, pdf_path):
        """Converts the first page of a PDF to a PIL Image."""
        try:
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0)  # First page only
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # 2x Zoom
            
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

        try:
            pil_image = Image.open(image_path)
            
            # --- UPDATED PROMPT FOR VECTOR-FRIENDLY DATA ---
            prompt = f"""
            You are a Recruitment Officer. Look at this visual resume.
            Extract factual data strictly.
            
            JOB CRITERIA (For Context):
            {json.dumps(criteria, indent=2)}
            
            TASK:
            Extract specific details. 
            - "previous_roles": A list of job titles held.
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
            time.sleep(60 / Requests_Per_Minute) 
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
            console.print(f" ⚠️ Vision Error: {e}")
            return None

def run_oracle_rescue():
    """Main execution loop with Merge & Delete."""
    if not QUARANTINE_DIR.exists():
        return

    # 1. Load Battle Sheet
    if not BATTLE_SHEET_PATH.exists():
        console.print("[red]❌ Battle Sheet missing! Cannot grade resumes.[/red]")
        return
    
    with open(BATTLE_SHEET_PATH, 'r') as f:
        battle_data = json.load(f)
        criteria = battle_data[0] if isinstance(battle_data, list) else battle_data
    
    # 2. Scan Files (Exclude temp files)
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

        # A. Handle PDF
        if f.suffix.lower() == '.pdf':
            image_to_process = oracle.convert_pdf_to_image(f)
            is_temp = True
        
        # B. Analyze (if conversion worked or file was already image)
        if image_to_process:
            result = oracle.analyze_image(image_to_process, criteria)

        # C. Cleanup Temp Image immediately
        if is_temp and image_to_process and image_to_process.exists():
            image_to_process.unlink()

        # D. Success? Store Data
        if result:
            console.print(f"   ✨ Rescued: {f.name} ({result.get('name')})")
            
            contact_info_dict = {
                "emails": [result.get('email')] if result.get('email') else [],
                "phones": [result.get('phone')] if result.get('phone') else [],
                "links": result.get('links', [])
            }

            roles_str = ", ".join(result.get('previous_roles') or [])
            skills_str = ", ".join(result.get('skills') or [])
            rich_text = (
                f"Name: {result.get('name')}\n"
                f"Current Role: {result.get('current_role')}\n"
                f"Location: {result.get('location')}\n"
                f"Experience: {result.get('years_experience')} years\n"
                f"Past Roles: {roles_str}\n"
                f"Skills: {skills_str}\n"
                f"Summary: {result.get('summary')}"
            )

            flat_record = {
                "id": f.stem,
                "file_name": f.name,
                "name": result.get("name", "Unknown"),
                # We save the "Rich Text" as safe_text so Scout embeds meaningful data
                "safe_text": rich_text,
                "extraction_method": "vision_gemini",
                "contact_info": contact_info_dict,
                
                # We can store the raw fields too for metadata if needed
                "meta_role": result.get('current_role'),
                "meta_yoe": result.get('years_experience')
            }
            rescued_candidates.append(flat_record)
        else:
            console.print(f"   ☠️ Could not rescue: {f.name}")

    # 3. MERGE & DELETE ORIGINAL FILES
    if rescued_candidates:
        new_df = pd.DataFrame(rescued_candidates)
        
        # Load existing if available
        if MAIN_DB_PATH.exists():
            try:
                existing_df = pd.read_parquet(MAIN_DB_PATH)
                console.print(f"   📥 Merging {len(new_df)} rescued files into existing {len(existing_df)} candidates...")
                final_df = pd.concat([existing_df, new_df], ignore_index=True)
            except Exception as e:
                console.print(f"   ⚠️ Could not read existing DB ({e}). Creating new.")
                final_df = new_df
        else:
            final_df = new_df

        # Save merged DB
        RECOVERED_DIR.mkdir(parents=True, exist_ok=True)
        final_df.to_parquet(MAIN_DB_PATH, index=False)
        
        # 4. DELETE SUCCESSFULLY RESCUED FILES FROM QUARANTINE
        console.print("   🧹 Cleaning up Quarantine...")
        for item in rescued_candidates:
            file_path = QUARANTINE_DIR / item['file_name']
            if file_path.exists():
                file_path.unlink()
        
        console.print(f"[bold green]✅ Success! Quarantine cleaned. Database updated.[/bold green]")
    else:
        console.print("[yellow]⚠️ Oracle finished, but no files were recoverable.[/yellow]")

if __name__ == "__main__":
    run_oracle_rescue()