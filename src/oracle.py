import sys
import os
import fitz  # PyMuPDF
import pandas as pd
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from concurrent.futures import ThreadPoolExecutor

# Import configuration from your main Engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.extractor import ResumeExtractor
from src.engine import Engine

# --- CONFIG ---
DATA_DIR = Path("data")
QUARANTINE_DIR = DATA_DIR / "quarantine"
RESUMES_DIR = DATA_DIR / "resumes" 
RECOVERED_DIR = DATA_DIR / "result"
MAIN_DB_PATH = RECOVERED_DIR / "candidates.parquet"

console = Console()

class VisionOracle:
    def __init__(self, engine):
        self.engine = engine 

    def convert_pdf_to_image(self, pdf_path):
        """Converts first page of PDF to image with x2 zoom for OCR clarity."""
        try:
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0) 
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)) 
            temp_path = QUARANTINE_DIR / f"{pdf_path.stem}_temp.jpg"
            pix.save(str(temp_path))
            doc.close()
            return temp_path
        except Exception as e:
            console.print(f" ❌ PDF Conversion Failed for {pdf_path.name}: {e}")
            return None

def process_single_file(f, oracle, engine):
    """Parallel Worker: Handles preparation, AI Vision, and safety checks."""
    image_to_process = f
    is_temp = False
    
    if f.suffix.lower() == '.pdf':
        image_to_process = oracle.convert_pdf_to_image(f)
        is_temp = True
    
    if not image_to_process or not image_to_process.exists():
        return (f, None)

    prompt = """
    Extract all resume text into clean Markdown format.
    1. # and ## for Headers (Education, Experience)
    2. Use bullet points for lists, - or * for Bullet points.
    3. Maintain column data by using Markdown tables if necessary, use | for Tables.
    Return the result in this JSON format:
    {
        "raw_text": "The full markdown content goes here..."
    }
    STRICT RULE: If the document is NOT a resume, you MUST NOT extract any text. Instead, return exactly this JSON: 
    {
        "raw_text": "N/A"
    }
    """
    result = oracle.engine.see(str(image_to_process), prompt)

    if is_temp and image_to_process.exists():
        image_to_process.unlink()

    if result is None:
        console.print(f"[red]❌ Engine Error: No response for {f.name}[/red]")
        return (f, None)

    if isinstance(result, list) and len(result) > 0:
        result = result[0]

    if isinstance(result, dict):
        if "raw_text" not in result:
            return (f, None)
            
    if result and result.get("raw_text") == "N/A":
        console.print(f"[yellow]🚫 Filtered: {f.name} is not a resume.[/yellow]")
        return (f, None)

    return (f, result)

def run_oracle_rescue():
    if not QUARANTINE_DIR.exists(): return

    engine = Engine()
    oracle = VisionOracle(engine)
    
    files = [f for f in QUARANTINE_DIR.iterdir() if f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.pdf'} and "_temp" not in f.name]

    if not files:
        console.print("[dim]✅ Quarantine is empty.[/dim]")
        return

    console.print(Panel(f"🔮 Oracle Parallel Core: Rescuing {len(files)} files...", border_style="purple"))
    rescued_candidates = []

    num_workers = min(10, len(files)) if files else 1
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_single_file, f, oracle, engine) for f in files]
        
        for future in track(futures, description="Parallel Processing..."):
            try:
                f_original, result = future.result()
            except Exception as e:
                console.print(f"[red]❌ Thread Crash: {e}[/red]")
                continue

            # Deduplication
            txt_filename = f"{f_original.stem}.txt"
            txt_path = RESUMES_DIR / txt_filename
            
            if txt_path.exists():
                console.print(f" [dim]♻️  {f_original.name} already exists. Cleaning quarantine.[/dim]")
                f_original.unlink()
                continue

            if not result or not result.get("raw_text"):
                console.print(f"[yellow]⚠️ Data Error: {f_original.name} has no content.[/yellow]")
                continue

            try:
                with open(txt_path, 'w', encoding='utf-8') as txt_file:
                    txt_file.write(result.get("raw_text"))
                                
                rescued_candidates.append({
                    "id": ResumeExtractor.get_hash(txt_file),
                    "file_name": f_original.name,
                    "file_type": f_original.suffix.lower(),
                    "extraction_method": "VLM",
                    "raw_text": result.get("raw_text")
                })

                f_original.unlink() 

            except Exception as e:
                console.print(f"   ❌ Save Failed for {f_original.name}: {e}")

    # Final DB Sync
    if rescued_candidates:
        new_df = pd.DataFrame(rescued_candidates)
        if MAIN_DB_PATH.exists():
            final_df = pd.concat([pd.read_parquet(MAIN_DB_PATH), new_df], ignore_index=True)
        else:
            final_df = new_df

        RECOVERED_DIR.mkdir(parents=True, exist_ok=True)
        final_df.to_parquet(MAIN_DB_PATH, index=False)
        console.print(f"[bold green]✅ Oracle Complete. Daily Tokens Used: {engine.usage['total_tokens']}[/bold green]")

if __name__ == "__main__":
    run_oracle_rescue()