"""Push-to-talk voice REPL for the CLI.

The loop:

1. Print the input indicator and wait for ENTER.
2. Start capturing microphone PCM frames with :mod:`sounddevice`.
3. Stop capture on the next ENTER (or Ctrl-C).
4. Transcribe the capture locally with :mod:`faster-whisper`.
5. Send the transcript to Jarvis and stream the reply, speaking each chunk
   aloud. A second ENTER interrupts playback, captures the barge-in, and
   loops back to step 4.
"""

from __future__ import annotations

import asyncio
import sys

from rich.console import Console

from jarvis.cli.client import JarvisClient
from jarvis.voice.stt import SpeechRecognizer
from jarvis.voice.tts import Speaker, split_for_speech

console = Console()


async def run_voice(
    base_url: str,
    api_key: str,
    session: str | None,
    device: int | None,
    whisper_model: str,
) -> None:
    try:
        import sounddevice as sd
    except ImportError as exc:
        console.print(
            "[red]voice mode requires the [voice] extra: "
            "pip install 'jarvis-assistant[voice]'[/]"
        )
        console.print(f"[dim]{exc}[/]")
        return

    recognizer = SpeechRecognizer(model=whisper_model)
    speaker = Speaker()
    sample_rate = 16000
    channels = 1

    async with JarvisClient(base_url, api_key) as client:
        session_id = session or (await client.create_session(title="voice"))["id"]
        console.print(f"[bold cyan]Voice mode.[/] session={session_id[:8]}  [dim](ENTER to talk, Ctrl-C to exit)[/]")

        loop = asyncio.get_event_loop()

        while True:
            try:
                await loop.run_in_executor(None, input, "\n[press ENTER to start recording] ")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]bye.[/]")
                return

            # -- record
            console.print("[red]● recording... [press ENTER to stop][/]")
            frames: list[bytes] = []

            def callback(indata, frames_count, time_info, status, _frames=frames) -> None:
                _frames.append(bytes(indata))

            stream = sd.RawInputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
                device=device,
                callback=callback,
            )
            stream.start()
            try:
                await loop.run_in_executor(None, input, "")
            except (KeyboardInterrupt, EOFError):
                pass
            stream.stop()
            stream.close()

            if not frames:
                console.print("[yellow](no audio captured)[/]")
                continue

            audio_bytes = b"".join(frames)
            console.print("[dim]transcribing...[/]")
            result = await asyncio.to_thread(
                recognizer.stream, [audio_bytes], sample_rate=sample_rate
            )
            if not result.text.strip():
                console.print("[yellow](didn't catch that, sir)[/]")
                continue
            console.print(f"[bold]you>[/] {result.text}")

            # -- send & stream reply
            console.print("[bold green]jarvis>[/] ", end="")
            reply_text: list[str] = []
            interrupt = asyncio.Event()
            keypress_task = asyncio.create_task(_watch_interrupt(interrupt))
            async for ev in client.chat_stream(result.text, session_id):
                kind = ev.get("kind")
                data = ev.get("data", {})
                if interrupt.is_set():
                    await client.interrupt(session_id)
                    break
                if kind == "token":
                    text = data.get("text", "")
                    console.print(text, end="")
                    sys.stdout.flush()
                    reply_text.append(text)
                elif kind == "approval_request":
                    console.print(
                        f"\n[yellow]Approval required for {data.get('tool')} (risk={data.get('overall')}). "
                        f"Use /approve from another terminal or the web UI.[/]"
                    )
                elif kind == "tool_call_end":
                    mark = "[green]✓[/]" if data.get("ok") else "[red]✗[/]"
                    console.print(f"\n{mark} {data.get('name')}", end="")
                elif kind == "error":
                    console.print(f"\n[red]{data.get('message')}[/]")
                elif kind == "done":
                    break
            console.print()
            keypress_task.cancel()

            # -- speak the reply with barge-in
            spoken = "".join(reply_text).strip()
            if not spoken:
                continue
            console.print("[dim]speaking... (ENTER to interrupt)[/]")
            barge_in = asyncio.Event()
            barge_task = asyncio.create_task(_watch_interrupt(barge_in))
            try:
                chunks_played = await speaker.speak(spoken, interrupt=barge_in)
            except RuntimeError as exc:
                console.print(f"[yellow]TTS unavailable: {exc}[/]")
                chunks_played = 0
            barge_task.cancel()
            total = len(split_for_speech(spoken))
            if barge_in.is_set() and chunks_played < total:
                console.print("[yellow](interrupted)[/]")


async def _watch_interrupt(event: asyncio.Event) -> None:
    """Set ``event`` when ENTER is pressed. Cancelled cleanly otherwise."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, sys.stdin.readline)
        event.set()
    except asyncio.CancelledError:
        return
