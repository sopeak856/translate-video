import urllib.request
import urllib.parse
import json
import time
import re

class KhmerTranslator:
    def __init__(self, api_key: str = None, engine: str = "google"):
        """
        engine: 'google' (free web endpoint) or 'gemini' (if API key provided)
        """
        self.api_key = api_key
        self.engine = engine
        self._cache = {}

    def translate(self, text: str, src_lang: str = "auto") -> str:
        text = text.strip()
        if not text:
            return ""

        cache_key = f"{src_lang}:{text}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Use Gemini if key provided and engine is gemini
        if self.engine == "gemini" and self.api_key:
            translated = self._translate_gemini(text, src_lang)
            if translated:
                self._cache[cache_key] = translated
                return translated

        # Default: Google Translate endpoint
        translated = self._translate_google(text, src_lang)
        self._cache[cache_key] = translated
        return translated

    def _translate_google(self, text: str, src_lang: str = "auto", retries: int = 3) -> str:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=" + \
              urllib.parse.quote(src_lang) + "&tl=km&dt=t&q=" + urllib.parse.quote(text)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as response:
                    raw = response.read().decode("utf-8")
                    data = json.loads(raw)
                    result = "".join([part[0] for part in data[0] if part and part[0]])
                    # Cleanup extra spaces around Khmer punctuation if any
                    result = re.sub(r'\s+([។!?])', r'\1', result)
                    return result.strip()
            except Exception as e:
                time.sleep(1.0 * (attempt + 1))
                if attempt == retries - 1:
                    print(f"Translation warning: {e}. Returning original text.")
                    return text
        return text

    def _translate_gemini(self, text: str, src_lang: str) -> str:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
            prompt = (
                "You are an expert movie and story translator into natural Khmer. "
                "Translate the following spoken movie dialogue into smooth, natural, spoken Khmer. "
                "Do not add any explanations or notes, return ONLY the Khmer translation:\n\n"
                f"{text}"
            )
            payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                return res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"Gemini translation error: {e}. Falling back to Google Translate.")
            return self._translate_google(text, src_lang)

    def translate_segments(self, segments: list, src_lang: str = "auto", progress_cb=None) -> list:
        """
        Translates a list of segment dictionaries with 'start', 'end', 'text'.
        Adds 'khmer_text' to each segment.
        """
        total = len(segments)
        for idx, seg in enumerate(segments):
            orig_text = seg.get("text", "").strip()
            if orig_text:
                km = self.translate(orig_text, src_lang=src_lang)
                seg["khmer_text"] = km
            else:
                seg["khmer_text"] = ""
            
            if progress_cb:
                progress_cb(idx + 1, total, orig_text, seg["khmer_text"])
            
            # slight delay to prevent rate-limit
            time.sleep(0.05)
        return segments
