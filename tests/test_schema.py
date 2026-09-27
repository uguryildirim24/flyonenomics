"""Strict schema, matching, layers, names, topology and overlap contracts."""
import copy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError
from flyonenomics.schema import Experiment, load_experiment
from flyonenomics.schema.experiment import Manipulation, Phase, Probe
from flyonenomics.orchestrator.phases import build_topology, probe_inputs

ROOT = Path(__file__).resolve().parents[1]


def example() -> dict:
    """Return the sugar example; units seconds/Hz, nested scalar mapping."""
    return json.loads((ROOT / 'data/experiments/sugar-reflex.json').read_text())


def registry() -> SimpleNamespace:
    """Return overlapping test populations; int32 indices (m,), four neurons."""
    pops = {name: SimpleNamespace(name=name, idx=np.array(idx, dtype=np.int32)) for name, idx in
            {'sugar_GRN_R':[2,0], 'MN9':[1], 'TuBu':[0,3], 'DAN':[3], 'CX_DAN':[3]}.items()}
    return SimpleNamespace(n=4, population=lambda name:pops[name], compartments=lambda:[])


@pytest.mark.parametrize('path',[(),('substrate',),('layers',),('record',),('arms',0),('arms',0,'genotype'),('arms',1,'genotype','manipulations',0),('arms',0,'protocol',0),('arms',0,'protocol',0,'params')])
def test_unknown_fields(path: tuple) -> None:
    """Reject unknown fields at each nested level; units none, scalar extra."""
    raw=example(); node=raw
    for key in path: node=node[key]
    node['unknown']=True
    with pytest.raises(ValidationError,match='extra_forbidden|unexpected_keyword_argument'):
        Experiment.model_validate(raw)


@pytest.mark.parametrize('hook',[
 {'type':'silence','population':'MN9'}, {'type':'disconnect','population':'MN9'},
 {'type':'activate','population':'MN9','rate_hz':20}, {'type':'shift_threshold','population':'MN9','delta_mv':3},
 {'type':'scale_gain','population':'MN9','factor':2}, {'type':'scale_receptor','population':'all','receptor':'D1','factor':0},
 {'type':'scale_dat','compartments':'all','factor':0}, {'type':'scale_release','factor':0.5}])
def test_each_manipulation_forbids_extras(hook: dict) -> None:
    """Reject extra hook keys; units per hook, scalar mapping."""
    TypeAdapter(Manipulation).validate_python(hook)
    with pytest.raises(ValidationError):
        TypeAdapter(Manipulation).validate_python({**hook,'surprise':0})


@pytest.mark.parametrize('phase',[
 {'type':'dose','drug':'methylphenidate','c_food_mm':0.5}, {'type':'washout','drug':'vehicle'},
 {'type':'wait','hours':2}, {'type':'repeat','n':2,'spacing_hours':2,'body':[{'type':'wait','hours':1}]},
 {'type':'probe','assay':'spontaneous','label':'x','duration_s':0.2,'params':{'input':{'population':'MN9','rate_hz':1,'bad':0}}},
 {'type':'probe','assay':'buridan','label':'x','duration_s':20,'params':{'distractor':{'azimuth':90,'flicker_hz':3,'contrast':1,'onset_s':5,'duration_s':10,'bad':0}}},
 {'type':'probe','assay':'open_loop_steering','label':'x','duration_s':20,'params':{'bad':0}},
])
def test_each_phase_forbids_extras(phase: dict) -> None:
    """Reject extra phase, input and visual episode keys; units per phase."""
    if phase['type']!='probe':phase['bad']=0
    with pytest.raises(ValidationError):TypeAdapter(Phase).validate_python(phase)


def test_matching_and_drug_exception() -> None:
    """Report first mismatched field and allow only drug-name variation; Hz/mM."""
    raw=example();raw['arms'][1]['protocol'][1]['params']['rate_hz']=51
    with pytest.raises(ValidationError,match=r'protocol\[1\].params.rate_hz'):
        Experiment.model_validate(raw)
    raw=example()
    for arm,drug in zip(raw['arms'],('vehicle','methylphenidate')):
        arm['protocol'].insert(0,{'type':'dose','drug':drug,'c_food_mm':0.5})
    Experiment.model_validate(raw)
    raw['arms'][1]['protocol'][0]['c_food_mm']=1
    with pytest.raises(ValidationError,match='c_food_mm'):Experiment.model_validate(raw)


@pytest.mark.parametrize('key,value',[('seed',-1),('seed',2**32),('seed',1.2),('seeds',[1,1]),('name','../run'),('name','UPPER')])
def test_domains(key: str,value: object) -> None:
    """Reject out-of-domain identity fields; uint32 seeds, scalar/list fields."""
    raw=example();raw[key]=value
    with pytest.raises(ValidationError):Experiment.model_validate(raw)


def test_malecns_is_a_distinct_connectome_version() -> None:
    """MaleCNS is admitted under its own release name, never the FlyWire label."""
    from flyonenomics.datasets import MaleCNSAdapter, get_dataset_adapter

    raw = example()
    raw["substrate"]["connectome_version"] = "male-cns:v1.0"
    experiment = Experiment.model_validate(raw)
    assert experiment.substrate.connectome_version == "male-cns:v1.0"
    assert isinstance(get_dataset_adapter(experiment.substrate.connectome_version), MaleCNSAdapter)
    with pytest.raises(KeyError, match="unknown connectome version"):
        get_dataset_adapter("male-cns")


def test_repeat_expansion_washout_layers_and_hash() -> None:
    """Repeat spacing and expanded matching; hours/seconds, phase lists."""
    raw=example();body=[{'type':'dose','drug':'vehicle','c_food_mm':0.5},raw['arms'][0]['protocol'][0]]
    for arm in raw['arms']:arm['protocol']=[{'type':'repeat','n':2,'spacing_hours':1,'body':body}]
    e=Experiment.model_validate(raw)
    assert [p.type for p in e.arms[0].expanded()]==['dose','probe','wait','dose','probe']
    assert e.protocol_hash()==Experiment.model_validate_json(e.canonical_json()).protocol_hash()
    raw['arms'][0]['protocol'][0]['body']=[{'type':'washout','drug':'methylphenidate'},body[1]]
    with pytest.raises(ValidationError,match='must follow'):Experiment.model_validate(raw)
    for name,flag in [('fumin','transporter_C'),('dop1r1_null','dopamine_A'),('dopamine_depleted','transporter_C')]:
        raw=example();raw['layers'][flag]=False;raw['arms'][0]['genotype']['named']=name
        with pytest.raises(ValidationError,match='layer off'):Experiment.model_validate(raw)


def test_ablation_override_scope() -> None:
    """Only explicit ablation permits the two overrides; flags are scalar."""
    raw=example();raw['arms'][0]['layers']={'dopamine_A':False}
    with pytest.raises(ValidationError,match='ablation'):Experiment.model_validate(raw)
    raw['comparison']='ablation';e=Experiment.model_validate(raw)
    assert not e.arm_layers(e.arms[0]).dopamine_A and e.arm_layers(e.arms[1]).dopamine_A
    raw['arms'][0]['layers']['background']=False
    with pytest.raises(ValidationError):Experiment.model_validate(raw)


def test_overlap_warning_topology_order_and_resolution() -> None:
    """Keep engine topology imports in a child; Hz, int32 arrays (m,)."""
    result = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'tests'); from test_schema import _check_overlap; _check_overlap()"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def _check_overlap() -> None:
    """Warn on named overlaps, preserve bank order and sum extended Hz (m,)."""
    raw=example();raw['arms'][0]['genotype']['manipulations']=[{'type':'activate','population':'TuBu','rate_hz':50}]
    e=Experiment.model_validate(raw);reg=registry()
    with pytest.warns(UserWarning,match='sugar_GRN_R and TuBu'):e.resolve(reg)
    plan=build_topology(e,reg)
    assert plan.topology.upstream_banks[0].idx.tolist()==[2,0]
    assert plan.topology.extended_idx.tolist()==[0,2,3]
    active,rates,overlap=probe_inputs(plan,e.arms[0].protocol[0],e.arms[0],reg)
    assert active==[True] and rates.tolist()==[50,0,50] and overlap.tolist()==[0]
    _,rates,overlap=probe_inputs(plan,e.arms[0].protocol[1],e.arms[0],reg)
    assert rates.tolist()==[200,150,50] and not len(overlap)
    raw['record']['rates']=['missing']
    with pytest.raises(ValueError,match='unknown population'):Experiment.model_validate(raw).resolve(reg)


def test_v630_assay_restriction_and_numeric_limits() -> None:
    """Validate the v630 assay domain and finite numeric bounds; seconds/Hz."""
    raw=example();raw['substrate']['connectome_version']='630';Experiment.model_validate(raw)
    for arm in raw['arms']:
        arm['protocol'][0].update(assay='buridan',params={})
    with pytest.raises(ValidationError,match='630'):Experiment.model_validate(raw)
    for value in (float('nan'),float('inf'),-1,1001):
        with pytest.raises(ValidationError):TypeAdapter(Manipulation).validate_python({'type':'activate','population':'MN9','rate_hz':value})
    for value in (0,0.015,121):
        p=example()['arms'][0]['protocol'][0];p['duration_s']=value
        with pytest.raises(ValidationError):Probe.model_validate(p)


@pytest.mark.parametrize('key,value',[
 ('name',''),('name','x'*65),('seed',True),('seed',2**32),
 ('seeds',[]),('seeds',[-1]),('seeds',[2**32]),('seeds',[False]),('seeds',[1.5]),
 ('arms',[]),('schema_version','1.1')])
def test_identity_domain_edges(key: str, value: object) -> None:
    """Reject invalid names and uint32 seed domains; scalar/list inputs."""
    raw=example();raw[key]=value
    with pytest.raises(ValidationError):Experiment.model_validate(raw)


@pytest.mark.parametrize('label',['','Bad','a_b','a'*33,'../x'])
def test_arm_label_domain(label: str) -> None:
    """Reject invalid arm identifiers; units none, scalar strings."""
    raw=example();raw['arms'][0]['label']=label
    with pytest.raises(ValidationError):Experiment.model_validate(raw)


@pytest.mark.parametrize('field,phase,values',[
 ('duration_s',{'type':'probe','assay':'spontaneous','label':'p','params':{}},[0,-1,120.01,0.015,119.99999999,float('nan'),float('inf')]),
 ('c_food_mm',{'type':'dose','drug':'vehicle'},[0,-1,100.01,float('nan'),float('inf')]),
 ('hours',{'type':'wait'},[0,-1,240.01,float('nan'),float('inf')]),
 ('n',{'type':'repeat','spacing_hours':0,'body':[{'type':'wait','hours':1}]},[1,21,2.5,True]),
 ('spacing_hours',{'type':'repeat','n':2,'body':[{'type':'wait','hours':1}]},[-1,241,float('nan'),float('inf')]),
])
def test_all_phase_numeric_domains(field: str, phase: dict, values: list) -> None:
    """Reject phase bounds in seconds, hours and mM; scalar numeric candidates."""
    for value in values:
        with pytest.raises(ValidationError):TypeAdapter(Phase).validate_python({**phase,field:value})


@pytest.mark.parametrize('kind,field,base,values',[
 ('shift_threshold','delta_mv',{'population':'MN9'},[-20.01,20.01,float('nan'),float('inf')]),
 ('scale_gain','factor',{'population':'MN9'},[-0.01,10.01,float('nan'),float('inf')]),
 ('scale_receptor','factor',{'population':'all','receptor':'D1'},[-0.01,10.01,float('nan'),float('inf')]),
 ('scale_dat','factor',{'compartments':'all'},[-0.01,10.01,float('nan'),float('inf')]),
 ('scale_release','factor',{},[-0.01,10.01,float('nan'),float('inf')]),
])
def test_manipulation_numeric_domains(kind: str, field: str, base: dict, values: list) -> None:
    """Reject nonfinite/out-of-range mV and scaling factors; scalar candidates."""
    for value in values:
        with pytest.raises(ValidationError):TypeAdapter(Manipulation).validate_python({'type':kind,**base,field:value})


@pytest.mark.parametrize('drug',['amphetamine','atomoxetine','caffeine','cocaine','unknown'])
def test_unsupported_drugs(drug: str) -> None:
    """Reject unsupported drug identifiers; units none, scalar strings."""
    for phase in ({'type':'dose','c_food_mm':1},{'type':'washout'}):
        with pytest.raises(ValidationError):TypeAdapter(Phase).validate_python({**phase,'drug':drug})


def test_protocol_rejections_and_resolution() -> None:
    """Reject invalid phases and empty population selections; int32 indices (0,)."""
    raw=example();raw['arms'][1]['label']=raw['arms'][0]['label']
    with pytest.raises(ValidationError,match='labels'):Experiment.model_validate(raw)
    raw=example();raw['arms'][0]['protocol']=[{'type':'wait','hours':1}]
    with pytest.raises(ValidationError,match='probe'):Experiment.model_validate(raw)
    repeat={'type':'repeat','n':2,'spacing_hours':0,'body':[{'type':'wait','hours':1}]}
    with pytest.raises(ValidationError):TypeAdapter(Phase).validate_python({**repeat,'body':[repeat]})
    raw=example();raw['layers']['transporter_C']=False
    for arm in raw['arms']:arm['protocol'].insert(0,{'type':'dose','drug':'methylphenidate','c_food_mm':1})
    with pytest.raises(ValidationError,match='layer off'):Experiment.model_validate(raw)
    reg=registry();reg.population=lambda name:SimpleNamespace(idx=np.zeros(0,dtype=np.int32))
    with pytest.raises(ValueError,match='zero neurons'):Experiment.model_validate(example()).resolve(reg)
    raw=example();raw['arms'][0]['genotype']['manipulations']=[{'type':'scale_dat','compartments':['missing'],'factor':1}]
    with pytest.raises(ValueError,match='compartments'):Experiment.model_validate(raw).resolve(registry())


def test_spec_example_and_exact_named_genotypes() -> None:
    """Validate the literal spec example and exact dimensionless genotype factors."""
    from flyonenomics.schema.experiment import Genotype
    section=(ROOT/'docs/SPEC.md').read_text().split('### 6.3 Example:',1)[1]
    raw=json.loads(section.split('```json',1)[1].split('```',1)[0])
    Experiment.model_validate(raw)
    expected={'wild_type':[], 'fumin':[{'type':'scale_dat','compartments':'all','factor':0.0}],
              'dop1r1_null':[{'type':'scale_receptor','population':'all','receptor':'D1','factor':0.0}],
              'dopamine_depleted':[{'type':'scale_release','factor':0.5}]}
    for name,hooks in expected.items():
        assert [h.model_dump() for h in Genotype(named=name).expanded()]==hooks
    for duration in (0.01,0.03,1.01,120):
        Probe.model_validate({'type':'probe','assay':'spontaneous','label':'p','duration_s':duration,'params':{}})
