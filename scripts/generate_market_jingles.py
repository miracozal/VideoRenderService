#!/usr/bin/env python3
"""Generate original, market-specific Reels cues as MP3 files.

These tracks are original utility music. They do not reproduce or imitate any
official brand melody. The only external dependency is ``lameenc`` for MP3
encoding (`python -m pip install lameenc`).
"""

from __future__ import annotations

import argparse
import math
import random
import struct
from array import array
from pathlib import Path

import lameenc


SAMPLE_RATE = 44_100
DURATION_SECONDS = 12.0
TAU = math.tau


def midi(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


class Track:
    def __init__(self, duration: float = DURATION_SECONDS) -> None:
        self.duration = duration
        self.length = round(duration * SAMPLE_RATE)
        self.left = array("f", [0.0]) * self.length
        self.right = array("f", [0.0]) * self.length
        self.random = random.Random(20260830)

    def tone(
        self,
        start: float,
        duration: float,
        note: int,
        volume: float,
        *,
        voice: str = "sine",
        pan: float = 0.0,
        attack: float = 0.008,
        release: float = 0.08,
    ) -> None:
        begin = max(0, round(start * SAMPLE_RATE))
        end = min(self.length, round((start + duration) * SAMPLE_RATE))
        if begin >= end:
            return

        frequency = midi(note)
        left_gain = math.sqrt((1.0 - pan) / 2.0)
        right_gain = math.sqrt((1.0 + pan) / 2.0)
        release_start = max(attack, duration - release)

        for sample_index in range(begin, end):
            elapsed = sample_index / SAMPLE_RATE - start
            if elapsed < attack:
                envelope = elapsed / max(attack, 1e-6)
            elif elapsed > release_start:
                envelope = max(0.0, (duration - elapsed) / max(release, 1e-6))
            else:
                envelope = 1.0

            phase = TAU * frequency * elapsed
            if voice == "pluck":
                signal = (
                    math.sin(phase)
                    + 0.42 * math.sin(phase * 2.0)
                    + 0.16 * math.sin(phase * 3.0)
                ) * math.exp(-3.8 * elapsed)
            elif voice == "bell":
                signal = (
                    math.sin(phase)
                    + 0.55 * math.sin(phase * 2.01)
                    + 0.22 * math.sin(phase * 3.98)
                ) * math.exp(-2.7 * elapsed)
            elif voice == "soft_square":
                signal = (
                    math.sin(phase)
                    + math.sin(phase * 3.0) / 3.0
                    + math.sin(phase * 5.0) / 5.0
                ) * 0.72
            elif voice == "pad":
                signal = (
                    math.sin(phase)
                    + 0.24 * math.sin(phase * 0.501)
                    + 0.18 * math.sin(phase * 2.003)
                ) * 0.72
            else:
                signal = math.sin(phase)

            value = signal * envelope * volume
            self.left[sample_index] += value * left_gain
            self.right[sample_index] += value * right_gain

    def kick(self, start: float, volume: float = 0.55) -> None:
        duration = 0.22
        begin = round(start * SAMPLE_RATE)
        end = min(self.length, begin + round(duration * SAMPLE_RATE))
        for sample_index in range(max(0, begin), end):
            elapsed = (sample_index - begin) / SAMPLE_RATE
            frequency = 118.0 * math.exp(-13.0 * elapsed) + 42.0
            phase = TAU * frequency * elapsed
            value = math.sin(phase) * math.exp(-18.0 * elapsed) * volume
            self.left[sample_index] += value * 0.72
            self.right[sample_index] += value * 0.72

    def clap(self, start: float, volume: float = 0.18) -> None:
        duration = 0.11
        begin = round(start * SAMPLE_RATE)
        end = min(self.length, begin + round(duration * SAMPLE_RATE))
        last = 0.0
        for sample_index in range(max(0, begin), end):
            elapsed = (sample_index - begin) / SAMPLE_RATE
            noise = self.random.uniform(-1.0, 1.0)
            high_pass = noise - last * 0.82
            last = noise
            value = high_pass * math.exp(-28.0 * elapsed) * volume
            self.left[sample_index] += value * 0.64
            self.right[sample_index] += value * 0.78

    def shaker(self, start: float, volume: float = 0.06) -> None:
        duration = 0.055
        begin = round(start * SAMPLE_RATE)
        end = min(self.length, begin + round(duration * SAMPLE_RATE))
        previous = 0.0
        for sample_index in range(max(0, begin), end):
            elapsed = (sample_index - begin) / SAMPLE_RATE
            noise = self.random.uniform(-1.0, 1.0)
            value = (noise - previous) * math.exp(-42.0 * elapsed) * volume
            previous = noise
            self.left[sample_index] += value * 0.74
            self.right[sample_index] += value * 0.68

    def encode(self, output_path: Path) -> None:
        peak = max(
            max(abs(value) for value in self.left),
            max(abs(value) for value in self.right),
            1e-6,
        )
        gain = min(0.92 / peak, 1.0)
        fade_samples = round(0.18 * SAMPLE_RATE)
        pcm = bytearray(self.length * 4)

        for index in range(self.length):
            edge_gain = 1.0
            if index < fade_samples:
                edge_gain = index / fade_samples
            elif index >= self.length - fade_samples:
                edge_gain = (self.length - index - 1) / fade_samples

            left = max(-1.0, min(1.0, self.left[index] * gain * edge_gain))
            right = max(-1.0, min(1.0, self.right[index] * gain * edge_gain))
            struct.pack_into("<hh", pcm, index * 4, round(left * 32767), round(right * 32767))

        encoder = lameenc.Encoder()
        encoder.set_bit_rate(192)
        encoder.set_in_sample_rate(SAMPLE_RATE)
        encoder.set_channels(2)
        encoder.set_quality(2)
        encoded = encoder.encode(bytes(pcm)) + encoder.flush()
        output_path.write_bytes(encoded)


def add_rhythm(track: Track, bpm: float, *, clap: bool = True) -> float:
    beat = 60.0 / bpm
    total_beats = math.ceil(track.duration / beat)
    for index in range(total_beats):
        at = index * beat
        track.kick(at, 0.48 if index % 4 in {0, 2} else 0.3)
        if clap and index % 4 in {1, 3}:
            track.clap(at, 0.16)
        track.shaker(at + beat / 2.0, 0.045)
    return beat


def add_chords(track: Track, beat: float, progression: list[tuple[int, int, int]], volume: float) -> None:
    for bar in range(math.ceil(track.duration / (beat * 4))):
        start = bar * beat * 4
        chord = progression[bar % len(progression)]
        for note_index, note in enumerate(chord):
            track.tone(
                start,
                beat * 3.9,
                note,
                volume,
                voice="pad",
                pan=(-0.35 + note_index * 0.35),
                attack=0.14,
                release=0.25,
            )


def migros_track() -> Track:
    track = Track()
    beat = add_rhythm(track, 116)
    progression = [(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)]
    add_chords(track, beat, progression, 0.12)
    motif = [72, 76, 79, 76, 74, 72, 67, 72]
    for index in range(math.ceil(track.duration / (beat / 2))):
        note = motif[index % len(motif)]
        track.tone(index * beat / 2, beat * 0.42, note, 0.33, voice="pluck", pan=-0.18 + 0.36 * (index % 2))
    for bar in range(math.ceil(track.duration / (beat * 4))):
        root = progression[bar % len(progression)][0] - 12
        for step in (0, 2):
            track.tone((bar * 4 + step) * beat, beat * 0.78, root, 0.24, voice="soft_square", pan=-0.1)
    return track


def trendyol_track() -> Track:
    track = Track()
    beat = add_rhythm(track, 128)
    progression = [(62, 65, 69), (58, 62, 65), (55, 58, 62), (60, 64, 67)]
    add_chords(track, beat, progression, 0.105)
    arpeggio = [0, 1, 2, 1, 0, 2, 1, 2]
    for bar in range(math.ceil(track.duration / (beat * 4))):
        chord = progression[bar % len(progression)]
        for step in range(8):
            note = chord[arpeggio[step]] + 12
            track.tone(
                (bar * 4 + step / 2) * beat,
                beat * 0.3,
                note,
                0.29,
                voice="soft_square",
                pan=-0.45 + (step % 4) * 0.3,
                release=0.04,
            )
    logo_motif = [74, 76, 81, 79]
    for cycle in range(3):
        start = 0.16 + cycle * beat * 8
        for index, note in enumerate(logo_motif):
            track.tone(start + index * beat / 2, beat * 0.46, note, 0.22, voice="bell", pan=0.24)
    return track


def hepsiburada_track() -> Track:
    track = Track()
    beat = add_rhythm(track, 108)
    progression = [(57, 61, 64), (54, 57, 61), (50, 54, 57), (52, 56, 59)]
    add_chords(track, beat, progression, 0.115)
    bass_pattern = [0, 0, 7, 4]
    for bar in range(math.ceil(track.duration / (beat * 4))):
        root = progression[bar % len(progression)][0] - 24
        for step, interval in enumerate(bass_pattern):
            track.tone(
                (bar * 4 + step) * beat,
                beat * 0.7,
                root + interval,
                0.33,
                voice="soft_square",
                pan=-0.12,
                release=0.1,
            )
    motif = [69, 73, 76, 73, 71, 69]
    for cycle in range(5):
        start = cycle * beat * 4 + beat * 0.5
        for index, note in enumerate(motif):
            track.tone(start + index * beat / 2, beat * 0.36, note, 0.25, voice="pluck", pan=0.25)
    return track


def gratis_track() -> Track:
    track = Track()
    beat = add_rhythm(track, 122)
    progression = [(65, 69, 72), (60, 64, 67), (62, 65, 69), (64, 68, 71)]
    add_chords(track, beat, progression, 0.12)
    motif = [77, 81, 84, 81, 79, 84, 86, 84]
    for index in range(math.ceil(track.duration / (beat / 2))):
        note = motif[index % len(motif)]
        track.tone(
            index * beat / 2,
            beat * 0.62,
            note,
            0.27,
            voice="bell",
            pan=-0.52 + (index % 4) * 0.34,
            release=0.13,
        )
    for bar in range(math.ceil(track.duration / (beat * 4))):
        root = progression[bar % len(progression)][0] - 24
        for step in range(4):
            track.tone((bar * 4 + step) * beat, beat * 0.6, root, 0.25, voice="sine", pan=-0.08)
    return track


TRACKS = {
    "migros_soundtrack.mp3": migros_track,
    "trendyol_soundtrack.mp3": trendyol_track,
    "hepsiburada_soundtrack.mp3": hepsiburada_track,
    "gratis_soundtrack.mp3": gratis_track,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Assets/Musics"),
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for file_name, factory in TRACKS.items():
        output_path = args.output_dir / file_name
        factory().encode(output_path)
        print(f"created {output_path} ({output_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
