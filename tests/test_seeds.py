"""Pin section 3.6 streams, Brian seeds and matched-arm pairing."""
import numpy as np
import pytest
from flyonenomics.orchestrator.seeds import stream,brian_seed,ENGINE,BEHAVIOUR,ENCODER,JITTER,LIVE,ANALYSIS

EXPECTED = {ENGINE:[2687398953,1753626608,1031707218,2444953432],BEHAVIOUR:[2343904778,938441645,3078219797,1057059332],ENCODER:[3962930822,888344756,3971339280,1640507488],JITTER:[2272564311,3064794683,602987169,2749776506],LIVE:[1567123129,4127910942,601211996,2538195606],ANALYSIS:[529674926,3929111287,1407066330,1917601230]}


@pytest.mark.parametrize('component',list(EXPECTED))
def test_known_streams_and_pairing(component: int) -> None:
    """Pin four uint32 draws and paired-arm identity; units none, arrays (4,)."""
    a=stream(20260912,1,0,component).integers(0,2**32,4)
    b=stream(20260912,1,0,component).integers(0,2**32,4)
    np.testing.assert_array_equal(a,EXPECTED[component]);np.testing.assert_array_equal(a,b)
    assert not np.array_equal(a,stream(20260912,1,1,component).integers(0,2**32,4))


def test_brian_values() -> None:
    """Pin uint32 Brian seeds separately from generator draws; scalar integers."""
    assert brian_seed(20260912,1,0)==2194859040
    assert brian_seed(20260912,2,3)==738872750
    with pytest.raises(ValueError):brian_seed(-1,1,0)
    with pytest.raises(ValueError):stream(1,1,1,0)
