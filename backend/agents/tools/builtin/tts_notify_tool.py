"""TTS notification tool with Edge TTS + Bark/PushDeer"""
import os
import sys
from pathlib import Path
from typing import Optional, Any, Dict, List, Tuple
from urllib.parse import quote
from backend.agents.tools.base_tool import BaseTool, ToolResult
from backend.utils.logger_handler import logger


class TTSNotifyTool(BaseTool):
    """TTS notification via Edge TTS (local) or Bark/PushDeer (phone)."""

    name = "tts_notify"
    description = "Broadcast text via Edge TTS (local speaker) or push to phone via Bark/PushDeer"
    parameters = {
        "text": {
            "type": "string",
            "description": "Text to broadcast",
            "required": True,
        },
        "device": {
            "type": "string",
            "enum": ["phone", "speaker", "auto"],
            "description": "phone=Bark/PushDeer, speaker=Edge TTS, auto=auto select",
        },
        "voice": {
            "type": "string",
            "description": "Edge TTS voice name, default zh-CN-XiaoxiaoNeural",
        },
        "output_dir": {
            "type": "string",
            "description": "Audio output directory for speaker mode, default backend/data/tts_output",
        },
    }

    def __init__(
        self,
        # Edge TTS
        edge_tts_voice: str = "zh-CN-XiaoxiaoNeural",
        tts_output_dir: Optional[str] = None,
        auto_play: bool = False,
        # Phone push (Bark / PushDeer)
        bark_key: Optional[str] = None,
        bark_endpoint: str = "https://api.day.app",
        pushdeer_key: Optional[str] = None,
        pushdeer_endpoint: str = "https://api2.pushdeer.com",
        # WebSocket broadcast to frontend
        broadcast_fn: Optional[Any] = None,
        # Legacy params
        push_fn: Optional[Any] = None,
        tts_api_key: Optional[str] = None,
        tts_endpoint: Optional[str] = None,
    ):
        self._edge_tts_voice = edge_tts_voice
        self._tts_output_dir = tts_output_dir or "backend/data/tts_output"
        self._auto_play = auto_play

        self._bark_key = bark_key
        self._bark_endpoint = bark_endpoint.rstrip("/")
        self._pushdeer_key = pushdeer_key
        self._pushdeer_endpoint = pushdeer_endpoint.rstrip("/")

        self._broadcast_fn = broadcast_fn

        self._push_fn = push_fn
        self._tts_api_key = tts_api_key
        self._tts_endpoint = tts_endpoint

    async def execute(
        self,
        text: str = "",
        device: str = "auto",
        voice: str = "",
        output_dir: str = "",
        **kwargs,
    ) -> ToolResult:
        try:
            text = text.strip()
            if not text:
                return ToolResult(success=False, error="Broadcast text cannot be empty")

            effective_voice = voice or self._edge_tts_voice
            effective_output = output_dir or self._tts_output_dir

            # Routing:
            #   phone / (auto + phone push configured) -> Bark/PushDeer
            #   speaker / (auto + Edge TTS configured) -> Edge TTS
            #   else fallback to legacy or simulated

            # Phone push: phone mode returns regardless; auto mode falls through on failure
            if device == "phone" or (device == "auto" and self._has_phone_push()):
                if self._has_phone_push():
                    result = await self._push_to_phone(text, effective_voice)
                    if device == "phone" or result.success:
                        return result

            # Speaker: speaker mode returns regardless; auto mode falls through on failure
            if device == "speaker" or (device == "auto" and self._edge_tts_voice):
                if self._edge_tts_voice:
                    result = await self._synthesize_to_speaker(text, effective_voice, effective_output)
                    if device == "speaker" or result.success:
                        return result

            if self._push_fn is not None:
                return await self._push_to_device(text, device, voice)

            if self._tts_endpoint and self._tts_api_key:
                return await self._azure_tts(text, device, voice)

            logger.info(f"[TTS SIM] Broadcast: '{text}' to {device}")
            return ToolResult(success=True, data={
                "answer": f"Broadcast via TTS: {text}",
                "text": text, "device": device,
                "duration_seconds": self._estimate_duration(text),
                "simulated": True,
            })

        except Exception as e:
            logger.error(f"TTSNotify tool failed: {e}")
            return ToolResult(success=False, error=f"TTS broadcast failed: {e}")

    # ========== Edge TTS (Plan B) ==========

    async def _synthesize_to_speaker(self, text: str, voice: str, output_dir: str) -> ToolResult:
        """Synthesize audio via Edge TTS and save locally."""
        try:
            import edge_tts
        except ImportError:
            return ToolResult(success=False, error="Edge TTS not installed, run: pip install edge-tts")

        try:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)

            from datetime import datetime
            safe_text = "".join(c for c in text if c.isalnum() or c in " _-")[:30]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tts_{timestamp}_{safe_text}.mp3"
            filepath = out_path / filename

            logger.info(f"[Edge TTS] Synthesizing: '{text[:50]}...' voice={voice}")
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(filepath))

            file_size = filepath.stat().st_size
            duration = self._estimate_duration(text)

            play_info = ""
            if self._auto_play:
                ok = self._play_audio(str(filepath))
                play_info = ", auto-played" if ok else ""

            # Broadcast to frontend
            if self._broadcast_fn:
                try:
                    audio_url = f"/tts/{filename}"
                    await self._broadcast_fn({
                        "type": "ui.notification",
                        "payload": {
                            "message": f"TTS: {text[:40]}...",
                            "audio_url": audio_url,
                            "text": text,
                            "notification_type": "tts",
                        }
                    })
                except Exception as e:
                    logger.warning(f"TTS broadcast failed: {e}")

            return ToolResult(success=True, data={
                "answer": f"TTS file saved: {filename} ({file_size}B, ~{duration:.0f}s){play_info}",
                "text": text,
                "file_path": str(filepath.absolute()),
                "file_name": filename,
                "file_size": file_size,
                "duration_seconds": duration,
                "voice": voice,
            })

        except Exception as e:
            logger.error(f"Edge TTS failed: {e}")
            return ToolResult(success=False, error=f"Edge TTS failed: {e}")

    @staticmethod
    def _play_audio(filepath: str) -> bool:
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(filepath)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", filepath])
            else:
                subprocess.Popen(["aplay", filepath])
            return True
        except Exception as e:
            logger.warning(f"Auto-play failed: {e}")
            return False

    # ========== Phone Push (Plan C) ==========

    def _has_phone_push(self) -> bool:
        return bool(self._bark_key) or bool(self._pushdeer_key)

    async def _push_to_phone(self, text: str, voice: str) -> ToolResult:
        successes: List[str] = []
        failures: List[str] = []

        if self._bark_key:
            ok, msg = await self._push_via_bark(text)
            (successes if ok else failures).append(msg)

        if self._pushdeer_key:
            ok, msg = await self._push_via_pushdeer(text)
            (successes if ok else failures).append(msg)

        if not successes and not failures:
            return ToolResult(success=False, error="No Bark Key or PushDeer Key configured")

        if not successes:
            return ToolResult(success=False, error=" | ".join(failures))

        combined = " | ".join(
            successes + [f"Failed: {f}" for f in failures]
        )

        # Broadcast to frontend
        if self._broadcast_fn:
            try:
                await self._broadcast_fn({
                    "type": "ui.notification",
                    "payload": {
                        "message": combined,
                        "notification_type": "phone_push",
                    }
                })
            except Exception as e:
                logger.warning(f"Push broadcast failed: {e}")

        return ToolResult(success=True, data={
            "answer": combined,
            "text": text,
            "push_results": successes + failures,
        })

    async def _push_via_bark(self, text: str) -> Tuple[bool, str]:
        import aiohttp
        encoded = quote(text, safe="")
        url = f"{self._bark_endpoint}/{self._bark_key}/{encoded}"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        return (False, f"Bark HTTP {resp.status}")
                    logger.info(f"Bark push OK: {text[:40]}...")
                    return (True, "Bark pushed to phone")
        except Exception as e:
            return (False, f"Bark {e}")

    async def _push_via_pushdeer(self, text: str) -> Tuple[bool, str]:
        import aiohttp
        url = f"{self._pushdeer_endpoint}/message/push"
        payload = {
            "pushkey": self._pushdeer_key,
            "text": "Robot TTS",
            "desp": text,
            "type": "markdown",
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, timeout=10) as resp:
                    if resp.status != 200:
                        return (False, f"PushDeer HTTP {resp.status}")
                    logger.info(f"PushDeer push OK: {text[:40]}...")
                    return (True, "PushDeer pushed to phone")
        except Exception as e:
            return (False, f"PushDeer {e}")

    # ========== Legacy interface ==========

    async def _push_to_device(self, text: str, device: str, voice: str) -> ToolResult:
        payload = {
            "type": "tts",
            "text": text,
            "device": device,
            "voice": voice or "default",
        }
        try:
            if hasattr(self._push_fn, "__call__"):
                result = await self._push_fn(payload)
                return ToolResult(success=True, data={
                    "answer": f"Pushed to {device}: {text}",
                    "text": text, "device": device,
                    "push_result": result,
                })
            return ToolResult(success=False, error="Push function not available")
        except Exception as e:
            return ToolResult(success=False, error=f"Push failed: {e}")

    async def _azure_tts(self, text: str, device: str, voice: str) -> ToolResult:
        endpoint = self._tts_endpoint or ""
        try:
            import aiohttp
            headers = {
                "Authorization": f"Bearer {self._tts_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "text": text,
                "voice": voice or "zh-CN-XiaoxiaoNeural",
                "format": "audio-16khz-32kbitrate-mono-mp3",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{endpoint}/cognitiveservices/v1",
                    headers=headers, json=payload, timeout=30,
                ) as resp:
                    if resp.status != 200:
                        return ToolResult(success=False, error=f"Azure TTS failed: HTTP {resp.status}")
                    audio_data = await resp.read()
            return ToolResult(success=True, data={
                "answer": f"Azure TTS synthesized ({len(audio_data)} bytes)",
                "text": text, "device": device,
                "audio_size": len(audio_data),
            })
        except Exception as e:
            return ToolResult(success=False, error=f"Azure TTS failed: {e}")

    @staticmethod
    def _estimate_duration(text: str) -> float:
        return max(1.0, len(text) / 4.0)
