import json
import os
from itertools import product

import numpy as np
from rdkit import Chem, RDConfig
from rdkit.Chem import AllChem, ChemicalFeatures
from rdkit.Chem import SDWriter

EXCLUSION_RADIUS = 1.2
CLASH_TOLERANCE = 0.1
SIGMA = 1.25
NUM_CONFS = 200
RANDOM_SEED = 42
MAX_FEATURES_PER_ANCHOR = 3
NUM_ANCHORS = 4

FAMILY_MAP = {
    'Donor': 'Donor',
    'Acceptor': 'Acceptor',
    'Hydrophobe': 'Hydrophobe',
    'LumpedHydrophobe': 'Hydrophobe',
    'Aromatic': 'Aromatic',
}

FAMILY_PRIORITY = {'Donor': 4, 'Acceptor': 3, 'Aromatic': 2, 'Hydrophobe': 1}


def get_feature_factory():
    fdef_path = os.path.join(RDConfig.RDDataDir, 'BaseFeatures.fdef')
    return ChemicalFeatures.BuildFeatureFactory(fdef_path)


def generate_conformers(smiles):
    mol = Chem.MolFromSmiles(smiles)
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = RANDOM_SEED
    params.numThreads = 0
    params.pruneRmsThresh = 0.5
    AllChem.EmbedMultipleConfs(mol, numConfs=NUM_CONFS, params=params)
    AllChem.MMFFOptimizeMoleculeConfs(mol, numThreads=0)
    return Chem.RemoveHs(mol)


def get_feature_positions(factory, mol, conf_id):
    positions = {f: [] for f in ['Donor', 'Acceptor', 'Hydrophobe', 'Aromatic']}
    for feat in factory.GetFeaturesForMol(mol, confId=conf_id):
        family = FAMILY_MAP.get(feat.GetFamily())
        if family:
            positions[family].append(np.array(feat.GetPos()))
    return positions


def get_atom_family_map(factory, mol, conf_id):
    n_atoms = mol.GetNumAtoms()
    atom_fam = {}

    for feat in factory.GetFeaturesForMol(mol, confId=conf_id):
        family = FAMILY_MAP.get(feat.GetFamily())
        if not family:
            continue
        for idx in feat.GetAtomIds():
            if idx >= n_atoms:
                continue
            current = atom_fam.get(idx, '')
            if FAMILY_PRIORITY.get(family, 0) > FAMILY_PRIORITY.get(current, 0):
                atom_fam[idx] = family

    for i in range(n_atoms):
        if i not in atom_fam:
            atom = mol.GetAtomWithIdx(i)
            atomic_num = atom.GetAtomicNum()
            if atom.GetIsAromatic():
                atom_fam[i] = 'Aromatic'
            elif atomic_num in (6, 16, 17, 35, 53):
                atom_fam[i] = 'Hydrophobe'
            else:
                atom_fam[i] = ''

    return atom_fam


def kabsch(P, Q):
    p_c = P.mean(axis=0)
    q_c = Q.mean(axis=0)
    H = (Q - q_c).T @ (P - p_c)
    U, _, Vt = np.linalg.svd(H)
    d = np.linalg.det(Vt.T @ U.T)
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    t = p_c - R @ q_c
    return R, t


def apply_transform(positions, R, t):
    return (R @ positions.T).T + t


def has_clash(positions, excluded_volumes):
    threshold = EXCLUSION_RADIUS - CLASH_TOLERANCE
    for ev in excluded_volumes:
        center = np.array([ev['x'], ev['y'], ev['z']])
        if np.any(np.linalg.norm(positions - center, axis=1) < threshold):
            return True
    return False


def score_pose(positions, atom_fam, sites):
    score = 0.0
    for site in sites:
        family = site['family']
        site_pos = np.array([site['x'], site['y'], site['z']])
        matching = [positions[i] for i in range(len(positions)) if atom_fam.get(i) == family]
        if not matching:
            continue
        d = np.linalg.norm(np.array(matching) - site_pos, axis=1).min()
        score += site['weight'] * np.exp(-(d / SIGMA) ** 2)
    return score


def build_final_mol(mol, conf_id, R, t):
    positions = mol.GetConformer(conf_id).GetPositions()
    new_positions = apply_transform(positions, R, t)

    new_mol = Chem.RWMol(mol)
    for cid in [c.GetId() for c in new_mol.GetConformers()]:
        new_mol.RemoveConformer(cid)

    conf = Chem.Conformer(new_mol.GetNumAtoms())
    for i, pos in enumerate(new_positions):
        conf.SetAtomPosition(i, pos.tolist())
    new_mol.AddConformer(conf, assignId=True)

    return new_mol.GetMol()


def select_anchors(sites):
    return sorted(sites, key=lambda s: -s['weight'])[:NUM_ANCHORS]


def try_alignment(site_points, ligand_options, positions, atom_fam, excluded_volumes, sites):
    best_score = -1.0
    best_R, best_t = np.eye(3), np.zeros(3)

    capped = [opts[:MAX_FEATURES_PER_ANCHOR] for opts in ligand_options]

    for combo in product(*capped):
        P = np.array(site_points)
        Q = np.array(combo)
        try:
            R, t = kabsch(P, Q)
        except np.linalg.LinAlgError:
            continue

        transformed = apply_transform(positions, R, t)
        if has_clash(transformed, excluded_volumes):
            continue

        s = score_pose(transformed, atom_fam, sites)
        if s > best_score:
            best_score = s
            best_R, best_t = R, t

    return best_score, best_R, best_t


def centroid_fallback(positions, sites, excluded_volumes, atom_fam):
    site_centroid = np.mean([[s['x'], s['y'], s['z']] for s in sites], axis=0)
    mol_centroid = positions.mean(axis=0)
    t = site_centroid - mol_centroid
    transformed = positions + t
    if has_clash(transformed, excluded_volumes):
        return -1.0, np.eye(3), np.zeros(3)
    s = score_pose(transformed, atom_fam, sites)
    return s, np.eye(3), t


def process_target(target_data, factory):
    smiles = target_data['smiles']
    sites = target_data['interaction_sites']
    excluded = target_data['excluded_volumes']

    mol = generate_conformers(smiles)
    n_confs = mol.GetNumConformers()
    anchors = select_anchors(sites)

    best_score = -1.0
    best_conf_id = 0
    best_R = np.eye(3)
    best_t = np.zeros(3)

    for conf_id in range(n_confs):
        positions = mol.GetConformer(conf_id).GetPositions()
        feat_pos = get_feature_positions(factory, mol, conf_id)
        atom_fam = get_atom_family_map(factory, mol, conf_id)

        site_points = []
        ligand_options = []

        for anchor in anchors:
            family = anchor['family']
            opts = feat_pos.get(family, [])
            if opts:
                site_points.append([anchor['x'], anchor['y'], anchor['z']])
                ligand_options.append(opts)

        if len(site_points) >= 3:
            s, R, t = try_alignment(
                site_points, ligand_options, positions, atom_fam, excluded, sites
            )
        else:
            s, R, t = centroid_fallback(positions, sites, excluded, atom_fam)

        if s > best_score:
            best_score = s
            best_conf_id = conf_id
            best_R, best_t = R, t

    return build_final_mol(mol, best_conf_id, best_R, best_t), best_score


def main():
    data_path = '/root/data/targets.json'
    output_path = '/root/results/docked_poses.sdf'

    if not os.path.exists(data_path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(base, 'targets.json')
        output_path = os.path.join(base, 'pharmacophore_alignment', 'docked_poses.sdf')

    with open(data_path) as f:
        targets = json.load(f)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    factory = get_feature_factory()
    writer = SDWriter(output_path)

    for target_name, target_data in targets.items():
        print(f"Processing {target_name} ({target_data['smiles']})")
        mol, score = process_target(target_data, factory)
        mol.SetProp('_Name', target_name)
        mol.SetProp('Score', f'{score:.4f}')
        writer.write(mol)
        print(f"  Score: {score:.4f}")

    writer.close()
    print(f"\nDone. Results written to {output_path}")


if __name__ == '__main__':
    main()
