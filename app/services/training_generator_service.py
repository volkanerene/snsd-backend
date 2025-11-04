"""
Training Generator Service using OpenAI GPT
Generates training scripts from incident reports
"""
import os
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI


class TrainingGeneratorService:
    """Service for generating training content from incident reports using GPT"""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4-turbo-preview"  # or "gpt-3.5-turbo" for cost savings

    async def generate_training_script(
        self,
        prompt: str,
        incident_reports: List[Dict[str, Any]],
        target_duration_minutes: int = 5,
        language: str = "tr"  # Turkish by default
    ) -> Dict[str, Any]:
        """
        Generate a training script from incident reports

        Args:
            prompt: User's specific request/topic
            incident_reports: List of incident report data
            target_duration_minutes: Target video duration
            language: Language code (tr, en, etc.)

        Returns:
            Dict with generated script and metadata
        """

        # Build context from incident reports
        reports_context = self._build_reports_context(incident_reports)

        # Build system prompt
        system_prompt = self._build_system_prompt(language, target_duration_minutes)

        # Build user prompt
        user_prompt = f"""
Konu: {prompt}

Aşağıdaki olay raporlarından yararlanarak bir eğitim içeriği hazırla:

{reports_context}

Lütfen bu raporlardan öğrenilen dersleri ve önlemleri vurgulayan, pratik ve eğitici bir senaryo oluştur.
"""

        try:
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            generated_text = response.choices[0].message.content

            # Estimate word count and duration
            word_count = len(generated_text.split())
            estimated_duration = word_count / 150  # ~150 words per minute

            return {
                "script": generated_text,
                "word_count": word_count,
                "estimated_duration_minutes": round(estimated_duration, 1),
                "model_used": self.model,
                "reports_used_count": len(incident_reports),
                "language": language
            }

        except Exception as e:
            raise Exception(f"Failed to generate training script: {str(e)}")

    def _build_system_prompt(self, language: str, target_duration: int) -> str:
        """Build the system prompt for GPT"""

        if language == "tr":
            return f"""Sen bir iş güvenliği eğitim uzmanısın. Görevin, gerçek olay raporlarından yola çıkarak
etkili ve öğretici eğitim senaryoları hazırlamak.

Senaryolar:
- Yaklaşık {target_duration} dakikalık konuşma süresi için tasarlanmalı (~{target_duration * 150} kelime)
- Net ve anlaşılır Türkçe kullan
- Teknik terimleri açıkla
- Gerçek olaylardan somut örnekler ver
- Önleyici tedbirleri vurgula
- Çalışanları motive edecek pozitif bir ton kullan
- Giriş, gelişme ve sonuç bölümlerini içersin

Format:
- Başlık ile başla
- Giriş: Konunun önemini vurgula
- Ana İçerik: Olay örnekleri ve dersler
- Sonuç: Önemli noktaları özetle ve harekete geçir
"""
        else:
            return f"""You are a workplace safety training expert. Your task is to create
effective and educational training scenarios based on real incident reports.

Scenarios should:
- Be designed for approximately {target_duration} minutes of speech (~{target_duration * 150} words)
- Use clear and understandable language
- Explain technical terms
- Provide concrete examples from real incidents
- Highlight preventive measures
- Use a positive tone that motivates employees
- Include introduction, body, and conclusion sections

Format:
- Start with a title
- Introduction: Emphasize the importance of the topic
- Main Content: Incident examples and lessons learned
- Conclusion: Summarize key points and call to action
"""

    def _build_reports_context(self, incident_reports: List[Dict[str, Any]]) -> str:
        """Build context string from incident reports"""

        if not incident_reports:
            return "Olay raporu bulunmamaktadır."

        context_parts = []

        for idx, report in enumerate(incident_reports[:10], 1):  # Limit to 10 reports
            summary = report.get('summary') or report.get('text_content', '')[:500]
            incident_type = report.get('incident_type', 'Bilinmiyor')
            severity = report.get('severity', 'Bilinmiyor')

            context_parts.append(f"""
Rapor {idx}:
- Olay Tipi: {incident_type}
- Şiddet Seviyesi: {severity}
- Özet: {summary}
""")

        return "\n".join(context_parts)

    async def retrieve_relevant_reports(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant incident reports based on query
        Uses simple keyword matching for now (can be enhanced with embeddings)

        Args:
            query: Search query
            limit: Maximum number of reports to return

        Returns:
            List of relevant incident reports
        """
        from app.db.supabase_client import supabase

        # For now, use simple text search
        # TODO: Implement semantic search with embeddings

        response = supabase.table("marcel_gpt_incident_reports") \
            .select("*") \
            .eq("tenant_id", self.tenant_id) \
            .eq("processing_status", "completed") \
            .limit(limit) \
            .execute()

        return response.data or []

    async def extract_pdf_text(self, pdf_content: bytes) -> str:
        """
        Extract text from PDF content
        Uses PyPDF2 for extraction

        Args:
            pdf_content: PDF file bytes

        Returns:
            Extracted text
        """
        try:
            import io
            from PyPDF2 import PdfReader

            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)

            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)

        except Exception as e:
            raise Exception(f"Failed to extract PDF text: {str(e)}")

    async def summarize_incident_report(self, text_content: str) -> Dict[str, Any]:
        """
        Generate summary and extract metadata from incident report

        Args:
            text_content: Full text of the incident report

        Returns:
            Dict with summary, incident_type, severity, keywords
        """

        prompt = f"""
Aşağıdaki olay raporunu analiz et ve şu bilgileri çıkar:

1. Kısa özet (2-3 cümle)
2. Olay tipi (örn: Düşme, Yanma, Elektrik, vb.)
3. Şiddet seviyesi (Düşük, Orta, Yüksek)
4. Anahtar kelimeler (5-10 kelime, virgülle ayrılmış)

Rapor:
{text_content[:3000]}

Lütfen yanıtını şu formatta ver:
ÖZET: ...
TİP: ...
ŞİDDET: ...
KELIMELER: ...
"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # Use cheaper model for analysis
                messages=[
                    {"role": "system", "content": "Sen bir iş güvenliği analisti yardımcısısın."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            result_text = response.choices[0].message.content

            # Parse the response
            lines = result_text.split('\n')
            result = {
                'summary': '',
                'incident_type': '',
                'severity': '',
                'keywords': []
            }

            for line in lines:
                if line.startswith('ÖZET:'):
                    result['summary'] = line.replace('ÖZET:', '').strip()
                elif line.startswith('TİP:'):
                    result['incident_type'] = line.replace('TİP:', '').strip()
                elif line.startswith('ŞİDDET:'):
                    result['severity'] = line.replace('ŞİDDET:', '').strip()
                elif line.startswith('KELIMELER:'):
                    keywords_str = line.replace('KELIMELER:', '').strip()
                    result['keywords'] = [k.strip() for k in keywords_str.split(',')]

            return result

        except Exception as e:
            raise Exception(f"Failed to summarize incident report: {str(e)}")
