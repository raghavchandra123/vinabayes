#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import seaborn as sns
import rdkit
import torch
import vina
import meeko
import pexpect
import pickle
import numpy as np
from scipy.stats import norm
from typing import Optional, Union, List
from bayes_opt import BayesianOptimization
from bayes_opt.util import load_logs
from bayes_opt.domain_reduction import DomainTransformer
from bayes_opt.logger import JSONLogger
from bayes_opt.event import Events
from bayes_opt.target_space import TargetSpace
import sys
from contextlib import redirect_stdout
latent_size=56


# In[ ]:


class vaeinterface:
    def __init__(self):
        pass
    def start(self):
        cmd = "conda run -n jtvae --no-capture-output python sample.py --nsample 3 --vocab data/zinc/vocab.txt --hidden 450 --depth 3 --latent 56 --model molvae/MPNVAE-h450-L56-d3-beta0.005/model.iter-4"  # launch python2 script
        self.p=pexpect.spawn(cmd,timeout=1200,logfile=open('vae_log.txt','wb'))
    def decode(self,all_vec):
        p=self.p
        tree_vec = all_vec[:,0:latent_size//2].astype("f")
        mol_vec = all_vec[:,latent_size//2:].astype("f")
        pickle.dump([tree_vec,mol_vec],open("molvec.pk1","wb"),protocol=2)
        p.sendline("'go'")
        p.expect("~.*~")
        mol=p.after.decode()[1:-1]
        return mol
    def debug(self):
        p = self.p
        p.sendline("'go'")
        p.expect("~.*~")
        mol=p.after.decode()[1:-1]
        print(mol)
        protmol = self.dim.protonate(mol)
        print(protmol[0])
    def encode(self,mol):
        p=self.p
        p.sendline("'enc"+mol+"'")
        p.expect("done")
        all_vec = pickle.load(open("encoded.pk1","rb"),encoding="latin1")
        return all_vec
    def reconstruct(self,mol):
        p=self.p
        all_vec = self.encode(mol)
        return self.decode(all_vec)
        
    def stop(self):
        p=self.p
        p.sendline("'stop'")



class vinainterface:
    def __init__(self,receptor,center,box_size,flex=None):
        v = vina.Vina(sf_name='vinardo', verbosity=0)
        v.set_receptor(receptor,flex_pdbqt_filename=flex)
        v.compute_vina_maps(center=center, box_size=box_size)
        self.v=v
        self.remember_seen = True
        self.predicted = {}
        self.receptor = receptor
        self.center = center
        self.seen = 0
        print("Vina Initialisation complete")
    def predict(self,molecule,exhaustiveness):
        if molecule=="failed":
            return -5.0,-1
        if self.remember_seen:
            if (molecule,exhaustiveness) in self.predicted:
                self.seen+=1
                if (molecule,exhaustiveness*2) in self.predicted:
                    return self.predicted[(molecule,exhaustiveness*2)],1
                return self.predicted[(molecule,exhaustiveness)],1
        lig = rdkit.Chem.MolFromSmiles(molecule)
        protonated_lig = rdkit.Chem.AddHs(lig)
        success = rdkit.Chem.AllChem.EmbedMolecule(protonated_lig)
        if success==-1:
            success=rdkit.Chem.AllChem.EmbedMolecule(protonated_lig, useRandomCoords = True)
        if success==-1:
            print("failed conformer gen")
            return -5.0,-1
        v=self.v
        meeko_prep = meeko.MoleculePreparation()
        meeko_prep.prepare(protonated_lig)
        lig_pdbqt = meeko_prep.write_pdbqt_string()
        v.set_ligand_from_string(lig_pdbqt)
        v.dock(exhaustiveness=exhaustiveness, n_poses=20)
        en=v.energies()[0][0]
        self.predicted[(molecule,exhaustiveness)]=en
        return en,1


