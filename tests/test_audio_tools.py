import os, wave
import numpy as np
import sfx_gen, audio_tidy


def test_sfx_presets_deterministic(tmp_path):
    for kind in ["coin", "jump", "laser", "explosion", "hit", "powerup", "blip"]:
        p = sfx_gen.preset(kind, np.random.default_rng(5))
        x = sfx_gen.synth(p, 5)
        assert 0.02 < len(x) / sfx_gen.SR < 2.0
        assert np.abs(x).max() <= 1.0 and np.abs(x).max() > 0.05
        y = sfx_gen.synth(sfx_gen.preset(kind, np.random.default_rng(5)), 5)
        assert np.array_equal(x, y)
    sfx_gen.main(["coin", "-n", "3", "-o", str(tmp_path / "s")])
    files = sorted(os.listdir(tmp_path / "s"))
    assert len([f for f in files if f.endswith(".wav")]) == 3
    with wave.open(str(tmp_path / "s" / "coin_0000.wav")) as wf:
        assert wf.getframerate() == 44100 and wf.getsampwidth() == 2


def test_audio_tidy_trim_normalize(tmp_path):
    sr = 48000
    t = np.arange(sr) / sr
    tone = 0.1 * np.sin(2 * np.pi * 440 * t)
    sig = np.concatenate([np.zeros(sr // 2), tone, np.zeros(sr // 2)])
    st = np.stack([sig, sig], 1)
    src = tmp_path / "in.wav"
    audio_tidy.write_wav(str(src), st, sr)
    x, r = audio_tidy.read_wav(str(src))
    assert r == sr and x.shape[1] == 2
    audio_tidy.main([str(src), "-o", str(tmp_path / "out"), "--peak", "-1", "--mono", "--rate", "44100"])
    y, r2 = audio_tidy.read_wav(str(tmp_path / "out" / "in.wav"))
    assert r2 == 44100 and y.shape[1] == 1
    assert abs(len(y) / r2 - 1.02) < 0.05  # 1s tone + 2x10ms pad
    assert abs(audio_tidy.db(np.abs(y).max()) - (-1)) < 0.2
    z, _ = audio_tidy.process(x, sr, rms=-20)
    assert abs(audio_tidy.stats(z)["rms_db"] - (-20)) < 0.5
