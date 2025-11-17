"""
Video Composition Service
Handles scene composition and music mixing for HeyGen-generated videos using FFmpeg
"""

import os
import json
import asyncio
import tempfile
import subprocess
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VideoCompositionService:
    """Service for composing videos with scene clips and background music"""

    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        if not self.ffmpeg_path:
            logger.warning("FFmpeg not found. Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)")

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        """Find FFmpeg executable path"""
        for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
            if os.path.exists(path):
                return path
        # Try using 'which' command
        try:
            result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    async def compose_video(
        self,
        base_video_url: str,
        base_video_path: str,
        scene_clips: List[Dict[str, Any]],
        background_music_url: Optional[str] = None,
        background_music_path: Optional[str] = None,
        output_path: str = None
    ) -> Dict[str, Any]:
        """
        Compose a video with scene clips and background music

        Args:
            base_video_url: URL of the base HeyGen video
            base_video_path: Local path to downloaded base video
            scene_clips: List of scene clip configs
                [{
                    "path": "/path/to/clip.mp4",
                    "start_time": 5.0,  # when clip starts in final video
                    "end_time": 15.0,   # when clip ends in final video
                    "position": {"x": 0.65, "y": 0.05, "scale": 0.3}  # optional PiP position
                }]
            background_music_url: URL of background music
            background_music_path: Local path to background music
            output_path: Where to save the final video

        Returns:
            {
                "success": True,
                "output_path": "/path/to/output.mp4",
                "duration": 120.5,
                "size": 1024000
            }
        """
        if not self.ffmpeg_path:
            return {
                "success": False,
                "error": "FFmpeg not installed. Cannot compose videos."
            }

        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4")

        try:
            # Get video dimensions and duration
            base_info = await self._get_video_info(base_video_path)
            if not base_info:
                return {"success": False, "error": "Cannot read base video"}

            base_width = base_info.get("width", 1280)
            base_height = base_info.get("height", 720)
            base_duration = base_info.get("duration", 0)

            logger.info(f"[Composition] Base video: {base_width}x{base_height}, duration: {base_duration}s")

            # Build FFmpeg command
            if scene_clips and background_music_path:
                # Complex composition with scenes and music
                await self._compose_with_scenes_and_music(
                    base_video_path,
                    base_width,
                    base_height,
                    scene_clips,
                    background_music_path,
                    output_path
                )
            elif scene_clips:
                # Composition with scenes only
                await self._compose_with_scenes(
                    base_video_path,
                    base_width,
                    base_height,
                    scene_clips,
                    output_path
                )
            elif background_music_path:
                # Music mixing only
                await self._add_background_music(
                    base_video_path,
                    background_music_path,
                    output_path
                )
            else:
                # No composition needed
                return {
                    "success": True,
                    "output_path": base_video_path,
                    "duration": base_duration,
                    "size": os.path.getsize(base_video_path)
                }

            # Verify output
            if not os.path.exists(output_path):
                return {"success": False, "error": "Composition failed: output file not created"}

            output_info = await self._get_video_info(output_path)
            output_size = os.path.getsize(output_path)

            logger.info(f"[Composition] Success: {output_size} bytes")

            return {
                "success": True,
                "output_path": output_path,
                "duration": output_info.get("duration", 0),
                "size": output_size
            }

        except Exception as e:
            logger.error(f"[Composition] Error: {str(e)}")
            return {
                "success": False,
                "error": f"Composition error: {str(e)}"
            }

    async def _compose_with_scenes(
        self,
        base_video: str,
        width: int,
        height: int,
        scene_clips: List[Dict[str, Any]],
        output_path: str
    ):
        """Compose video with scene clips in Picture-in-Picture"""
        # Build filter complex for scene overlays
        filter_parts = []
        inputs = [f"[0:v]"]
        input_files = [base_video]

        for idx, clip in enumerate(scene_clips):
            clip_path = clip.get("path")
            start_time = clip.get("start_time", 0)
            end_time = clip.get("end_time", start_time + 10)
            position = clip.get("position", {})

            # PiP positioning
            pip_scale = position.get("scale", 0.3)
            pip_x = int(position.get("x", 0.65) * width)
            pip_y = int(position.get("y", 0.05) * height)
            pip_w = int(width * pip_scale)
            pip_h = int(height * pip_scale)

            input_files.append(clip_path)
            clip_input_idx = idx + 1

            # Scale and position the clip
            # Using select filter to only show clip during its time range
            filter_parts.append(
                f"[{clip_input_idx}:v]"
                f"scale={pip_w}:{pip_h},"
                f"select=between(t\\,{start_time}\\,{end_time}),"
                f"setpts=PTS-STARTPTS[clip{idx}]"
            )

            # Overlay on base
            if idx == 0:
                overlay_input = inputs[-1]
            else:
                overlay_input = f"[tmp{idx-1}]"

            filter_parts.append(
                f"{overlay_input}[clip{idx}]"
                f"overlay={pip_x}:{pip_y}:enable='between(t\\,{start_time}\\,{end_time})'"
                f"[tmp{idx}]"
            )

        # Final output
        final_filter = ";".join(filter_parts)
        if scene_clips:
            final_filter += f"[tmp{len(scene_clips)-1}]"
        else:
            final_filter += "[0:v]"
        final_filter += "format=yuv420p[outv]"

        # Build FFmpeg command
        cmd = [self.ffmpeg_path, "-y"]

        # Add all inputs
        for input_file in input_files:
            cmd.extend(["-i", input_file])

        # Add filter
        cmd.extend(["-filter_complex", final_filter])
        cmd.extend(["-map", "[outv]", "-map", "0:a", "-c:a", "aac"])
        cmd.append(output_path)

        await self._run_ffmpeg(cmd)

    async def _compose_with_scenes_and_music(
        self,
        base_video: str,
        width: int,
        height: int,
        scene_clips: List[Dict[str, Any]],
        music_path: str,
        output_path: str
    ):
        """Compose video with scenes and background music"""
        # First compose with scenes
        temp_composed = tempfile.mktemp(suffix=".mp4")

        await self._compose_with_scenes(
            base_video,
            width,
            height,
            scene_clips,
            temp_composed
        )

        # Then add music
        await self._add_background_music(temp_composed, music_path, output_path)

        # Cleanup temp file
        try:
            os.remove(temp_composed)
        except:
            pass

    async def _add_background_music(
        self,
        video_path: str,
        music_path: str,
        output_path: str,
        music_volume: float = 0.5,
        fade_in: float = 1.0,
        fade_out: float = 1.0
    ):
        """Mix background music with video"""
        # Get durations
        video_info = await self._get_video_info(video_path)
        music_info = await self._get_video_info(music_path)

        if not video_info or not music_info:
            raise Exception("Cannot read video or music duration")

        video_duration = video_info.get("duration", 0)
        music_duration = music_info.get("duration", 0)

        # Build audio filter for music with fade
        audio_filter = f"afade=t=in:st=0:d={fade_in},afade=t=out:st={music_duration-fade_out}:d={fade_out}"

        # Build FFmpeg command
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex",
            f"[1:a]{audio_filter}[music];[0:a][music]amix=inputs=2:duration=longest[audio]",
            "-map", "0:v:0",
            "-map", "[audio]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]

        await self._run_ffmpeg(cmd)

    async def _get_video_info(self, video_path: str) -> Optional[Dict[str, Any]]:
        """Get video information using ffprobe"""
        ffprobe_path = self.ffmpeg_path.replace("ffmpeg", "ffprobe")

        if not os.path.exists(ffprobe_path):
            # Try alternate paths
            for path in ["/usr/bin/ffprobe", "/usr/local/bin/ffprobe", "/opt/homebrew/bin/ffprobe"]:
                if os.path.exists(path):
                    ffprobe_path = path
                    break

        if not os.path.exists(ffprobe_path):
            logger.warning("ffprobe not found")
            return None

        try:
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration,r_frame_rate",
                "-of", "json",
                video_path
            ]

            result = await self._run_command(cmd)
            data = json.loads(result)

            if data.get("streams"):
                stream = data["streams"][0]
                # Get duration from format if stream doesn't have it
                return {
                    "width": stream.get("width", 1280),
                    "height": stream.get("height", 720),
                    "duration": float(stream.get("duration", 0))
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")

        return None

    async def _run_ffmpeg(self, cmd: List[str], timeout: float = 600.0) -> str:
        """
        Run FFmpeg command with timeout

        Args:
            cmd: Command and arguments
            timeout: Max seconds to wait (default: 600 seconds / 10 minutes)
        """
        logger.info(f"[FFmpeg] {' '.join(cmd)} (timeout: {timeout}s)")
        return await self._run_command(cmd, timeout=timeout)

    async def _run_command(self, cmd: List[str], timeout: float = 600.0) -> str:
        """
        Run system command asynchronously with timeout

        Args:
            cmd: Command and arguments
            timeout: Max seconds to wait before killing process
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
                # Kill the process if it times out
                logger.error(f"[FFmpeg] Process timed out after {timeout}s, terminating")
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    # Force kill if graceful kill doesn't work
                    logger.error("[FFmpeg] Process kill timed out, force killing")
                    process.kill()
                raise Exception(f"FFmpeg process timed out after {timeout} seconds")

            if process.returncode != 0:
                error = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"FFmpeg failed: {error}")

            return stdout.decode() if stdout else ""

        except asyncio.TimeoutError:
            raise Exception(f"FFmpeg operation timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"[FFmpeg] Error: {str(e)}")
            raise


# Singleton instance
_composition_service = None


def get_composition_service() -> VideoCompositionService:
    """Get singleton composition service instance"""
    global _composition_service
    if _composition_service is None:
        _composition_service = VideoCompositionService()
    return _composition_service
