import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Extensive mocking to isolate RealtimeClient
mock_modules = [
    'app.config',
    'app.utils.logging',
    'app.services.rag_service',
    'app.voip.prompts',
    'websockets',
    'fastapi',
    'app.voip.media_stream',
    'app.services.report_service'
]
for mod in mock_modules:
    sys.modules[mod] = MagicMock()

# Mock audioop
sys.modules['audioop'] = MagicMock()
import audioop

# Now import RealtimeClient
import app.voip.realtime_client as rt_module
from app.voip.realtime_client import RealtimeClient

async def test_vad_logic():
    print("Starting VAD logic test...")
    client = RealtimeClient("test_call_sid")
    client.is_connected = True
    client.socket = MagicMock()
    client.socket.send = AsyncMock() # Must be AsyncMock
    
    # Configure mock behavior
    mock_rms_values = []
    def mock_rms_fn(*args):
        return mock_rms_values.pop(0) if mock_rms_values else 0
    
    audioop.rms.side_effect = mock_rms_fn
    audioop.ulaw2lin.return_value = b'pcm8k'
    audioop.ratecv.return_value = (b'pcm24k', None)

    # 1. Learning phase
    print("Phase 1: Learning noise floor...")
    learn_frames = rt_module.NOISE_LEARN_FRAMES
    mock_rms_values = [100] * learn_frames
    for _ in range(learn_frames):
        await client.send_audio("ZmFrZQ==")
    
    print(f"Noise floor after learning: {client.noise_floor}")
    assert client.noise_floor == 100, f"Expected 100, got {client.noise_floor}"

    # 2. Noise floor adaptation
    print("Phase 2: Adapting noise floor...")
    # threshold = max(100 * 3.0, 150) = 300
    mock_rms_values = [200]
    await client.send_audio("ZmFrZQ==")
    # self.noise_floor = (100 * 0.99) + (200 * 0.01) = 101.0
    print(f"Noise floor after adaptation: {client.noise_floor}")
    assert abs(client.noise_floor - 101.0) < 0.001, f"Expected ~101.0, got {client.noise_floor}"

    # 3. Speech detection
    print("Phase 3: Detecting speech...")
    # threshold = max(101 * 3.0, 150) = 303
    speech_frames = rt_module.MIN_SPEECH_FRAMES
    mock_rms_values = [1000] * speech_frames
    
    for i in range(speech_frames - 1):
        await client.send_audio("ZmFrZQ==")
        assert client.speech_frame_count == i + 1, f"Expected speech_frame_count {i+1}, got {client.speech_frame_count}"
        assert client.socket.send.call_count == 0, f"Socket should not have sent yet at frame {i+1}"
    
    await client.send_audio("ZmFrZQ==")
    assert client.speech_frame_count == speech_frames, f"Expected speech_frame_count {speech_frames}, got {client.speech_frame_count}"
    assert client.socket.send.call_count == 1, f"Socket should have sent audio, count: {client.socket.send.call_count}"
    print("Speech detection passed!")

    # 4. Silence after speech
    print("Phase 4: Silence after speech...")
    mock_rms_values = [100] # Below threshold
    await client.send_audio("ZmFrZQ==")
    assert client.speech_frame_count == 0, "speech_frame_count should reset on silence"
    
    print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_vad_logic())
