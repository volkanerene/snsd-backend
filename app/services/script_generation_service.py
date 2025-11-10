"""
Script Generation Service
Generates video scripts using ChatGPT for education topics, PDFs, and incident reports
"""

import json
import asyncio
from typing import Optional, Dict, Any, List
from app.config import settings

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes"""
    if PyPDF2 is None:
        raise ValueError("PyPDF2 not installed. Install with: pip install PyPDF2")

    from io import BytesIO
    pdf_file = BytesIO(file_bytes)
    pdf_reader = PyPDF2.PdfReader(pdf_file)

    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"

    return text.strip()


def _build_education_prompt(topic: str) -> str:
    """Build prompt for education script generation"""
    return f"""You are a professional training video scriptwriter specializing in safety,
health, and business training content.

Create a compelling and engaging video script for the following educational topic:

TOPIC: {topic}

The script should:
1. Have a clear introduction that grabs attention
2. Present 3-5 key learning points with examples
3. Include practical takeaways
4. End with a memorable conclusion

Format the script naturally as dialogue/narration that would be read by a speaking avatar.
Keep sentences concise and engaging. Use a professional but friendly tone.

Write ONLY the script content, no metadata or stage directions."""


def _build_pdf_script_prompt(pdf_content: str) -> str:
    """Build prompt for PDF-based script generation"""
    return f"""You are a professional training video scriptwriter. Your task is to convert
educational material into an engaging video script.

Here is the educational content from a PDF:

---
{pdf_content[:3000]}
---

Create a video script that:
1. Extracts the most important information from this content
2. Presents it in an engaging, conversational way
3. Includes practical examples or applications
4. Has a clear beginning, middle, and end

The script will be narrated by an AI avatar, so write it naturally as if someone is speaking.
Keep sentences concise. Make it suitable for a 2-3 minute video.

Write ONLY the script content, no metadata."""


def _build_incident_script_prompt(
    what_happened: str,
    why_did_it_happen: Optional[str],
    what_did_they_learn: Optional[str],
    ask_yourself_or_crew: Optional[str],
    similar_incident: Optional[Dict[str, Any]] = None
) -> str:
    """Build prompt for incident-based script generation"""

    similar_incident_text = ""
    if similar_incident:
        similar_incident_text = f"""

Here's a similar incident from our database for context:
{similar_incident.get('title', 'Similar Incident')}
- What happened: {similar_incident.get('what_happened', '')}
- Why it happened: {similar_incident.get('why_did_it_happen', '')}
- What we learned: {similar_incident.get('what_did_they_learn', '')}"""

    return f"""You are a safety training speaker creating a brief safety conversation script based on a real incident in our company.

NEW INCIDENT DETAILS:
What happened: {what_happened}
Why it happened: {why_did_it_happen or 'N/A'}
What we can learn: {what_did_they_learn or 'N/A'}{similar_incident_text}

Create a natural spoken conversation (NOT a video script with scenes, music, or stage directions).
Start with: "My team, I want to share something important. We recently had an incident at our company, and I'd like to tell you about a similar situation that happened before..."

Then:
1. Briefly describe the similar incident from our database
2. Explain what caused it and what we learned
3. Connect it to the current situation

Keep it natural, conversational, and sincere. Maximum 1500 characters. No scene descriptions, no stage directions, no reflection questions.
Write ONLY the spoken dialogue - nothing else."""


async def generate_script_from_topic(topic: str) -> Dict[str, Any]:
    """Generate a video script from an educational topic"""
    try:
        if not settings.OPENAI_API_KEY:
            return {
                "success": False,
                "error": "OpenAI API key not configured"
            }

        if OpenAI is None:
            return {
                "success": False,
                "error": "OpenAI library not installed"
            }

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = _build_education_prompt(topic)

        print(f"[Script Gen] Generating script from topic: {topic[:50]}...")

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional training video scriptwriter."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )

        script = response.choices[0].message.content.strip()

        return {
            "success": True,
            "script": script,
            "source": "topic",
            "generated_at": str(__import__('datetime').datetime.now(
                __import__('datetime').timezone.utc
            ).isoformat())
        }

    except Exception as e:
        print(f"[Script Gen] Error: {str(e)}")
        return {
            "success": False,
            "error": f"Script generation failed: {str(e)}"
        }


async def generate_script_from_pdf(pdf_content: str) -> Dict[str, Any]:
    """Generate a video script from PDF content"""
    try:
        if not settings.OPENAI_API_KEY:
            return {
                "success": False,
                "error": "OpenAI API key not configured"
            }

        if OpenAI is None:
            return {
                "success": False,
                "error": "OpenAI library not installed"
            }

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = _build_pdf_script_prompt(pdf_content)

        print(f"[Script Gen] Generating script from PDF ({len(pdf_content)} chars)...")

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional training video scriptwriter."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )

        script = response.choices[0].message.content.strip()

        return {
            "success": True,
            "script": script,
            "source": "pdf",
            "generated_at": str(__import__('datetime').datetime.now(
                __import__('datetime').timezone.utc
            ).isoformat())
        }

    except Exception as e:
        print(f"[Script Gen] Error: {str(e)}")
        return {
            "success": False,
            "error": f"PDF script generation failed: {str(e)}"
        }


def _generate_training_questions(
    what_happened: str,
    why_did_it_happen: Optional[str],
    what_did_they_learn: Optional[str]
) -> Dict[str, Any]:
    """Generate 3 training questions: 2 multiple choice, 1 text-based"""
    try:
        if OpenAI is None or not settings.OPENAI_API_KEY:
            return {"success": False, "questions": []}

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = f"""Based on this incident, generate exactly 3 training questions.

INCIDENT:
What happened: {what_happened}
Why it happened: {why_did_it_happen or 'N/A'}
What we learned: {what_did_they_learn or 'N/A'}

Generate exactly this JSON format (no markdown, pure JSON):
{{
  "questions": [
    {{
      "type": "multiple_choice",
      "question": "question text here?",
      "options": ["option A", "option B", "option C", "option D"],
      "correct_answer": 0
    }},
    {{
      "type": "multiple_choice",
      "question": "another question?",
      "options": ["option A", "option B", "option C", "option D"],
      "correct_answer": 1
    }},
    {{
      "type": "text",
      "question": "What would you do differently in this situation?"
    }}
  ]
}}

Keep questions professional and related to the incident. Make them assessment-focused."""

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a training assessment expert. Generate only valid JSON with no additional text."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=800
        )

        response_text = response.choices[0].message.content.strip()

        # Parse JSON response
        questions_data = json.loads(response_text)
        return {
            "success": True,
            "questions": questions_data.get("questions", [])
        }

    except Exception as e:
        print(f"[Training Questions] Error: {str(e)}")
        return {"success": False, "questions": []}


async def generate_script_from_incident(
    what_happened: str,
    why_did_it_happen: Optional[str] = None,
    what_did_they_learn: Optional[str] = None,
    ask_yourself_or_crew: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a video script from incident details.
    Optionally finds similar incidents from database for context.
    """
    try:
        if not settings.OPENAI_API_KEY:
            return {
                "success": False,
                "error": "OpenAI API key not configured"
            }

        if OpenAI is None:
            return {
                "success": False,
                "error": "OpenAI library not installed"
            }

        # Find similar incident from database if tenant_id provided
        similar_incident = None
        if tenant_id:
            similar_incident = _find_similar_incident(
                what_happened,
                tenant_id
            )
            if similar_incident:
                print(f"[Script Gen] Found similar incident: {similar_incident.get('title', 'N/A')}")

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = _build_incident_script_prompt(
            what_happened,
            why_did_it_happen,
            what_did_they_learn,
            ask_yourself_or_crew,
            similar_incident
        )

        print(f"[Script Gen] Generating incident script...")

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a safety training speaker. Create natural, conversational dialogue only - no scene descriptions, no stage directions, no visual cues."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=500
        )

        script = response.choices[0].message.content.strip()

        # Generate training questions
        questions_result = _generate_training_questions(
            what_happened,
            why_did_it_happen,
            what_did_they_learn
        )

        return {
            "success": True,
            "script": script,
            "source": "incident",
            "questions": questions_result.get("questions", []),
            "similar_incident_id": similar_incident.get("id") if similar_incident else None,
            "generated_at": str(__import__('datetime').datetime.now(
                __import__('datetime').timezone.utc
            ).isoformat())
        }

    except Exception as e:
        print(f"[Script Gen] Error: {str(e)}")
        return {
            "success": False,
            "error": f"Incident script generation failed: {str(e)}"
        }


def _find_similar_incident(
    description: str,
    tenant_id: str
) -> Optional[Dict[str, Any]]:
    """
    Find the most similar incident from database using semantic similarity.
    Searches both tenant-specific incidents and global templates.
    For now, using simple keyword matching. Can be enhanced with embeddings later.
    """
    try:
        from app.db.supabase_client import supabase

        # Get incidents for tenant + global templates
        # First get tenant-specific incidents
        res_tenant = supabase.table("incident_report_dialogues").select(
            "id, title, what_happened, why_did_it_happen, what_did_they_learn"
        ).eq("tenant_id", tenant_id).execute()

        # Then get global template incidents (is_template=true, tenant_id=NULL)
        res_templates = supabase.table("incident_report_dialogues").select(
            "id, title, what_happened, why_did_it_happen, what_did_they_learn"
        ).eq("is_template", True).is_("tenant_id", "null").execute()

        incidents = []
        if hasattr(res_tenant, 'data') and res_tenant.data:
            incidents.extend(res_tenant.data)
        if hasattr(res_templates, 'data') and res_templates.data:
            incidents.extend(res_templates.data)

        if not incidents:
            return None

        # Simple keyword matching: count common words
        description_words = set(description.lower().split())

        best_match = None
        best_score = 0

        for incident in incidents:
            incident_text = (
                incident.get("what_happened", "").lower() + " " +
                incident.get("why_did_it_happen", "").lower()
            )
            incident_words = set(incident_text.split())

            # Calculate Jaccard similarity
            if incident_words and description_words:
                intersection = len(description_words & incident_words)
                score = intersection / len(description_words | incident_words)

                if score > best_score:
                    best_score = score
                    best_match = incident

        # Only return if similarity > 0.1 (at least some common words)
        return best_match if best_score > 0.1 else None

    except Exception as e:
        print(f"[Script Gen] Error finding similar incident: {str(e)}")
        return None
