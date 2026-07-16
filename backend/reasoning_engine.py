import os
import json
import asyncio
import google.generativeai as genai
from typing import Optional

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SUBJECT_STYLES = {
    "math": "Use clear mathematical notation, numbered steps, and show all working. Explain each operation.",
    "cs": "Use pseudocode or code examples where helpful. Explain algorithms step-by-step.",
    "biology": "Use proper scientific terminology. Describe processes sequentially with cause-and-effect.",
    "chemistry": "Show chemical equations where relevant. Explain reactions and mechanisms clearly.",
    "physics": "Include relevant formulas. Explain the physical intuition behind each step.",
    "history": "Provide chronological context. Link causes to effects and explain significance.",
    "english": "Analyze structure, tone, and literary devices. Support points with evidence.",
    "auto": "Adapt your explanation style to best suit the subject matter of the question."
}

REASONING_PROMPT = """
You are StudyFrame, an expert AI tutor. A student has submitted the following question:

""" + """QUESTION: {question}"""

PROMPT_TEMPLATE = """
You are StudyFrame, an expert AI tutor. A student has submitted the following question:

QUESTION: {question}

SUBJECT CONTEXT: {subject_style}

Your task is to produce a detailed, educational explanation that will be turned into a step-by-step explainer video.

Respond ONLY with a valid JSON object in this exact format:
{{
  "subject": "detected subject name (e.g. Math, Computer Science, Biology)",
  "difficulty": "Introductory | Intermediate | Advanced",
  "title": "Short title for this explainer video",
  "summary": "One sentence overview of the answer",
  "steps": [
    {{
      "step_number": 1,
      "title": "Step title",
      "explanation": "Detailed explanation for this step (2-4 sentences, spoken aloud in the video)",
      "key_concept": "The single most important concept in this step"
    }}
  ],
  "conclusion": "Wrap-up sentence summarizing what was learned",
  "key_terms": ["term1", "term2", "term3"]
}}

Provide between 4 and 8 steps. Make each explanation clear enough for a student hearing it for the first time.
"""

class ReasoningEngine:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.95,
                "max_output_tokens": 4096,
                "response_mime_type": "application/json"
            }
        )

    async def explain(self, question: str, subject: str = "auto") -> dict:
        """
        Takes a student question and returns a structured explanation dict.
        Runs Gemini in a thread to avoid blocking the async event loop.
        """
        subject_style = SUBJECT_STYLES.get(subject.lower(), SUBJECT_STYLES["auto"])
        prompt = PROMPT_TEMPLATE.format(
            question=question,
            subject_style=subject_style
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._call_gemini, prompt)
        return response

    def _call_gemini(self, prompt: str) -> dict:
        """Synchronous Gemini call (run in thread pool)."""
        try:
            response = self.model.generate_content(prompt)
            raw = response.text.strip()

            # Strip markdown code blocks if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            
            data = json.loads(raw)
            self._validate_explanation(data)
            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Gemini returned invalid JSON: {e}")
        except Exception as e:
            raise RuntimeError(f"Gemini API error: {e}")

    def _validate_explanation(self, data: dict):
        """Ensure required fields are present."""
        required = ["subject", "title", "steps", "conclusion"]
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field in response: {field}")
        if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
            raise ValueError("Response must contain at least one step")
        for step in data["steps"]:
            if "explanation" not in step:
                raise ValueError("Each step must have an explanation")
