import os
import json
import asyncio
import aiohttp
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
LEONARDO_API_URL = "https://cloud.leonardo.ai/api/rest/v1"

IMAGE_PLANNING_PROMPT = """
You are a visual director for an educational explainer video.

Below is a structured explanation of a study topic:
{explanation_json}

For each step in the explanation, design ONE visual scene that perfectly illustrates that step.
Also create an intro scene (Step 0) and an outro/summary scene.

For each scene, write a HIGHLY DETAILED text-to-image generation prompt that:
- Describes the exact visual content
- Specifies an educational, clean whiteboard or infographic art style
- Mentions colors (prefer blue/white/teal academic palette)
- Specifies the composition (what is in the foreground, background)
- Requests 4K, sharp, professional quality
- Avoids text in images (images should be purely visual)

Respond ONLY with a valid JSON array:
[
  {{
    "scene_id": "scene_0",
    "step_reference": "intro",
    "description": "What this image shows",
    "prompt": "Highly detailed image generation prompt here..."
  }},
  {{
    "scene_id": "scene_1",
    "step_reference": "step_1",
    "description": "What this image shows",
    "prompt": "Highly detailed image generation prompt here..."
  }}
]
"""

class ImagePlanner:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 8192,
                "response_mime_type": "application/json"
            }
        )

    async def plan(self, explanation: dict) -> list:
        """
        Takes the explanation dict and returns a list of image scene dicts,
        each containing a scene_id, step_reference, and detailed prompt.
        """
        explanation_json = json.dumps(explanation, indent=2)
        prompt = IMAGE_PLANNING_PROMPT.format(explanation_json=explanation_json)

        loop = asyncio.get_event_loop()
        scenes = await loop.run_in_executor(None, self._call_gemini, prompt)
        return scenes

    def _call_gemini(self, prompt: str) -> list:
        """Synchronous Gemini call (run in thread pool)."""
        try:
            response = self.model.generate_content(prompt)
            raw = response.text.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            scenes = json.loads(raw)
            if not isinstance(scenes, list):
                raise ValueError("Expected a JSON array of scenes")
            return scenes

        except json.JSONDecodeError as e:
            raise ValueError(f"Gemini returned invalid JSON for image plan: {e}")
        except Exception as e:
            raise RuntimeError(f"Image planning error: {e}")


async def generate_image_fallback(prompt: str, scene_id: str, job_id: str) -> str:
    """
    Fallback: Generate image using Leonardo AI REST API directly.
    Returns the local path of the saved JPEG image.
    """
    output_dir = f"outputs/{job_id}/images"
    os.makedirs(output_dir, exist_ok=True)
    output_path = f"{output_dir}/{scene_id}.jpg"

    headers = {
        "Authorization": f"Bearer {LEONARDO_API_KEY}",
        "Content-Type": "application/json"
    }

    # Step 1: Submit generation request
    generation_payload = {
        "prompt": prompt,
        "modelId": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3",  # Leonardo Diffusion XL
        "width": 1024,
        "height": 576,
        "num_images": 1,
        "guidance_scale": 7,
        "num_inference_steps": 40,
        "public": False
    }

    async with aiohttp.ClientSession() as session:
        # Submit generation
        async with session.post(
            f"{LEONARDO_API_URL}/generations",
            headers=headers,
            json=generation_payload
        ) as resp:
            resp.raise_for_status()
            gen_data = await resp.json()
            generation_id = gen_data["sdGenerationJob"]["generationId"]

        # Poll for completion (max 90 seconds)
        for _ in range(18):
            await asyncio.sleep(5)
            async with session.get(
                f"{LEONARDO_API_URL}/generations/{generation_id}",
                headers=headers
            ) as poll_resp:
                poll_data = await poll_resp.json()
                status = poll_data["generations_by_pk"]["status"]
                if status == "COMPLETE":
                    image_url = poll_data["generations_by_pk"]["generated_images"][0]["url"]
                    break
                elif status == "FAILED":
                    raise RuntimeError("Leonardo AI generation failed")
        else:
            raise TimeoutError("Leonardo AI generation timed out")

        # Download the image
        async with session.get(image_url) as img_resp:
            img_data = await img_resp.read()
            with open(output_path, "wb") as f:
                f.write(img_data)

    return output_path
