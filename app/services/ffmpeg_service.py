"""
FFmpeg Video Composition Service

Handles post-processing of HeyGen videos:
1. Subtitle rendering (text overlay with custom styling)
2. Scene clips composition (Picture-in-Picture video insertion)
3. Background music mixing (audio layer addition with volume control)
"""

import asyncio
import subprocess
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class FFmpegService:
    """
    ✅ Service for FFmpeg video composition operations.

    Handles all video post-processing after HeyGen video completion.
    """

    def __init__(self):
        self.ffmpeg_path = os.environ.get("FFMPEG_PATH", "ffmpeg")
        self.tmp_dir = os.environ.get("VIDEO_TEMP_DIR", "/tmp/marcel-videos")
        self._ensure_tmp_dir()

    def _ensure_tmp_dir(self):
        """Ensure temporary directory exists"""
        os.makedirs(self.tmp_dir, exist_ok=True)

    async def download_video(self, video_url: str, job_id: int) -> str:
        """
        Download HeyGen video from URL to temporary storage.

        Args:
            video_url: URL to HeyGen video
            job_id: Database job ID

        Returns:
            Path to downloaded video file
        """
        output_path = f"{self.tmp_dir}/heygen_video_{job_id}.mp4"

        try:
            logger.info(f"[FFmpeg] Downloading video from: {video_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(video_url, follow_redirects=True)
                response.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(response.content)

            logger.info(f"[FFmpeg] Video downloaded to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"[FFmpeg] Failed to download video: {str(e)}")
            raise

    async def add_subtitle(
        self,
        input_video: str,
        subtitle_config: Dict[str, Any],
        job_id: int
    ) -> str:
        """
        Add subtitle text overlay to video using FFmpeg drawtext filter.

        Args:
            input_video: Path to input video
            subtitle_config: Subtitle configuration
                - text: Subtitle text
                - position: 'top' | 'middle' | 'bottom'
                - fontSize: Font size in pixels
                - color: Text color (hex)
                - backgroundColor: Background color (hex)
                - opacity: Background opacity (0-1)
            job_id: Database job ID

        Returns:
            Path to video with subtitles
        """
        try:
            logger.info(f"[FFmpeg] Adding subtitles to job #{job_id}")

            text = subtitle_config.get("text", "")
            position = subtitle_config.get("position", "bottom")
            font_size = subtitle_config.get("fontSize", 24)
            text_color = subtitle_config.get("color", "#FFFFFF").lstrip("#")
            bg_color = subtitle_config.get("backgroundColor", "#000000").lstrip("#")
            bg_opacity = subtitle_config.get("opacity", 0.7)

            # Convert opacity to alpha (0-255)
            bg_alpha = hex(int(255 * (1 - bg_opacity)))[2:].zfill(2)

            # Determine Y position
            y_pos_map = {
                "top": "h*0.1",
                "middle": "(h-text_h)/2",
                "bottom": "h-text_h-20"
            }
            y_pos = y_pos_map.get(position, "h-text_h-20")

            # Build drawtext filter with background
            drawtext_filter = (
                f"drawtext="
                f"text='{text}':"
                f"fontsize={font_size}:"
                f"fontcolor=#{text_color}:"
                f"boxcolor=#{bg_color}{bg_alpha}:"
                f"box=1:"
                f"boxborderw=5:"
                f"x=(w-text_w)/2:"
                f"y={y_pos}"
            )

            output_path = f"{self.tmp_dir}/subtitle_job_{job_id}.mp4"

            cmd = [
                self.ffmpeg_path,
                "-i", input_video,
                "-vf", drawtext_filter,
                "-codec:a", "copy",  # Keep audio unchanged
                "-y",  # Overwrite output
                output_path
            ]

            logger.info(f"[FFmpeg] Running subtitle command: {' '.join(cmd)}")
            result = await self._run_ffmpeg(cmd)

            if result == 0:
                logger.info(f"[FFmpeg] Subtitles added successfully to job #{job_id}")
                return output_path
            else:
                raise RuntimeError(f"FFmpeg subtitle operation failed with code {result}")

        except Exception as e:
            logger.error(f"[FFmpeg] Subtitle addition failed: {str(e)}")
            raise

    async def add_scene_clips(
        self,
        input_video: str,
        scene_clips: List[Dict[str, Any]],
        job_id: int
    ) -> str:
        """
        Add scene clips as Picture-in-Picture overlays.

        Args:
            input_video: Path to main video
            scene_clips: List of scene clip configs
                Each clip:
                - file: File path or URL
                - startTime: Start time in seconds
                - endTime: End time in seconds
                - position: {x, y, scale}
            job_id: Database job ID

        Returns:
            Path to video with scene clips
        """
        try:
            logger.info(f"[FFmpeg] Adding {len(scene_clips)} scene clips to job #{job_id}")

            current_video = input_video
            clip_index = 0

            for clip in scene_clips:
                clip_index += 1
                logger.info(f"[FFmpeg] Processing scene clip {clip_index}/{len(scene_clips)}")

                clip_file = clip.get("file", {})
                if isinstance(clip_file, dict):
                    clip_path = clip_file.get("path")
                else:
                    clip_path = clip_file

                start_time = clip.get("startTime", 0)
                end_time = clip.get("endTime", 10)
                duration = end_time - start_time

                position = clip.get("position", {})
                x = position.get("x", 0.65)
                y = position.get("y", 0.05)
                scale = position.get("scale", 0.3)

                # Convert normalized positions to pixels (assuming 1920x1080)
                x_px = int(x * 1920)
                y_px = int(y * 1080)
                scale_w = int(1920 * scale)

                # Build complex filter for PiP
                overlay_filter = (
                    f"[0:v][1:v]overlay="
                    f"x={x_px}:"
                    f"y={y_px}:"
                    f"enable='between(t,{start_time},{end_time})'"
                )

                output_path = f"{self.tmp_dir}/pip_job_{job_id}_clip_{clip_index}.mp4"

                # Build FFmpeg command with multiple inputs
                cmd = [
                    self.ffmpeg_path,
                    "-i", current_video,
                    "-i", clip_path,
                    "-filter_complex", overlay_filter,
                    "-c:a", "aac",  # Encode audio
                    "-b:a", "128k",
                    "-y",
                    output_path
                ]

                logger.info(f"[FFmpeg] Running PiP command for clip {clip_index}")
                result = await self._run_ffmpeg(cmd)

                if result == 0:
                    current_video = output_path
                    logger.info(f"[FFmpeg] Scene clip {clip_index} added successfully")
                else:
                    raise RuntimeError(f"FFmpeg scene clip operation failed with code {result}")

            logger.info(f"[FFmpeg] All scene clips added to job #{job_id}")
            return current_video

        except Exception as e:
            logger.error(f"[FFmpeg] Scene clip addition failed: {str(e)}")
            raise

    async def add_logo_overlay(
        self,
        input_video: str,
        logo_image: str,
        job_id: int,
        start_time: float = 0,
        end_time: float = 5,
        position: str = "top_right",
        width: int = 150,
        height: int = 100
    ) -> str:
        """
        Add logo/image overlay to video for specified time range.

        Args:
            input_video: Path to input video
            logo_image: Path to logo image file
            job_id: Database job ID
            start_time: Start time in seconds (default 0)
            end_time: End time in seconds (default 5)
            position: Position - 'top_left', 'top_right', 'bottom_left', 'bottom_right', 'center'
            width: Logo width in pixels
            height: Logo height in pixels

        Returns:
            Path to video with logo overlay
        """
        try:
            logger.info(f"[FFmpeg] Adding logo overlay to job #{job_id} from {start_time}s to {end_time}s")

            # Position mappings
            positions = {
                "top_left": "x=20:y=20",
                "top_right": f"x=W-w-20:y=20",
                "bottom_left": "x=20:y=H-h-20",
                "bottom_right": f"x=W-w-20:y=H-h-20",
                "center": "x=(W-w)/2:y=(H-h)/2"
            }

            pos_str = positions.get(position, positions["top_right"])

            # Build overlay filter
            overlay_filter = (
                f"[1:v]scale={width}:{height}[logo]; "
                f"[0:v][logo]overlay={pos_str}:enable='between(t,{start_time},{end_time})'[out]"
            )

            output_path = f"{self.tmp_dir}/logo_job_{job_id}.mp4"

            cmd = [
                self.ffmpeg_path,
                "-i", input_video,
                "-i", logo_image,
                "-filter_complex", overlay_filter,
                "-map", "[out]",
                "-map", "0:a",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-y",
                output_path
            ]

            logger.info(f"[FFmpeg] Running logo overlay command")
            result = await self._run_ffmpeg(cmd)

            if result == 0:
                logger.info(f"[FFmpeg] Logo overlay added successfully to job #{job_id}")
                return output_path
            else:
                raise RuntimeError(f"FFmpeg logo overlay operation failed with code {result}")

        except Exception as e:
            logger.error(f"[FFmpeg] Logo overlay addition failed: {str(e)}")
            raise

    async def add_background_music(
        self,
        input_video: str,
        music_name: str,
        job_id: int,
        music_volume: float = 0.3,
        video_volume: float = 0.7
    ) -> str:
        """
        Add background music to video and mix audio tracks.

        Args:
            input_video: Path to video
            music_name: Name/path of music file
            job_id: Database job ID
            music_volume: Background music volume (0.0 - 1.0, default 0.3)
            video_volume: Original video volume (0.0 - 1.0, default 0.7)

        Returns:
            Path to video with background music
        """
        try:
            logger.info(f"[FFmpeg] Adding background music '{music_name}' to job #{job_id}")

            # Build audio mixing filter with custom volumes
            audio_filter = (
                f"[0:a]volume={video_volume}[original];"
                f"[1:a]volume={music_volume}[music];"
                f"[original][music]amix=inputs=2:duration=first[out]"
            )

            output_path = f"{self.tmp_dir}/music_job_{job_id}.mp4"

            cmd = [
                self.ffmpeg_path,
                "-i", input_video,
                "-i", music_name,
                "-filter_complex", audio_filter,
                "-map", "0:v",      # Use video from first input
                "-map", "[out]",    # Use mixed audio
                "-shortest",        # Stop at shortest stream
                "-c:v", "libx264",  # Re-encode video
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",      # Encode audio to AAC
                "-b:a", "192k",
                "-y",
                output_path
            ]

            logger.info(f"[FFmpeg] Running background music command")
            result = await self._run_ffmpeg(cmd)

            if result == 0:
                logger.info(f"[FFmpeg] Background music added successfully to job #{job_id}")
                return output_path
            else:
                raise RuntimeError(f"FFmpeg music addition failed with code {result}")

        except Exception as e:
            logger.error(f"[FFmpeg] Background music addition failed: {str(e)}")
            raise

    async def _run_ffmpeg(self, cmd: List[str], timeout: int = 3600) -> int:
        """
        Run FFmpeg command asynchronously.

        Args:
            cmd: FFmpeg command as list
            timeout: Timeout in seconds (default 1 hour)

        Returns:
            Return code (0 = success)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                logger.error(f"[FFmpeg] Command timed out after {timeout}s")
                return -1

            if process.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="ignore")
                logger.warning(f"[FFmpeg] Command failed with code {process.returncode}:")
                logger.warning(stderr_text[-1000:])  # Last 1000 chars

            return process.returncode

        except Exception as e:
            logger.error(f"[FFmpeg] Failed to run command: {str(e)}")
            return -1

    def cleanup_temp_files(self, job_id: int):
        """Clean up temporary files for a job"""
        try:
            import glob
            pattern = f"{self.tmp_dir}/*_job_{job_id}*"
            for filepath in glob.glob(pattern):
                try:
                    os.remove(filepath)
                    logger.info(f"[FFmpeg] Cleaned up: {filepath}")
                except Exception as e:
                    logger.warning(f"[FFmpeg] Failed to delete {filepath}: {str(e)}")
        except Exception as e:
            logger.error(f"[FFmpeg] Cleanup failed: {str(e)}")
