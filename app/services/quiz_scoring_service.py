"""
Quiz scoring service for evaluating quiz answers
Handles both multiple choice and text answer scoring with AI evaluation
"""
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI, APIError

from app.config import settings

logger = logging.getLogger(__name__)


class QuizScoringService:
    """Service for scoring quiz answers"""

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured for quiz scoring")
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def score_answers(
        self,
        answers: List[Dict[str, Any]],
        questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Score a list of answers and return total score and individual question scores

        Returns:
        {
            "score": 85.0,  # Total percentage score
            "answers_with_scores": [
                {
                    "question_index": 0,
                    "question_text": "...",
                    "type": "text",
                    "user_answer": "...",
                    "correct_answer": "...",
                    "points_earned": 33.33,
                    "ai_score": 85.0,
                    "feedback": "Good answer"
                },
                ...
            ]
        }
        """
        if not answers or not questions:
            return {"score": 0, "answers_with_scores": []}

        points_per_question = 100 / len(questions)
        scored_answers = []
        total_points = 0

        for idx, answer in enumerate(answers):
            question = next((q for i, q in enumerate(questions) if i == answer.get('question_index')), None)
            if not question:
                continue

            scored_answer = {
                "question_index": idx,
                "question_text": answer.get("question_text"),
                "type": answer.get("question_type"),
                "user_answer": answer.get("user_answer"),
                "correct_answer": answer.get("correct_answer")
            }

            if answer.get("question_type") == "text":
                # Use AI to evaluate text answer
                score_result = await self._score_text_answer(
                    answer.get("user_answer"),
                    answer.get("correct_answer"),
                    answer.get("question_text")
                )

                if score_result:
                    scored_answer["ai_score"] = score_result["score"]
                    scored_answer["feedback"] = score_result["feedback"]
                    points_earned = (score_result["score"] / 100) * points_per_question
                    scored_answer["points_earned"] = points_earned
                    total_points += points_earned
                else:
                    scored_answer["ai_score"] = 0
                    scored_answer["feedback"] = "Unable to evaluate answer"
                    scored_answer["points_earned"] = 0

            elif answer.get("question_type") == "multiple_choice":
                # Multiple choice: correct or incorrect
                is_correct = str(answer.get("user_answer")).strip() == str(answer.get("correct_answer")).strip()
                scored_answer["is_correct"] = is_correct
                points_earned = points_per_question if is_correct else 0
                scored_answer["points_earned"] = points_earned
                total_points += points_earned

            scored_answers.append(scored_answer)

        total_score = (total_points / (len(questions) * 100)) * 100 if questions else 0

        return {
            "score": total_score,
            "answers_with_scores": scored_answers
        }

    async def _score_text_answer(
        self,
        user_answer: str,
        expected_answer: str,
        question: str
    ) -> Optional[Dict[str, Any]]:
        """
        Use AI to score a text answer
        Returns score (0-100) and feedback
        """
        if not self.client or not user_answer or not expected_answer:
            return None

        try:
            prompt = self._build_scoring_prompt(
                user_answer,
                expected_answer,
                question
            )

            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert educational evaluator. Score student answers fairly and provide constructive feedback."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )

            response_text = response.choices[0].message.content.strip()

            # Parse response - expecting format like: SCORE: 85\nFEEDBACK: ...
            lines = response_text.split('\n')
            score = 0
            feedback = ""

            for line in lines:
                if line.startswith("SCORE:"):
                    try:
                        score = int(line.replace("SCORE:", "").strip())
                        score = min(100, max(0, score))  # Clamp to 0-100
                    except ValueError:
                        score = 0
                elif line.startswith("FEEDBACK:"):
                    feedback = line.replace("FEEDBACK:", "").strip()

            logger.info(f"[QuizScoring] Scored text answer: {score}/100")
            return {"score": score, "feedback": feedback}

        except APIError as e:
            logger.error(f"[QuizScoring] OpenAI API error: {e}")
            return None
        except Exception as e:
            logger.error(f"[QuizScoring] Error scoring text answer: {e}")
            return None

    @staticmethod
    def _build_scoring_prompt(user_answer: str, expected_answer: str, question: str) -> str:
        """Build the prompt for scoring a text answer"""
        return f"""Score the following student answer to an exam question.

QUESTION: {question}

EXPECTED/MODEL ANSWER: {expected_answer}

STUDENT ANSWER: {user_answer}

Instructions:
1. Evaluate the student answer for correctness, completeness, and understanding
2. Give a score from 0-100 where:
   - 90-100: Excellent, comprehensive answer that meets or exceeds expectations
   - 70-89: Good, covers main points and shows understanding
   - 50-69: Fair, covers some points but missing important details
   - 30-49: Poor, shows limited understanding or significant gaps
   - 0-29: Very poor, incorrect or largely incomplete

Format your response EXACTLY like this (two lines):
SCORE: <number>
FEEDBACK: <brief feedback about the answer>

Be fair and constructive in your evaluation."""
