import os
import asyncio
from pathlib import Path
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    CompositeVideoClip, TextClip, ColorClip
)
from google.cloud import texttospeech
import tempfile

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 24
FONT = "Arial-Bold"
FONT_SIZE = 40
TEXT_COLOR = "white"
TEXT_BG_COLOR = (0, 0, 0, 180)  # semi-transparent black
PADDING = 40

class VideoAssembler:
    def __init__(self):
        self.tts_client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Neural2-D",  # Clear, professional male voice
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.95,
            pitch=0.0
        )

    async def assemble(self, explanation: dict, image_paths: list, job_id: str) -> str:
        """
        Assembles the final MP4 video from explanation steps + images.
        Returns the path to the output MP4 file.
        """
        output_dir = f"outputs/{job_id}"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/explainer.mp4"

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._build_video, explanation, image_paths, output_path
        )
        return result

    def _build_video(self, explanation: dict, image_paths: list, output_path: str) -> str:
        """Synchronous video build (run in thread pool)."""
        clips = []
        steps = explanation.get("steps", [])
        title = explanation.get("title", "Study Explainer")
        conclusion = explanation.get("conclusion", "")

        # --- Intro slide ---
        intro_audio = self._generate_tts(
            f"Welcome to StudyFrame. Today we will explore: {title}"
        )
        intro_clip = self._make_clip(
            image_path=image_paths[0] if image_paths else None,
            audio_path=intro_audio,
            subtitle=title,
            subtitle_size=56
        )
        clips.append(intro_clip)

        # --- Step clips ---
        for i, step in enumerate(steps):
            img_index = i + 1  # offset for intro image
            img_path = image_paths[img_index] if img_index < len(image_paths) else None

            narration = f"Step {step.get('step_number', i+1)}: {step.get('title', '')}. {step.get('explanation', '')}"
            audio_path = self._generate_tts(narration)

            subtitle = f"Step {step.get('step_number', i+1)}: {step.get('title', '')}"
            clip = self._make_clip(
                image_path=img_path,
                audio_path=audio_path,
                subtitle=subtitle
            )
            clips.append(clip)

        # --- Conclusion slide ---
        if conclusion:
            outro_audio = self._generate_tts(f"In summary: {conclusion}")
            outro_img = image_paths[-1] if image_paths else None
            outro_clip = self._make_clip(
                image_path=outro_img,
                audio_path=outro_audio,
                subtitle="Summary"
            )
            clips.append(outro_clip)

        # --- Concatenate all clips ---
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(
            output_path,
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=f"{output_path}_temp_audio.m4a",
            remove_temp=True,
            preset="medium",
            logger=None
        )

        # Cleanup TTS temp files
        for clip in clips:
            clip.close()
        final_video.close()

        return output_path

    def _generate_tts(self, text: str) -> str:
        """Generate TTS audio for a text segment, returns path to MP3 file."""
        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = self.tts_client.synthesize_speech(
            input=synthesis_input,
            voice=self.voice,
            audio_config=self.audio_config
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(response.audio_content)
        tmp.close()
        return tmp.name

    def _make_clip(self, image_path: str, audio_path: str, subtitle: str, subtitle_size: int = FONT_SIZE):
        """Creates a single video clip from image + audio + subtitle overlay."""
        audio = AudioFileClip(audio_path)
        duration = audio.duration

        if image_path and os.path.exists(image_path):
            img_clip = (
                ImageClip(image_path)
                .set_duration(duration)
                .resize((VIDEO_WIDTH, VIDEO_HEIGHT))
            )
        else:
            # Fallback: solid blue background
            img_clip = ColorClip(
                size=(VIDEO_WIDTH, VIDEO_HEIGHT),
                color=(30, 80, 160)
            ).set_duration(duration)

        # Subtitle bar at bottom
        try:
            txt_clip = (
                TextClip(
                    subtitle,
                    fontsize=subtitle_size,
                    font=FONT,
                    color=TEXT_COLOR,
                    bg_color="rgba(0,0,0,0.7)",
                    method="caption",
                    size=(VIDEO_WIDTH - 2 * PADDING, None)
                )
                .set_position((PADDING, VIDEO_HEIGHT - 120))
                .set_duration(duration)
            )
            final_clip = CompositeVideoClip([img_clip, txt_clip])
        except Exception:
            # If text rendering fails, just use image
            final_clip = img_clip

        final_clip = final_clip.set_audio(audio)
        return final_clip
