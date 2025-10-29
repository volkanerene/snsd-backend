"""
OpenAI Service for Video Script Generation
"""

import os
from typing import Optional
from openai import AsyncOpenAI

from app.config import settings


class OpenAIService:
    """Service for generating video scripts using OpenAI GPT models"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI service

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        # Prefer explicit key, then settings (loaded from .env), finally raw env
        self.api_key = api_key or settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        self.client = AsyncOpenAI(api_key=self.api_key)
        self.max_script_chars = 1500

    async def generate_video_script(
        self,
        prompt: str,
        context: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a video script based on a prompt

        Args:
            prompt: User's script generation request
            context: Additional context (e.g., from PDF or incident report)
            max_tokens: Maximum length of generated script
            temperature: Creativity level (0-1, higher is more creative)

        Returns:
            Generated video script text
        """
        system_prompt = """You are a professional video scriptwriter.
Generate clear, engaging, natural-sounding narration for AI avatar videos.
Respond with only the spoken dialogue that the avatar should say—no scene descriptions, stage directions, bullet points, or speaker labels.
Ensure the final script is concise, conversational, and no more than 1400 characters long (shorten it if necessary)."""

        max_tokens = min(max_tokens, 360)

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add context if provided
        if context:
            messages.append({
                "role": "system",
                "content": f"Context information:\n{context}"
            })

        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini for cost efficiency
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        script = response.choices[0].message.content.strip()
        return await self._ensure_length(script)

    async def extract_dialogue_from_text(
        self,
        text: str,
        format_instructions: Optional[str] = None,
    ) -> str:
        """
        Extract or convert text into dialogue format for video scripts

        Args:
            text: Source text (e.g., from PDF, incident report)
            format_instructions: Specific formatting requirements

        Returns:
            Formatted dialogue text
        """
        system_prompt = """You are a script editor. Convert the provided text into spoken dialogue for an AI avatar.
Output only the narration that should be spoken—no scene descriptions, instructions, or extra commentary.
Keep the result clear, conversational, and shorter than 1400 characters."""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if format_instructions:
            messages.append({
                "role": "system",
                "content": f"Formatting requirements:\n{format_instructions}"
            })

        messages.append({
            "role": "user",
            "content": f"Convert this text into video dialogue:\n\n{text}"
        })

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=360,
            temperature=0.5,  # Lower temperature for more faithful conversion
        )

        script = response.choices[0].message.content.strip()
        return await self._ensure_length(script)

    async def refine_script(
        self,
        original_script: str,
        refinement_instructions: str,
    ) -> str:
        """
        Refine or edit an existing script based on user instructions

        Args:
            original_script: The script to refine
            refinement_instructions: What changes to make

        Returns:
            Refined script
        """
        messages = [
            {
                "role": "system",
                "content": "You are a script editor. Refine the given script according to the user's instructions while maintaining its core message and quality."
            },
            {
                "role": "user",
                "content": f"Original script:\n{original_script}\n\nInstructions:\n{refinement_instructions}"
            }
        ]

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=360,
            temperature=0.6,
        )

        script = response.choices[0].message.content.strip()
        return await self._ensure_length(script)

    async def _ensure_length(self, script: str) -> str:
        """Ensure the script does not exceed the character limit."""
        script = script.strip()
        if len(script) <= self.max_script_chars:
            return script

        shorten_messages = [
            {
                "role": "system",
                "content": "You are a concise dialogue editor. Shorten the narration when needed while keeping it natural and fluent.",
            },
            {
                "role": "user",
                "content": (
                    f"Please shorten the following narration so that it stays under {self.max_script_chars} characters. "
                    "Preserve the main message and respond with only the shortened narration:\n\n"
                    f"{script}"
                ),
            },
        ]

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=shorten_messages,
            max_tokens=360,
            temperature=0.5,
        )

        shortened = response.choices[0].message.content.strip()
        if len(shortened) <= self.max_script_chars:
            return shortened

        # As a final safeguard, truncate politely while avoiding a hanging word
        truncated = shortened[: self.max_script_chars]
        if not truncated.endswith((" ", "\n")):
            truncated = truncated.rsplit(" ", 1)[0]
        return truncated.strip()
