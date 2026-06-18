import json
import os
import tempfile

import numpy as np
import pytest
from rdkit import Chem

from pharmacophore_alignment.solution import (
    apply_transform,
    generate_conformers,
    get_feature_factory,
    get_feature_positions,
    get_atom_family_map,
    has_clash,
    kabsch,
    process_target,
    score_pose,
    main,
)

IBUPROFEN_SMILES = "CC(C)Cc1ccc(cc1)C(C)C(O)=O"
CAFFEINE_SMILES = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
ASPIRIN_SMILES = "CC(=O)Oc1ccccc1C(O)=O"

TARGETS_JSON = {
    "target_1": {
        "smiles": IBUPROFEN_SMILES,
        "interaction_sites": [
            {"family": "Acceptor", "x": 2.45, "y": -1.32, "z": 0.87, "weight": 1.2},
            {"family": "Aromatic", "x": -2.34, "y": 1.12, "z": -0.67, "weight": 1.5},
            {"family": "Hydrophobe", "x": -1.23, "y": 0.56, "z": -0.34, "weight": 0.8},
        ],
        "excluded_volumes": [
            {"x": 100.0, "y": 100.0, "z": 100.0, "radius": 1.2},
        ],
    }
}


@pytest.fixture(scope="module")
def factory():
    return get_feature_factory()


@pytest.fixture(scope="module")
def ibuprofen_mol():
    return generate_conformers(IBUPROFEN_SMILES)


@pytest.fixture(scope="module")
def caffeine_mol():
    return generate_conformers(CAFFEINE_SMILES)


def test_generate_conformers_returns_multiple_conformers(ibuprofen_mol):
    assert ibuprofen_mol.GetNumConformers() > 0


def test_generate_conformers_removes_hydrogens(ibuprofen_mol):
    for atom in ibuprofen_mol.GetAtoms():
        assert atom.GetAtomicNum() != 1


def test_generate_conformers_caffeine(caffeine_mol):
    assert caffeine_mol.GetNumConformers() > 0
    assert caffeine_mol.GetNumAtoms() > 0


def test_generate_conformers_preserves_atom_count(ibuprofen_mol):
    ref = Chem.MolFromSmiles(IBUPROFEN_SMILES)
    assert ibuprofen_mol.GetNumAtoms() == ref.GetNumAtoms()


def test_get_feature_factory_returns_factory(factory):
    assert factory is not None


def test_get_feature_positions_has_expected_families(factory, ibuprofen_mol):
    feat_pos = get_feature_positions(factory, ibuprofen_mol, 0)
    assert set(feat_pos.keys()) == {"Donor", "Acceptor", "Hydrophobe", "Aromatic"}


def test_get_feature_positions_ibuprofen_has_acceptors(factory, ibuprofen_mol):
    feat_pos = get_feature_positions(factory, ibuprofen_mol, 0)
    assert len(feat_pos["Acceptor"]) > 0


def test_get_feature_positions_ibuprofen_has_aromatic(factory, ibuprofen_mol):
    feat_pos = get_feature_positions(factory, ibuprofen_mol, 0)
    assert len(feat_pos["Aromatic"]) > 0


def test_get_feature_positions_caffeine_has_acceptors(factory, caffeine_mol):
    feat_pos = get_feature_positions(factory, caffeine_mol, 0)
    assert len(feat_pos["Acceptor"]) > 0


def test_get_atom_family_map_covers_all_atoms(factory, ibuprofen_mol):
    atom_fam = get_atom_family_map(factory, ibuprofen_mol, 0)
    for i in range(ibuprofen_mol.GetNumAtoms()):
        assert i in atom_fam


def test_get_atom_family_map_valid_families(factory, ibuprofen_mol):
    valid = {"Donor", "Acceptor", "Hydrophobe", "Aromatic", ""}
    atom_fam = get_atom_family_map(factory, ibuprofen_mol, 0)
    for fam in atom_fam.values():
        assert fam in valid


def test_kabsch_identity_when_p_equals_q():
    P = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    R, t = kabsch(P, P)
    assert np.allclose(R, np.eye(3), atol=1e-5)
    assert np.allclose(t, np.zeros(3), atol=1e-5)


def test_kabsch_pure_translation():
    P = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    offset = np.array([3.0, -2.0, 1.5])
    Q = P - offset
    R, t = kabsch(P, Q)
    recovered = apply_transform(Q, R, t)
    assert np.allclose(recovered, P, atol=1e-5)


def test_kabsch_rotation_90_degrees():
    P = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    angle = np.pi / 2
    Rz = np.array([
        [np.cos(angle), -np.sin(angle), 0],
        [np.sin(angle), np.cos(angle), 0],
        [0, 0, 1],
    ])
    Q = (Rz @ P.T).T
    R, t = kabsch(P, Q)
    recovered = apply_transform(Q, R, t)
    assert np.allclose(recovered, P, atol=1e-5)


def test_apply_transform_identity():
    positions = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    R = np.eye(3)
    t = np.zeros(3)
    result = apply_transform(positions, R, t)
    assert np.allclose(result, positions)


def test_apply_transform_translation():
    positions = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    R = np.eye(3)
    t = np.array([5.0, 0.0, 0.0])
    result = apply_transform(positions, R, t)
    assert np.allclose(result, [[5.0, 0.0, 0.0], [6.0, 0.0, 0.0]])


def test_has_clash_detects_overlap():
    positions = np.array([[0.0, 0.0, 0.0]])
    excluded = [{"x": 0.0, "y": 0.0, "z": 0.5, "radius": 1.2}]
    assert has_clash(positions, excluded)


def test_has_clash_no_clash_when_far():
    positions = np.array([[0.0, 0.0, 0.0]])
    excluded = [{"x": 5.0, "y": 5.0, "z": 5.0, "radius": 1.2}]
    assert not has_clash(positions, excluded)


def test_has_clash_boundary_within_tolerance():
    positions = np.array([[0.0, 0.0, 0.0]])
    excluded = [{"x": 1.05, "y": 0.0, "z": 0.0, "radius": 1.2}]
    assert has_clash(positions, excluded)


def test_has_clash_boundary_just_outside():
    positions = np.array([[0.0, 0.0, 0.0]])
    excluded = [{"x": 1.15, "y": 0.0, "z": 0.0, "radius": 1.2}]
    assert not has_clash(positions, excluded)


def test_has_clash_empty_excluded_volumes():
    positions = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
    assert not has_clash(positions, [])


def test_score_pose_perfect_overlap():
    positions = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    atom_fam = {0: "Acceptor", 1: "Donor"}
    sites = [{"family": "Acceptor", "x": 1.0, "y": 0.0, "z": 0.0, "weight": 1.0}]
    score = score_pose(positions, atom_fam, sites)
    assert abs(score - 1.0) < 1e-5


def test_score_pose_increases_when_closer():
    positions_far = np.array([[5.0, 0.0, 0.0]])
    positions_close = np.array([[0.1, 0.0, 0.0]])
    atom_fam = {0: "Donor"}
    sites = [{"family": "Donor", "x": 0.0, "y": 0.0, "z": 0.0, "weight": 1.0}]
    s_far = score_pose(positions_far, atom_fam, sites)
    s_close = score_pose(positions_close, atom_fam, sites)
    assert s_close > s_far


def test_score_pose_no_matching_family_contributes_zero():
    positions = np.array([[0.0, 0.0, 0.0]])
    atom_fam = {0: "Hydrophobe"}
    sites = [{"family": "Donor", "x": 0.0, "y": 0.0, "z": 0.0, "weight": 2.0}]
    assert score_pose(positions, atom_fam, sites) == 0.0


def test_process_target_returns_mol_and_positive_score(factory):
    target_data = TARGETS_JSON["target_1"]
    mol, score = process_target(target_data, factory)
    assert mol is not None
    assert score >= 0.0


def test_process_target_mol_has_single_conformer(factory):
    target_data = TARGETS_JSON["target_1"]
    mol, _ = process_target(target_data, factory)
    assert mol.GetNumConformers() == 1


def test_process_target_mol_preserves_atom_count(factory):
    target_data = TARGETS_JSON["target_1"]
    mol, _ = process_target(target_data, factory)
    ref = Chem.MolFromSmiles(IBUPROFEN_SMILES)
    assert mol.GetNumAtoms() == ref.GetNumAtoms()


def test_process_target_no_clash_in_best_pose(factory):
    target_data = TARGETS_JSON["target_1"]
    mol, _ = process_target(target_data, factory)
    positions = mol.GetConformer(0).GetPositions()
    assert not has_clash(positions, target_data["excluded_volumes"])


def test_main_writes_sdf_file(factory):
    data_path = os.path.join(os.path.dirname(__file__), "..", "..", "targets.json")
    data_path = os.path.abspath(data_path)
    if not os.path.exists(data_path):
        pytest.skip("targets.json not found")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "docked_poses.sdf")
        with open(data_path) as f:
            targets = json.load(f)

        writer = Chem.SDWriter(output_path)
        for target_name, target_data in targets.items():
            mol, score = process_target(target_data, factory)
            mol.SetProp("_Name", target_name)
            mol.SetProp("Score", f"{score:.4f}")
            writer.write(mol)
        writer.close()

        assert os.path.exists(output_path)
        suppl = Chem.SDMolSupplier(output_path, removeHs=False)
        mols = [m for m in suppl if m is not None]
        assert len(mols) == len(targets)


def test_main_all_five_targets_have_positive_scores(factory):
    data_path = os.path.join(os.path.dirname(__file__), "..", "..", "targets.json")
    data_path = os.path.abspath(data_path)
    if not os.path.exists(data_path):
        pytest.skip("targets.json not found")

    with open(data_path) as f:
        targets = json.load(f)

    for target_name, target_data in targets.items():
        mol, score = process_target(target_data, factory)
        assert score > 0.0, f"{target_name} got score {score}"


def test_all_poses_have_no_steric_clashes(factory):
    data_path = os.path.join(os.path.dirname(__file__), "..", "..", "targets.json")
    data_path = os.path.abspath(data_path)
    if not os.path.exists(data_path):
        pytest.skip("targets.json not found")

    with open(data_path) as f:
        targets = json.load(f)

    for target_name, target_data in targets.items():
        mol, _ = process_target(target_data, factory)
        positions = mol.GetConformer(0).GetPositions()
        clashes = has_clash(positions, target_data["excluded_volumes"])
        assert not clashes, f"{target_name} best pose has steric clashes"
