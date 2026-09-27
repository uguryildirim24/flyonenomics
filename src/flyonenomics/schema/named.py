"""Named genotype expansions, SPEC section 6.2 and SPEC-P2 section 4.2."""
from flyonenomics.schema.experiment import Manipulation, ScaleDat, ScaleReceptor, ScaleRelease, Silence

# Normative genotype definition, not a tunable scientific constant.
DEPLETED_RELEASE_FRACTION = 0.5
DAT_HALF_FACTOR = 0.5

PHASE1_NAMED_GENOTYPES = ("wild_type", "fumin", "dop1r1_null", "dopamine_depleted")
NAMED_GENOTYPES = (
    "wild_type",
    "fumin",
    "dat_half",
    "dopamine_depleted",
    "dop1r1_null",
    "dop2r_null",
    "dan_autoreceptor_null",
    "er_dop1r1_kd",
    "pam_silenced",
    "cx_dan_silenced",
    "dfb_silenced",
)


def named_manipulations(name: str) -> list[Manipulation]:
    """Expand a genotype name; dimensionless factors, ordered manipulation list."""
    match name:
        case "wild_type":
            return []
        case "fumin":
            return [ScaleDat(type="scale_dat", compartments="all", factor=0)]
        case "dat_half":
            return [ScaleDat(type="scale_dat", compartments="all", factor=DAT_HALF_FACTOR)]
        case "dop1r1_null":
            return [ScaleReceptor(type="scale_receptor", receptor="D1", population="all", factor=0)]
        case "dop2r_null":
            return [ScaleReceptor(type="scale_receptor", receptor="D2", population="all", factor=0)]
        case "dopamine_depleted":
            return [ScaleRelease(type="scale_release", factor=DEPLETED_RELEASE_FRACTION)]
        case "dan_autoreceptor_null":
            return [
                ScaleReceptor(type="scale_receptor", receptor="D2", population="DAN", factor=0),
                ScaleReceptor(type="scale_receptor", receptor="D2", population="CX_DAN", factor=0),
            ]
        case "er_dop1r1_kd":
            return [ScaleReceptor(type="scale_receptor", receptor="D1", population="ER", factor=0)]
        case "pam_silenced":
            return [Silence(type="silence", population="PAM")]
        case "cx_dan_silenced":
            return [Silence(type="silence", population="CX_DAN")]
        case "dfb_silenced":
            return [Silence(type="silence", population="dFB")]
        case _:
            raise ValueError(f"unknown named genotype: {name}")
