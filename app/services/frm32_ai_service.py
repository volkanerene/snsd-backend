"""
FRM32 AI Scoring Service
Generates AI-based score suggestions using OpenAI ChatGPT
"""

import json
from typing import Dict, Any, List
from app.config import settings

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _build_ai_prompt(k2_metrics: List[Dict], answers: Dict[str, str], contractor_name: str) -> str:
    """
    Build the prompt for ChatGPT to evaluate answers and suggest K2 scores
    """
    k2_info = "\n".join([
        f"- {m['k2_code']}: {m['scope_en']}\n"
        f"  Score 10: {m['comment_10_en']}\n"
        f"  Score 6: {m['comment_6_en']}\n"
        f"  Score 3: {m['comment_3_en']}\n"
        f"  Score 0: {m['comment_0_en']}"
        for m in k2_metrics
    ])

    answers_str = "\n".join([
        f"Q: {q}\nA: {answers.get(q, 'Not answered')}"
        for q in sorted(answers.keys())
    ])

    prompt = f"""
You are an expert HSE (Health, Safety & Environment) assessor evaluating contractor capabilities.

CONTRACTOR: {contractor_name}

SCORING GUIDANCE:
- Score 10: Comprehensive evidence with processes, KPIs, regular reviews, quantified results
- Score 6: Structured approach with some evidence, but missing key elements or verification
- Score 3: Basic/partial evidence, ad-hoc processes, or minimal implementation
- Score 0: No concrete evidence or only attachment references

K2 METRICS AND SCORING CRITERIA:
{k2_info}

CONTRACTOR RESPONSES:
{answers_str}

TASK:
Analyze the contractor's responses and provide score suggestions for EACH K2 metric.
For each K2 code, evaluate the quality and completeness of evidence provided.

Return a JSON array with this exact format:
[
  {{
    "k2_code": "1.1",
    "suggested_score": 6,
    "reasoning": "Brief explanation of why this score was suggested based on the evidence provided"
  }},
  {{
    "k2_code": "2.1",
    "suggested_score": 3,
    "reasoning": "..."
  }}
]

Important:
- Only return valid scores: 0, 3, 6, or 10
- Evaluate each metric independently; do not assign the same score to every metric unless the evidence is genuinely identical.
- Reasoning should be 1-2 sentences explaining the evidence quality
- Be objective and evidence-based
- Return ONLY the JSON array, no other text
"""
    return prompt


async def generate_ai_score_suggestions(
    k2_metrics: List[Dict],
    answers: Dict[str, str],
    contractor_name: str
) -> Dict[str, Any]:
    """
    Call OpenAI ChatGPT to generate score suggestions for K2 metrics

    Args:
        k2_metrics: List of K2 metric definitions with scoring criteria
        answers: Dictionary of question codes -> answers
        contractor_name: Name of the contractor

    Returns:
        Dictionary with:
        {
            "success": bool,
            "suggestions": [
                {
                    "k2_code": str,
                    "suggested_score": int,
                    "reasoning": str
                }
            ],
            "error": str (if failed)
        }
    """
    try:
        if not settings.OPENAI_API_KEY:
            print("[AI Scoring] OPENAI_API_KEY not configured")
            return {
                "success": False,
                "suggestions": [],
                "error": "OpenAI API key not configured"
            }

        if OpenAI is None:
            print("[AI Scoring] OpenAI client not available")
            return {
                "success": False,
                "suggestions": [],
                "error": "OpenAI library not installed"
            }

        # Initialize OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Build prompt
        prompt = _build_ai_prompt(k2_metrics, answers, contractor_name)

        # Call ChatGPT
        print(f"[AI Scoring] Calling ChatGPT for score suggestions (contractor: {contractor_name})")

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert HSE assessor. Always return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=2000
        )

        response_text = response.choices[0].message.content.strip()
        print(f"[AI Scoring] ChatGPT response received")

        # Parse JSON response
        try:
            suggestions = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"[AI Scoring] Failed to parse ChatGPT JSON response: {str(e)}")
            print(f"[AI Scoring] Raw response: {response_text[:500]}")
            return {
                "success": False,
                "suggestions": [],
                "error": f"Invalid JSON response from AI: {str(e)}"
            }

        # Validate suggestions
        valid_suggestions = []
        for item in suggestions:
            if not isinstance(item, dict):
                continue

            k2_code = item.get("k2_code")
            score = item.get("suggested_score")
            reasoning = item.get("reasoning", "")

            if not k2_code or score not in (0, 3, 6, 10):
                print(f"[AI Scoring] Invalid suggestion: {item}")
                continue

            valid_suggestions.append({
                "k2_code": k2_code,
                "suggested_score": score,
                "reasoning": str(reasoning)[:500]  # Limit to 500 chars
            })

        print(f"[AI Scoring] Generated {len(valid_suggestions)} valid suggestions")

        return {
            "success": True,
            "suggestions": valid_suggestions,
            "error": None
        }

    except Exception as e:
        print(f"[AI Scoring] Error: {str(e)}")
        return {
            "success": False,
            "suggestions": [],
            "error": f"AI scoring error: {str(e)}"
        }
