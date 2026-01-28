import json
import requests

class LocalEngine:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3"  # The 8B model that fits your RAM

    def think(self, prompt_text: str) -> dict:
        """
        FALLBACK: Runs locally on CPU via Ollama.
        """
        print("   🛡️ [System] Engaging Local Backup (Ollama)...")
        
        payload = {
            "model": self.model,
            "prompt": prompt_text + "\n\nCRITICAL: Return ONLY valid JSON. No markdown.",
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1, 
                "num_ctx": 2048, #4096 
                "num_thread": 4 #none
            }
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            if response.status_code == 200:
                return self._clean_json(response.json().get('response', ''))
            else:
                print(f"   ❌ [Backup] Error {response.status_code}. Is 'ollama run llama3' active?")
                return None
        except Exception as e:
            print(f"   ❌ [Backup] Connection Failed: {e}")
            return None

    def _clean_json(self, text):
        try:
            if "```json" in text: text = text.replace("```json", "").replace("```", "")
            elif "```" in text: text = text.replace("```", "")
            start, end = text.find('{'), text.rfind('}')
            if start != -1 and end != -1: return json.loads(text[start : end+1])
            return json.loads(text)
        except: return None