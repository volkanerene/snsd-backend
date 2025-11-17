"""
Script Generation Service
Generates video scripts using ChatGPT for education topics, PDFs, and incident reports
"""

import json
import asyncio
import base64
from io import BytesIO
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

try:
    from pptx import Presentation
except ImportError:
    Presentation = None


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes"""
    if PyPDF2 is None:
        raise ValueError("PyPDF2 not installed. Install with: pip install PyPDF2")

    pdf_file = BytesIO(file_bytes)
    pdf_reader = PyPDF2.PdfReader(pdf_file)

    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"

    return text.strip()


def _extract_text_from_pptx(file_bytes: bytes) -> str:
    """Extract text from PPTX bytes"""
    if Presentation is None:
        raise ValueError("python-pptx not installed. Install with: pip install python-pptx")

    presentation = Presentation(BytesIO(file_bytes))
    texts: List[str] = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                texts.append(shape.text)
    return "\n".join(texts).strip()


def _parse_chat_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"text", "output_text"} and item.get("text"):
                    parts.append(item["text"])
        return "\n".join(parts)
    return ""


async def _extract_text_from_image(file_bytes: bytes, mime_type: str) -> str:
    """Use OpenAI vision to extract text from images"""
    if OpenAI is None or not settings.OPENAI_API_KEY:
        raise ValueError("OpenAI API key not configured for image extraction")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{encoded}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You read images and return the exact text content. Respond with plain text only."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all readable text from this document image."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ],
        max_tokens=700,
    )

    content = response.choices[0].message.content
    extracted = _parse_chat_message_content(content).strip()
    if not extracted:
        raise ValueError("Could not extract text from image")
    return extracted


async def extract_text_from_document(
    filename: str,
    content_type: Optional[str],
    file_bytes: bytes
) -> str:
    """Determine document type and extract text accordingly"""
    lowered = (filename or "").lower()
    content_type = content_type or ""

    if lowered.endswith(".pdf") or content_type == "application/pdf":
        return _extract_text_from_pdf(file_bytes)

    if lowered.endswith((".pptx", ".ppt")) or content_type in {
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    }:
        return _extract_text_from_pptx(file_bytes)

    if content_type.startswith("image/") or lowered.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return await _extract_text_from_image(file_bytes, content_type or "image/png")

    raise ValueError(f"Unsupported file type for {filename or 'document'}")


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

IMPORTANT FORMAT RULES:
- Write the entire response as spoken narration or dialogue only.
- Do NOT include headings, bullet points, scene directions, or stage notes.
- No brackets, numbered lists, or meta commentary. Every line should sound like someone speaking naturally.

Keep sentences concise and engaging. Use a professional but friendly tone."""


def _build_pdf_script_prompt(pdf_content: str) -> str:
    """Build prompt for PDF-based script generation"""
    return f"""You are a professional training video scriptwriter. Your task is to convert
educational material into an engaging video script.

Here is the educational content from a PDF (trimmed for length):

---
{pdf_content[:3000]}
---

Create a video script that:
1. Extracts the most important information from this content
2. Presents it in an engaging, conversational way
3. Includes practical examples or applications
4. Has a clear beginning, middle, and end

STRICT FORMAT RULES:
- Output MUST be pure spoken dialogue/narration with complete sentences.
- Do NOT add headings, bullet points, numbered lists, scene directions, or stage notes.
- Avoid meta phrases like "In this script" or "Scene 1". Every line should sound like the narrator speaking directly to the audience.

Keep it suitable for a 2-3 minute video and write ONLY the spoken script."""


def _build_incident_script_prompt(
    what_happened: str,
    why_did_it_happen: Optional[str],
    what_did_they_learn: Optional[str],
    ask_yourself_or_crew: Optional[str],
    similar_incident: Optional[Dict[str, Any]] = None,
    process_safety_violations: Optional[str] = None,
    life_saving_rule_violations: Optional[str] = None,
    preventive_actions: Optional[str] = None,
    reference_case: Optional[str] = None
) -> str:
    """Build prompt for incident-based script generation with 8-part format

    8-Part Structure:
    1. Introduction
    2. What happened?
    3. Why did it happen?
    4. Reference case from industry
    5. What should be done to prevent?
    6. Process Safety Fundamental violation
    7. Life Saving Rule violation
    8. Suggestion and Close Out
    """

    similar_incident_text = ""
    if similar_incident:
        similar_incident_text = f"""{similar_incident.get('reference_case_title', similar_incident.get('title', 'Reference Case'))}
{similar_incident.get('reference_case_description', '')}
Year: {similar_incident.get('reference_case_year', 'Unknown')}"""

    reference_case_final = reference_case or similar_incident_text or "N/A"

    return f"""You are a safety training speaker. Create a learning-from-incident video script.
Follow this 8-part structure with SPECIFIC, MEASURABLE details (NOT generic):

1. INTRODUCTION (1-2 sentences) - Engage audience and introduce the specific incident topic

2. WHAT HAPPENED (3-5 sentences) - Describe EXACTLY what occurred with:
   - Specific equipment names, serial numbers, or component names (from provided data)
   - Measurable data ONLY from the incident information - DO NOT invent numbers or specifications
   - Sequence of events in exact chronological order with times/durations
   - Specific consequences that are documented (injuries, environmental damage, costs - only if provided)

3. WHY DID IT HAPPEN (2-4 sentences) - Root cause analysis explaining:
   - The EXACT failure mechanism (not "failure" but "what specifically failed": seal degradation, corrosion, design flaw)
   - Contributing factors with their specific mechanism (not "maintenance was poor" but "seal was not inspected for <specific degradation>")
   - The SPECIFIC system or procedure that broke down and how

4. REFERENCE CASE FROM INDUSTRY (3-4 sentences) - MANDATORY FORMAT:
   - State incident name/platform + year + location (example: "Thistle Field, 1989, North Sea")
   - MUST explain the SPECIFIC MECHANISM SIMILARITY: "Like [reference incident], this incident also had [EXACT MECHANISM in common]"
   - Show how the root cause parallels the current incident mechanically
   - DO NOT use generic phrases like "similar incident" - explain the specific parallel
   - DO NOT mention current incident by location/name if reference is already clear

5. WHAT SHOULD BE DONE (3-5 sentences) - Preventive actions with MEASURABLE criteria:
   - Each action MUST follow: [Specific Action] | [Frequency/Timing] | [Acceptance Criteria] | [Verification Method]
   - Example: "Seal integrity testing every 90 days with <1 ppm leak rate acceptance, documented with supervisor sign-off"
   - Include equipment specifications, procedures, or design changes
   - State measurement units and success criteria explicitly
   - Include competency or training requirements with frequency

6. PROCESS SAFETY FUNDAMENTAL VIOLATION (2-3 sentences) - MANDATORY FORMAT:
   - State: "[Principle Name] was violated BECAUSE [specific mechanism/action not taken] which caused [outcome]"
   - Example: "We Respect Hazards was violated BECAUSE the noise signal from seal degradation was not escalated as a hazard warning"
   - Name the exact principle (e.g., "Verify Before You Act", "Know Your Procedures", "We Respect Hazards")
   - DO NOT just say "was violated" without the BECAUSE and outcome

7. LIFE SAVING RULE VIOLATION (2-3 sentences) - MANDATORY FORMAT:
   - State: "[Rule Name] was not followed BECAUSE [specific action that should have occurred but didn't] which resulted in [consequence]"
   - Example: "Control of Work was not followed BECAUSE the post-revision pressure test was not performed before startup"
   - Name the exact rule and explain what specific action was missing
   - DO NOT use generic language like "was not properly implemented"

8. SUGGESTION AND CLOSE OUT (2-3 sentences) - Conclude with:
   - One specific, actionable key takeaway relevant to the organization
   - One reflective question for the audience to consider

INCIDENT DATA:
What happened: {what_happened}
Why it happened: {why_did_it_happen or 'N/A'}
What we learned: {what_did_they_learn or 'N/A'}

CRITICAL RULES - DO NOT BREAK THESE:
- Write natural spoken dialogue ONLY (no headings, brackets, scene descriptions, no numbered lists)
- MAXIMUM: 5000 characters (~1300 words)
- Sound like one person speaking naturally and conversationally
- EVERY STATEMENT must use PROVIDED data - DO NOT invent numbers, equipment models, or specifications not in the incident information
- Use specific names, times, and measurements FROM the incident data provided
- DO NOT use generic phrases: "was violated", "similar incident", "proper procedures", "failure", "poor", "best practices"
- DO NOT use vague language: use exact mechanism names, specific equipment names from provided data, measurable criteria
- Reference case MUST include specific mechanism similarity to current incident
- PSF and LSR sections MUST follow the format: [Principle/Rule] was [violated/not followed] BECAUSE [specific mechanism] [outcome/consequence]
- All preventive actions MUST have measurable acceptance criteria and verification methods
- DO NOT exceed 2500 characters"""


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


async def generate_script_from_material(material: str) -> Dict[str, Any]:
    """Generate a video script from textual training material"""
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
        prompt = _build_pdf_script_prompt(material)

        print(f"[Script Gen] Generating script from material ({len(material)} chars)...")

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
            "source": "document",
            "generated_at": str(__import__('datetime').datetime.now(
                __import__('datetime').timezone.utc
            ).isoformat())
        }

    except Exception as e:
        print(f"[Script Gen] Error: {str(e)}")
        return {
            "success": False,
            "error": f"Document script generation failed: {str(e)}"
        }


# Backwards compatibility alias
generate_script_from_pdf = generate_script_from_material


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


def generate_questions_from_script(script_text: str) -> Dict[str, Any]:
    """
    Generate two multiple-choice and one short-answer question
    based on the provided training script.
    """
    try:
        if OpenAI is None or not settings.OPENAI_API_KEY:
            return {"success": False, "questions": []}

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        trimmed_script = script_text[:4000]

        prompt = f"""You are a training assessment expert.
Read the following training script and produce assessment questions to verify comprehension.

SCRIPT:
---
{trimmed_script}
---

Respond with valid JSON (no markdown) using this structure:
{{
  "questions": [
    {{
      "type": "multiple_choice",
      "question": "...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": 0
    }},
    {{
      "type": "multiple_choice",
      "question": "...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": 2
    }},
    {{
      "type": "text",
      "question": "Short-answer reflection question"
    }}
  ]
}}

Guidelines:
- Both multiple choice questions must have exactly 4 options with zero-based correct_answer index.
- The final question must be open-ended (type = "text").
- Focus on practical safety takeaways referenced in the script."""

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You generate structured assessment questions and only return strict JSON output."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.4,
            max_tokens=700
        )

        response_text = response.choices[0].message.content.strip()
        questions_data = json.loads(response_text)
        return {
            "success": True,
            "questions": questions_data.get("questions", [])
        }

    except Exception as e:
        print(f"[Training Questions] Error generating from script: {str(e)}")
        return {"success": False, "questions": []}


async def generate_script_from_incident(
    what_happened: str,
    why_did_it_happen: Optional[str] = None,
    what_did_they_learn: Optional[str] = None,
    ask_yourself_or_crew: Optional[str] = None,
    tenant_id: Optional[str] = None,
    process_safety_violations: Optional[str] = None,
    life_saving_rule_violations: Optional[str] = None,
    preventive_actions: Optional[str] = None,
    reference_case: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a video script from incident details with 8-part format.
    Optionally finds similar incidents from database for context.

    8-Part Structure:
    1. Introduction
    2. What happened?
    3. Why did it happen?
    4. Reference case from industry
    5. What should be done to prevent?
    6. Process Safety Fundamental violation
    7. Life Saving Rule violation
    8. Suggestion and Close Out
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
            similar_incident,
            process_safety_violations,
            life_saving_rule_violations,
            preventive_actions,
            reference_case
        )

        print(f"[Script Gen] Generating incident script with 8-part format...")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional safety training speaker. Create natural, conversational dialogue only - no scene descriptions, no stage directions, no visual cues. Follow the 8-part structure exactly as specified in the prompt."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=5000
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
