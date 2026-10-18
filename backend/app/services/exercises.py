"""Catalogue of common gym exercises, in French, grouped by muscle group.

Anything else can still be typed freely: the catalogue only makes the usual
choices one tap away.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Exercise:
    name: str
    group: str
    bodyweight: bool = False  # True: usually done without added load


EXERCISES: tuple[Exercise, ...] = (
    # Legs
    Exercise("Squat", "Jambes"),
    Exercise("Squat avant", "Jambes"),
    Exercise("Fentes", "Jambes"),
    Exercise("Presse à cuisses", "Jambes"),
    Exercise("Leg extension", "Jambes"),
    Exercise("Leg curl", "Jambes"),
    Exercise("Soulevé de terre roumain", "Jambes"),
    Exercise("Hip thrust", "Jambes"),
    Exercise("Mollets debout", "Jambes"),
    # Chest
    Exercise("Développé couché", "Pectoraux"),
    Exercise("Développé incliné haltères", "Pectoraux"),
    Exercise("Écarté à la poulie", "Pectoraux"),
    Exercise("Pompes", "Pectoraux", bodyweight=True),
    Exercise("Dips", "Pectoraux", bodyweight=True),
    # Back
    Exercise("Soulevé de terre", "Dos"),
    Exercise("Tractions", "Dos", bodyweight=True),
    Exercise("Rowing barre", "Dos"),
    Exercise("Rowing haltère", "Dos"),
    Exercise("Tirage vertical", "Dos"),
    Exercise("Tirage horizontal", "Dos"),
    # Shoulders
    Exercise("Développé militaire", "Épaules"),
    Exercise("Élévations latérales", "Épaules"),
    Exercise("Oiseau", "Épaules"),
    Exercise("Face pull", "Épaules"),
    # Arms
    Exercise("Curl biceps", "Bras"),
    Exercise("Curl marteau", "Bras"),
    Exercise("Extension triceps à la poulie", "Bras"),
    Exercise("Barre au front", "Bras"),
    # Core
    Exercise("Gainage", "Abdos", bodyweight=True),
    Exercise("Crunch", "Abdos", bodyweight=True),
    Exercise("Relevés de jambes", "Abdos", bodyweight=True),
    Exercise("Russian twist", "Abdos"),
)

CUSTOM_GROUP = "Mes exercices"  # exercises typed freely in earlier sessions
