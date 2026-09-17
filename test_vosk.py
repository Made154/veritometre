import sounddevice as sd
import queue, json
from vosk import Model, KaldiRecognizer

DEVICE_RATE = 48000

model = Model("vosk-model-fr.22")
q = queue.Queue()

def callback(indata, frames, time, status):
	q.put(bytes(indata))

with sd.RawInputStream(samplerate=DEVICE_RATE, blocksize=8000, dtype='int16', channels=1, device=2, callback=callback):
	rec = KaldiRecognizer(model, 48000)
	print("Parlez...")
	while True:
		data = q.get()
		if rec.AcceptWaveform(data):
			print(json.loads(rec.Result())["text"])
