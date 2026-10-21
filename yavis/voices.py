"""Stimmen-Katalog: Piper-Basismodelle x Stil-Profile (Tempo, Betonung, Tonhoehe).
EHRLICH: Das sind Varianten weniger echter Basisstimmen, keine 30+ voellig verschiedenen Sprecher.
Modellnamen vor dem Release gegen die aktuelle Piper-Stimmenliste pruefen."""
from __future__ import annotations
from dataclasses import dataclass

FEMALE_BASES = {"eva_k-x_low": "Eva", "kerstin-low": "Kerstin", "ramona-low": "Ramona"}
MALE_BASES = {"thorsten-medium": "Thorsten", "thorsten-high": "Thorsten HD", "karlsson-low": "Karlsson",
              "pavoque-low": "Pavoque", "thorsten_emotional-medium": "Thorsten Emotional"}
# Stil: (length_scale = Tempo, noise_scale, noise_w, pitch-Faktor fuer Nachbearbeitung)
FEMALE_STYLES = {"Warm": (1.0, .667, .8, 1.0), "Samtig & verfuehrerisch": (1.15, .5, .6, .95),
                 "Hell & freundlich": (.95, .7, .8, 1.08), "Streng": (.9, .4, .5, .92),
                 "Fluesternd": (1.25, .3, .4, .98), "Energisch": (.85, .75, .9, 1.05)}
MALE_STYLES = {"Normal": (1.0, .667, .8, 1.0), "Hart & tief": (1.05, .4, .5, .82),
               "Ruhig": (1.2, .5, .6, .95), "Energisch": (.88, .75, .9, 1.04)}


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    model: str
    gender: str
    length_scale: float
    noise_scale: float
    noise_w: float
    pitch: float


def build_catalog() -> list[Voice]:
    out = []
    for gender, bases, styles in (("w", FEMALE_BASES, FEMALE_STYLES), ("m", MALE_BASES, MALE_STYLES)):
        for model, name in bases.items():
            for style, (ls, ns, nw, pitch) in styles.items():
                out.append(Voice(f"{gender}:{model}:{style}", f"{name} - {style}", f"de_DE-{model}", gender, ls, ns, nw, pitch))
    return out


def get_voice(voice_id: str) -> Voice:
    for v in build_catalog():
        if v.id == voice_id:
            return v
    raise KeyError(voice_id)


def piper_args(v: Voice) -> list[str]:
    return ["--model", v.model, "--length_scale", str(v.length_scale),
            "--noise_scale", str(v.noise_scale), "--noise_w", str(v.noise_w)]
