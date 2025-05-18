import speech_recognition as sr
import numpy as np
import torch


def audio_to_numpy(audio_data):
    """Convert AudioData to numpy array."""
    audio_bytes = audio_data.get_raw_data()
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
    audio_np = audio_np.astype(np.float32) / 32768.0  # Normalize audio
    return audio_np

def resample_audio(audio_np, original_rate=44100, target_rate=16000):
    """Resample the audio numpy array to the target rate."""
    audio_tensor = torch.from_numpy(audio_np).unsqueeze(0).unsqueeze(0)  # Shape (1, 1, length)
    resampled_audio = torch.nn.functional.interpolate(audio_tensor, scale_factor=target_rate/original_rate, mode='linear', align_corners=False)
    return resampled_audio.squeeze().numpy()

def speech_to_text(model):
    """Transcribe speech to text using Whisper model."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for your answer...")
        audio_data = recognizer.listen(source)

    audio_np = audio_to_numpy(audio_data)  # Convert audio to numpy array
    audio_np = audio_np.flatten()  # Flatten numpy array
    resampled_audio = resample_audio(audio_np)  # Resample audio to 16000 Hz

    result = model.transcribe(resampled_audio)  # Transcribe using Whisper
    text = result['text']
    print(f"Recognized text: {text}")
    return text