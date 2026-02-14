import os
import fitz
import docx
import shutil
import hashlib
import pymupdf4llm  
import pandas as pd
from pathlib import Path
from rich.progress import track

class ResumeExtractor:
    def __init__(self) -> None:
        # Focuses on these 3 formats.
        self.supported = {'.pdf', '.docx', '.txt'}

    def get_hash(self, file_path) -> str:
        """
        Creates a unique ID based on file CONTENT, not file NAME.
        This solves the 'Split Brain' problem.
        """
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files efficiently
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def _extract_pdf(self, file_path) -> tuple:
        """
        Attempt 1: Markdown (Best for AI, preserves tables).
        Attempt 2: Raw Text (Ugly but reliable fallback).
        """
        # --- ATTEMPT 1: Markdown (The "Smart" Way) ---
        try:
            md_text = pymupdf4llm.to_markdown(file_path)
            # If it found a good amount of text, return it
            if len(md_text.strip()) > 50:
                return md_text, "markdown_pdf"
        except Exception:
            pass # Markdown failed, proceed to fallback

        # --- ATTEMPT 2: Raw Text (The "Reliable" Way) ---
        try:
            doc = fitz.open(file_path)
            raw_text = ""
            for page in doc:
                raw_text += page.get_text()
            
            # Check if even raw extraction failed
            if len(raw_text.strip()) < 50:
                return None, "error_image_pdf"
            
            return raw_text, "raw_text_fallback"
            
        except Exception as e:
            print(f"   [Error] PDF Fail: {file_path} - {e}")
            return None, "error_pdf"

    def _extract_docx(self, file_path) -> tuple:
        """
        Fallback for Word Documents.
        """
        try:
            doc = docx.Document(file_path)
            # Add double newlines to simulate paragraphs for the LLM
            text = "\n\n".join([p.text for p in doc.paragraphs])
            
            if len(text.strip()) < 50:
                return None, "error_empty_docx"
                
            return text, "native_docx"
        except Exception:
            return None, "error_docx"

    def _extract_txt(self, file_path) -> tuple:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
                return text, "native_txt"
        except Exception:
            return None, "error_txt"

    def _quarantine_file(self, file_path, reason) -> None:
        """
        Moves problematic files (Corrupt, Image-only, or Unknown format)
        to a 'data/quarantine' folder for manual review.
        """
        # 1. Ensure the quarantine directory exists
        quarantine_dir = Path("data/quarantine")
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        # 2. Define the destination
        dest_path = quarantine_dir / file_path.name

        # 3. Move the file
        try:
            print(f"   🚫 Quarantining {file_path.name} (Reason: {reason})")
            # shutil.move handles the physical move of the file
            shutil.move(str(file_path), str(dest_path))
        except Exception as e:
            print(f"   [Error] Could not quarantine file: {e}")

    def run(self, source_folder, output_file) -> pd.DataFrame:
        data = []
        folder = Path(source_folder)
        
        # Ensure the output folder exists (e.g., data/result/)
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Get all supported files
        files = [f for f in folder.iterdir() if f.suffix.lower() in self.supported]
        print(f"🏛️  The Gate: Processing {len(files)} resumes from '{source_folder}'...")
        quarantined = 0
        seen_hashes = set()
        for f in track(files, description="[green]Extracting Resumes..."):
            # 1. Identity: Create the Immutable Hash
            try:
                file_hash = self.get_hash(f)
                if file_hash in seen_hashes:
                    self._quarantine_file(f, "Duplicate Content (MD5 Match)")
                    continue
                seen_hashes.add(file_hash)
            except Exception as e:
                self._quarantine_file(f, f"Hash Read Error: {e}")
                continue

            ext = f.suffix.lower()
            text = None
            method = "unknown"

            # 2. Extraction Strategy
            if ext == '.pdf':
                text, method = self._extract_pdf(f)
            elif ext == '.docx':
                text, method = self._extract_docx(f)
            elif ext == '.txt':
                text, method = self._extract_txt(f)

            # 3. Quality Gate & Quarantine Logic
            if not text or len(text.strip()) < 50:
                try:
                    self._quarantine_file(f, "Empty or Image-based PDF (Text < 50 chars)")
                except Exception as e:
                    # to prevent it from entering the database.
                    print(f" ❌ Unable to move file {f.name} to quarantine: {e}")
                
                    quarantined += 1
                    continue # CRITICAL: This must happen even if the 'move' failed.

            # If extraction failed specifically (method returned error flag)
            if "error" in method:
                self._quarantine_file(f, f"Extraction Failed ({method})")
                quarantined += 1
                continue

            # 4. Store the Valid Data
            data.append({
                "id": file_hash,
                "file_name": f.name,
                "file_type": ext,
                "extraction_method": method,
                "raw_text": text  # Storing RAW text
            })

        # 5. Save
        if data:
            df = pd.DataFrame(data)
            # Remove duplicates based on hash (Double submission protection)
            df = df.drop_duplicates(subset=['id'])
            
            df.to_parquet(output_file, index=False)
            
            print(f"✅ Extraction Complete.")
            print(f"   - Processed: {len(files)}")
            print(f"   - Duplicates: {len(files) - len(df) + quarantined}")
            print(f"   - Quarantined: {quarantined}")
            print(f"   - Survivors: {len(df)}")
            print(f"   - Saved to: {output_file}")
            return df
        else:
            print("❌ No valid candidates found. Check 'data/quarantine'.")
            return None

if __name__ == "__main__":
    
    SOURCE_DIR = "data/resumes"
    OUTPUT_FILE = "data/result/candidates.parquet"
    
    extractor = ResumeExtractor()
    extractor.run(SOURCE_DIR, OUTPUT_FILE)