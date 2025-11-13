"""
Quiz question generation service using ChatGPT API
Generates training questions from video scripts
"""
import json
import logging
from typing import Optional, List, Dict, Any
from openai import OpenAI, APIError

from app.config import settings

logger = logging.getLogger(__name__)


class QuizGenerationService:
    """Service for generating quiz questions from video scripts using ChatGPT"""

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    @staticmethod
    def _validate_questions(questions: List[Dict[str, Any]]) -> bool:
        """Validate that questions have required structure"""
        if not isinstance(questions, list) or len(questions) != 3:
            return False

        for q in questions:
            if not isinstance(q, dict):
                return False
            required_fields = {'question', 'type'}
            if not required_fields.issubset(q.keys()):
                return False

            if q['type'] == 'text':
                if 'expected_answer' not in q:
                    return False
            elif q['type'] == 'multiple_choice':
                if not all(k in q for k in ['options', 'correct_answer']):
                    return False
                if not isinstance(q['options'], list) or len(q['options']) < 2:
                    return False
                if q['correct_answer'] not in q['options']:
                    return False

        return True

    async def generate_questions(self, script: str, video_title: str) -> Optional[List[Dict[str, Any]]]:
        """
        Generate 3 training questions (1 text, 2 multiple choice) from a video script

        Args:
            script: The video script/content
            video_title: Title of the video for context

        Returns:
            List of 3 questions with the structure:
            [
                {
                    "question": "What is...",
                    "type": "text",
                    "expected_answer": "..."
                },
                {
                    "question": "Which of...",
                    "type": "multiple_choice",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "A"
                },
                {
                    "question": "When...",
                    "type": "multiple_choice",
                    "options": ["X", "Y", "Z"],
                    "correct_answer": "Y"
                }
            ]
        """
        if not self.client:
            logger.warning(
                "[QuizGeneration] OpenAI client not configured, skipping question generation"
            )
            return None

        try:
            prompt = self._build_prompt(script, video_title)

            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert educational content creator. Generate clear, "
                        "concise training questions to assess video comprehension. Return ONLY valid JSON.",
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            response_text = response.choices[0].message.content.strip()

            # Extract JSON from response (in case there's extra text)
            try:
                # Try to find JSON object in response
                if response_text.startswith('{'):
                    json_str = response_text
                else:
                    # Look for JSON block
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    if start != -1 and end > start:
                        json_str = response_text[start:end]
                    else:
                        logger.error("[QuizGeneration] Could not find JSON in response")
                        return None

                questions_response = json.loads(json_str)

                # Handle both wrapped and direct responses
                questions = questions_response.get('questions', questions_response)
                if not isinstance(questions, list):
                    questions = [questions_response]

                # Validate and clean questions
                if not self._validate_questions(questions):
                    logger.error("[QuizGeneration] Invalid question structure from ChatGPT")
                    return None

                logger.info(
                    f"[QuizGeneration] Successfully generated {len(questions)} questions "
                    f"for video: {video_title}"
                )
                return questions

            except json.JSONDecodeError as e:
                logger.error(f"[QuizGeneration] Failed to parse JSON response: {e}")
                logger.error(f"[QuizGeneration] Response was: {response_text[:200]}")
                return None

        except APIError as e:
            logger.error(f"[QuizGeneration] OpenAI API error: {e}")
            return None
        except Exception as e:
            logger.error(f"[QuizGeneration] Unexpected error during question generation: {e}")
            return None

    @staticmethod
    def _build_prompt(script: str, video_title: str) -> str:
        """Build the prompt for ChatGPT to generate questions"""
        # Truncate script if too long
        max_script_length = 2000
        if len(script) > max_script_length:
            script = script[:max_script_length] + "..."

        return f"""Based on the following video script for "{video_title}", generate exactly 3 training questions to assess learner comprehension.

IMPORTANT - You MUST return ONLY a valid JSON object with this exact structure:
{{
  "questions": [
    {{
      "question": "Short question in English?",
      "type": "text",
      "expected_answer": "Expected answer or key points to cover"
    }},
    {{
      "question": "Multiple choice question?",
      "type": "multiple_choice",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A"
    }},
    {{
      "question": "Another multiple choice question?",
      "type": "multiple_choice",
      "options": ["Choice 1", "Choice 2", "Choice 3"],
      "correct_answer": "Choice 2"
    }}
  ]
}}

VIDEO SCRIPT:
{script}

Requirements:
- Generate exactly 3 questions
- First question must be "type": "text"
- Second and third questions must be "type": "multiple_choice"
- Questions must assess understanding of key concepts from the video
- Multiple choice options should be plausible but distinct
- Make questions clear and concise
- Return ONLY the JSON object, no other text"""
