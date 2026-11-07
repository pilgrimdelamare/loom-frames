import io, json, sys, urllib.request

import numpy as np
import sherpa_onnx as so
import soundfile as sf


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'render'}), timeout=60) as r:
        return r.read()


def main():
    job = json.loads(get(sys.argv[1]))
    d = 'm/sherpa-onnx-supertonic-3-tts-int8-2026-05-11/'
    tts = so.OfflineTts(so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(supertonic=so.OfflineTtsSupertonicModelConfig(
        duration_predictor=d + 'duration_predictor.int8.onnx', text_encoder=d + 'text_encoder.int8.onnx',
        vector_estimator=d + 'vector_estimator.int8.onnx', vocoder=d + 'vocoder.int8.onnx', tts_json=d + 'tts.json',
        unicode_indexer=d + 'unicode_indexer.bin', voice_style=d + 'voice.bin'), num_threads=4)))
    g = so.GenerationConfig()
    g.sid = int(job.get('voice', 7))
    g.num_steps = int(job.get('steps', 12))
    g.speed = float(job.get('speed', 1.05))
    g.extra['lang'] = job.get('lang', 'it')
    a = tts.generate(job['text'], g)
    x = np.clip(np.asarray(a.samples, dtype=np.float32), -1, 1)
    n = int(len(x) * 48000 / a.sample_rate)
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    buf = io.BytesIO()
    sf.write(buf, y, 48000, format='OGG', subtype='OPUS')
    req = urllib.request.Request(job['done'], data=buf.getvalue(), method='POST', headers={'Content-Type': 'audio/ogg', 'User-Agent': 'render'})
    urllib.request.urlopen(req, timeout=60).read()


main()
