"""WP21 named genotype expansions against SPEC-P2 section 4.2."""
from typing import get_args

from flyonenomics.schema.experiment import Genotype
from flyonenomics.schema.named import NAMED_GENOTYPES, PHASE1_NAMED_GENOTYPES, named_manipulations


def test_phase1_named_genotypes_unchanged() -> None:
    """Keep the Phase 1 four expansions bitwise as SPEC section 6.2."""
    expected = {
        "wild_type": [],
        "fumin": [{"type": "scale_dat", "compartments": "all", "factor": 0.0}],
        "dop1r1_null": [{"type": "scale_receptor", "population": "all", "receptor": "D1", "factor": 0.0}],
        "dopamine_depleted": [{"type": "scale_release", "factor": 0.5}],
    }
    assert PHASE1_NAMED_GENOTYPES == ("wild_type", "fumin", "dop1r1_null", "dopamine_depleted")
    for name, hooks in expected.items():
        assert [item.model_dump() for item in named_manipulations(name)] == hooks
        assert [item.model_dump() for item in Genotype(named=name).expanded()] == hooks


def test_seven_new_named_genotypes() -> None:
    """Expand the seven 1.3 names; dimensionless factors, ordered lists."""
    assert NAMED_GENOTYPES == (
        "wild_type", "fumin", "dat_half", "dopamine_depleted", "dop1r1_null",
        "dop2r_null", "dan_autoreceptor_null", "er_dop1r1_kd", "pam_silenced",
        "cx_dan_silenced", "dfb_silenced",
    )
    assert get_args(Genotype.model_fields["named"].annotation) == NAMED_GENOTYPES
    assert [item.model_dump() for item in named_manipulations("dat_half")] == [
        {"type": "scale_dat", "compartments": "all", "factor": 0.5},
    ]
    assert [item.model_dump() for item in named_manipulations("dop2r_null")] == [
        {"type": "scale_receptor", "population": "all", "receptor": "D2", "factor": 0.0},
    ]
    assert [item.model_dump() for item in named_manipulations("dan_autoreceptor_null")] == [
        {"type": "scale_receptor", "population": "DAN", "receptor": "D2", "factor": 0.0},
        {"type": "scale_receptor", "population": "CX_DAN", "receptor": "D2", "factor": 0.0},
    ]
    assert [item.model_dump() for item in named_manipulations("er_dop1r1_kd")] == [
        {"type": "scale_receptor", "population": "ER", "receptor": "D1", "factor": 0.0},
    ]
    assert [item.model_dump() for item in named_manipulations("pam_silenced")] == [
        {"type": "silence", "population": "PAM"},
    ]
    assert [item.model_dump() for item in named_manipulations("cx_dan_silenced")] == [
        {"type": "silence", "population": "CX_DAN"},
    ]
    assert [item.model_dump() for item in named_manipulations("dfb_silenced")] == [
        {"type": "silence", "population": "dFB"},
    ]


def test_unknown_named_genotype_rejected() -> None:
    """Reject a name outside the section 4.2 table."""
    import pytest
    with pytest.raises(ValueError, match="unknown named genotype"):
        named_manipulations("not_a_genotype")
