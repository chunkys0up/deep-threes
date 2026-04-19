import os
from dotenv import load_dotenv
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

load_dotenv()

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

for voice in voices.voices:
    print(f"{voice.name}")



audio = client.text_to_speech.convert(
    text="He pulls up from deep... BANG! What a shot!",
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
    voice_settings=VoiceSettings(
        stability=0.3,
        similarity_boost=0.9,
        style=0.7,
        use_speaker_boost=True,
        speed=1.1,
    ),
    seed=42,
)

play(audio)

with open("outout.mp3", "wb") as f:
    for chunk in audio:
        if chunk:
            f.write(chunk)
