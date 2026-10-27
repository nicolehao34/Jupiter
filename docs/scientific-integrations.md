# Scientific integrations (MVP decisions)

This note records what was read, what is in scope for Jupiter, and why. Optional extras are modular: the Gaussian-process planner runs if PyBaMM or Materials Project are missing.

**Intended product.** Help a battery researcher improve an *existing* material by proposing the next processing-parameter experiments. The first version is scientifically transparent and narrow: a few continuous numeric inputs, one target metric, human-in-the-loop results.

No claim is made that the app reduces real lab experiments. That is the intended benefit; this MVP demonstrates the closed loop on a labeled synthetic table.

---

## Comparison

| Integration | Intended role | Required data | Implementation effort | Limitations | Recommendation for this MVP |
| --- | --- | --- | --- | --- | --- |
| **Gaussian process + expected improvement** (scikit-learn) | Core ranking engine: fit a surrogate on measured (or demo) rows, propose a diverse batch | Numeric table: ≤6 continuous inputs, 1 target, user-supplied units and bounds | Low–medium; already implemented | Poor with tiny *n*, categorical variables, or constraints the user did not encode. Uncertainty is a **posterior standard deviation**, not experimental confidence. | **Use as the only source of numerical predictions.** |
| **NVIDIA Nemotron via Nebius Token Factory** | Turn a goal sentence into a *reviewable* config; summarize validator output; explain explore/exploit using supplied numbers; summarize batch-to-batch change; write a grounded PI brief from stored facts (best, budget, EI lift, run sheet) | The researcher’s text plus deterministic payloads (issues, EI, μ, σ, campaign facts) | Medium (client, schema checks, timeouts, offline flag) | Can hallucinate if ungrounded; credits and network required for live mode | **Use for language only.** Never let the LLM invent predictions. |
| **PyBaMM** | Optional cell-level illustration: discharge a published cell model | A complete parameter set (here Chen2020 LG M50), C-rate, temperature — **not** calcination temperature or slurry recipe | Medium if kept as a canned example; high if mapping processing → cell parameters | SPM/DFN do not take arbitrary composition or synthesis variables. Chen2020 is one commercial cell, not NMC811 powder processing. | **Include one optional SPM example; do not score candidates with it.** |
| **Materials Project** | Optional lookup of computed crystal properties for the *fixed* cathode formula | API key; formula or `mp-id` | Low for a summary-endpoint lookup | DFT formation energies / band gaps are **not** measured discharge capacity. Provenance and license obligations apply. | **Optional, off by default.** Core demo must work without a key. |
| **Self-driving-lab / robotics stack** | Out of scope | Hardware, schedulers, ontology | High | Hackathon track is Best Apps, not Physical AI | **Do not integrate.** Human records results. |

---

## 1. PyBaMM

**Docs read.** [PyBaMM fundamentals](https://docs.pybamm.org/en/stable/source/user_guide/fundamentals/index.html); [lithium-ion models](https://docs.pybamm.org/en/stable/source/api/models/lithium_ion/index.html) (SPM, SPMe, DFN); [parameter sets](https://docs.pybamm.org/en/latest/source/api/parameters/parameter_sets.html); [Chen2020 parameter tutorial](https://docs.pybamm.org/en/latest/source/examples/notebooks/getting_started/tutorial-4-setting-parameter-values.html); [SPM notebook](https://docs.pybamm.org/en/latest/source/examples/notebooks/models/SPM.html).

**What it actually is.** PyBaMM solves continuum electrochemical models for a *cell* given a full parameter set (thicknesses, diffusivities, OCP functions, etc.). The Chen2020 set describes an LG M50 cell (graphite / NMC 811 electrodes) from Chen et al., *J. Electrochem. Soc.* **167** 080534 (2020), [DOI 10.1149/1945-7111/ab9050](https://doi.org/10.1149/1945-7111/ab9050). PyBaMM itself: Sulzer et al., *JOSS* **6**(70) 3051 (2021), [DOI 10.21105/joss.03051](https://doi.org/10.21105/joss.03051).

**Feasible in this MVP?** Yes, as a **canned SPM discharge** at a user-chosen C-rate and ambient temperature. Not feasible as a scorer for processing-parameter candidates: there is no supported map from calcination temperature, hold time, ramp rate, or carbon-black loading onto Chen2020 parameters.

**Implementation.** `POST /api/simulate/pybamm` (optional extra `backend/requirements-optional.txt`). UI labels output as **simulated**, distinct from **surrogate predictions** and **measured / synthetic-demo** rows. If PyBaMM is not installed, the planner still runs.

---

## 2. Materials Project

**Docs read.** [Getting started with the API](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started); [querying data](https://docs.materialsproject.org/downloading-data/using-the-api/querying-data); [Materials API overview](https://doc.docs.materialsproject.org/open-apis/the-materials-api/).

**Access.** HTTPS only. API key from the [dashboard](https://next-gen.materialsproject.org/api), sent as `X-API-KEY`. Do not share keys. Data should be cited: Jain et al., *APL Mater.* **1**, 011002 (2013), [DOI 10.1063/1.4812323](https://doi.org/10.1063/1.4812323). Follow current MP terms for redistribution.

**What a lookup returns.** Summary fields such as `material_id`, formula, band gap, formation energy per atom, energy above hull, theoretical flag, plus a source URL `https://next-gen.materialsproject.org/materials/{mp-id}`.

**Use here.** Optional formula lookup for the demo’s fixed composition `LiNi0.8Mn0.1Co0.1O2`, shown as **computed materials properties**. Explicitly not a battery-performance measurement. Core workflow does not call MP.

---

## 3. Papers on automated experimentation / BO / batteries

References below were checked from publisher or PMC pages. Preprints are labeled.

| Work | Date / venue | Status | Methods | Code / data | Limitations | What we reuse |
| --- | --- | --- | --- | --- | --- | --- |
| Lookman, Balachandran, Xue, Yuan. [Active learning in materials science…](https://www.nature.com/articles/s41524-019-0153-8) *npj Comput. Mater.* **5**, 21. [DOI 10.1038/s41524-019-0153-8](https://doi.org/10.1038/s41524-019-0153-8) | 18 Feb 2019 | Peer-reviewed review | Surrogate + utility (EI and relatives); uncertainties drive adaptive sampling | Review | Multi-objective / multi-fidelity still hard | EI + “uncertainty is for targeting, not a proof of accuracy” |
| Xue, Balachandran, et al. (Lookman group). [Accelerated search for materials with targeted properties by adaptive design](https://www.nature.com/articles/ncomms11241) *Nat. Commun.* **7**, 11241. [DOI 10.1038/ncomms11241](https://doi.org/10.1038/ncomms11241) | 2016 | Peer-reviewed | Regressor + expected improvement to pick the next experiment | Paper | Piezoelectric alloy case, not batteries | EI formula used in the ranking engine |
| Kusne, Yu, Takeuchi, et al. [On-the-fly closed-loop materials discovery via Bayesian active learning](https://www.nature.com/articles/s41524-020-0310-2) (CAMEO) *npj Comput. Mater.* **6**, 120. [DOI 10.1038/s41524-020-0310-2](https://doi.org/10.1038/s41524-020-0310-2) | 16 Nov 2020 | Peer-reviewed | Closed-loop BO at a beamline; human-in-the-loop option | [GitHub / Zenodo](https://github.com/KusneNIST/CAMEO_NComm) | Hardware-specific; phase mapping + property | Keep a **human** in the loop; fail smarter, don’t hide errors |
| Yao et al. [Accelerating aqueous electrolyte design with automated full-cell battery experimentation and Bayesian optimization](https://www.cell.com/cell-reports-physical-science/fulltext/S2666-3864(25)00147-X) *Cell Rep. Phys. Sci.* (2025) 102548. [DOI 10.1016/j.xcrp.2025.102548](https://doi.org/10.1016/j.xcrp.2025.102548) | 16 Apr 2025 | Peer-reviewed | Automated coin cells + cycling + BO on a hybrid electrolyte | Paper | Electrolyte mixtures, not cathode calcination; robotics | Closed loop: propose → run → append → propose |
| Vogler et al. [Autonomous battery optimization by deploying distributed experiments and simulations](https://doi.org/10.1002/aenm.202403263) *Adv. Energy Mater.* (FINALES / MAP). [DOI 10.1002/aenm.202403263](https://doi.org/10.1002/aenm.202403263) | 2024 | Peer-reviewed | Distributed MAP; BO tenants; **simulations and lab** kept as separate modalities | Framework paper | Institutional ontology; async tenants | Keep **sim** (PyBaMM) and **lab/demo table** as separate data kinds |
| Dave / polymer-electrolyte team. [Autonomous discovery of polymer electrolyte formulations with warm-start batch Bayesian optimization](https://doi.org/10.1021/acs.chemmater.5c01209) *Chem. Mater.* [DOI 10.1021/acs.chemmater.5c01209](https://doi.org/10.1021/acs.chemmater.5c01209) | 25 Sep 2025 | Peer-reviewed | Warm-start from literature; **batch** BO; high-exploration batch sampling | Autonomous polymer platform | Different chemistry (PCL + Li salts) | Diverse **batches**, not one-at-a-time EI greedily without spacing |

Reusable techniques encoded in code: (1) expected improvement on a GP; (2) **batch diversity** so parallel lab slots are not clones; (3) explicit handling of **small n** via Latin-hypercube initial design; (4) exclusion of completed and already-proposed points; (5) labels that separate measured, predicted, simulated, and synthetic-demo values; (6) failed/invalid experiments surface as validator errors rather than silent NaNs; (7) a **same-pool space-filling baseline** scored with the same EI surface so the proposed batch can be compared without claiming lab savings.

---

## Decision summary

1. Rank with a sklearn Matern GP + EI; LLM does not invent μ, σ, or EI.
2. Ship a seeded synthetic NMC811 *processing* table so the demo does not require a lab file.
3. Ship PyBaMM as an optional Chen2020 SPM example, never as the objective for processing parameters.
4. Ship Materials Project as an optional formula lookup with source links.
5. Persist dataset version, config snapshot, and each recommendation batch in SQLite.
