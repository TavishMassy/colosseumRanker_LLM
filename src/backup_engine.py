import json
import requests
import math

class LocalEngine:
    def __init__(self, model="llama3"):
        self.ollama_url = "http://localhost:11434/api"
        self.model = model
        
        # --- ⚡ SPEED CONFIG ---
        self.max_ctx = 4096       # The Sweet Spot (Fits 5-page resumes)
        self.threads = 7          
        # -----------------------

        # Verify connection
        try:
            requests.get(f"{self.ollama_url}/tags", timeout=1)
            print(f"   🛡️ [Local] Online: {self.model} (Ctx: {self.max_ctx})")
        except:
            print(f"   ⚠️ [Local] Warning: Ollama not reachable at {self.ollama_url}")

    def think(self, prompt_text: str) -> dict:
        """Standard single-shot thinking."""
        return self._generate(prompt_text)

    def think_sandwich(self, header: str, body_text: str, footer: str, overlap: int = 50):
        """
        Smart Slicer: Fits massive text into the 4096 window.
        """
        # 1. Calculate Safe Chunk Size
        # 4096 tokens * ~3 chars/token = ~12,000 chars total capacity
        # Reserve 1,000 chars for Output buffer
        total_capacity = (self.max_ctx * 3) - 1000
        
        reserved_space = len(header) + len(footer) + 200 # +200 for newlines/spacing
        available_for_body = total_capacity - reserved_space
        
        # Safety Check
        if available_for_body < 2000:
            print("   ⚠️ [Local] Warning: Header/Footer are too huge. Shrinking chunk size.")
            available_for_body = 2000 # Force a minimum

        # 2. Slice the Body
        step = available_for_body - overlap
        chunks = []
        for i in range(0, len(body_text), step):
            chunks.append(body_text[i : i + available_for_body])
            
        if len(chunks) > 1:
            print(f"   🛡️ [Local] Resume too long for 4k. Split into {len(chunks)} parts...")
        
        results = []
        
        # 3. Process Each Slice
        for i, chunk in enumerate(chunks):
            # The "Sandwich" Prompt
            full_prompt = f"{header}\n\n--- PART {i+1}/{len(chunks)} ---\n{chunk}\n\n{footer}"
            
            response = self._generate(full_prompt)
            if response: results.append(response)

        # 4. Synthesize if needed
        if len(results) == 1:
            return results[0]
        else:
            return self._synthesize_chunks(header, results, footer)

    def _synthesize_chunks(self, header, partial_results, footer):
        """Merges multiple parts into one final verdict"""
        combined_notes = ""
        for res in partial_results:
            if isinstance(res, dict):
                # Extract narrative or key findings
                narrative = res.get('narrative', res.get('reason', ''))
                combined_notes += f"- {narrative}\n"
        
        final_prompt = f"""
        {header}
        ### AGGREGATED NOTES FROM PARTS:
        {combined_notes}
        ### INSTRUCTION:
        Synthesize these notes into a FINAL decision.
        {footer}
        """
        return self._generate(final_prompt)

    def _generate(self, prompt):
        payload = {
            "model": self.model,
            "prompt": prompt + "\n\nCRITICAL: Return ONLY valid JSON.",
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_ctx": self.max_ctx, # 4096
                "num_predict": -1,       # Infinite output
                "num_thread": self.threads # Force CPU usage
            }
        }
        try:
            # 5-minute timeout is enough for 4k context
            res = requests.post(f"{self.ollama_url}/generate", json=payload, timeout=300)
            if res.status_code == 200:
                return self._clean_json(res.json().get('response', ''))
        except Exception as e:
            print(f"   ❌ [Local] Error: {e}")
        return {}

    def _clean_json(self, text):
        text = text.strip()
        try: return json.loads(text)
        except:
            if "```" in text: text = text.replace("```json", "").replace("```", "")
            start, end = text.find('{'), text.rfind('}')
            if start != -1 and end != -1:
                try: return json.loads(text[start : end+1])
                except: pass
            return {}