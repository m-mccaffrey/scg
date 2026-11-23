"""Element grouping and formula display helpers for the selection lists."""

from typing import Dict, List

# Groups shown in the element selection list, in display order. Each element appears once;
# anything in a database that isn't listed here is shown under "Other".
ELEMENT_GROUPS: Dict[str, List[str]] = {
    "Glass formers": ["Si", "B", "P", "Ge", "As", "Sb"],
    "Alkalis": ["Li", "Na", "K", "Rb", "Cs", "Fr"],
    "Alkaline earths": ["Be", "Mg", "Ca", "Sr", "Ba", "Ra"],
    "Rare earths": ["Sc", "Y", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu"],
    "Transition metals": [
        "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
        "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
        "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    ],
    "Post-transition metals": ["Al", "Ga", "In", "Sn", "Tl", "Pb", "Bi", "Po"],
    "Chalcogens": ["O", "S", "Se", "Te"],
    "Halogens": ["F", "Cl", "Br", "I", "At"],
    "Actinides": ["Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr"],
    "Other": ["H", "C", "N", "He", "Ne", "Ar", "Kr", "Xe", "Rn"],
}

OTHER_GROUP = "Other"


def group_elements(elements: List[str]) -> Dict[str, List[str]]:
    """Arrange the given elements into ELEMENT_GROUPS order, dropping empty groups."""
    present = set(elements)
    placed = set()
    groups: Dict[str, List[str]] = {}
    for group, members in ELEMENT_GROUPS.items():
        found = [e for e in members if e in present]
        placed.update(found)
        if found:
            groups[group] = found
    leftovers = [e for e in elements if e not in placed]
    if leftovers:
        groups.setdefault(OTHER_GROUP, []).extend(leftovers)
    return groups


_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def to_subscript(formula: str) -> str:
    """Display form of a chemical formula: digits become subscripts, e.g. Al2O3 -> Al₂O₃."""
    return formula.translate(_SUBSCRIPTS)
