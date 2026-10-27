"""Optional, modular scientific extras. The core planner never depends on these."""

from __future__ import annotations

from typing import Any

import httpx

from .config import get_settings

PYBAMM_NOTE = (
    "PyBaMM evaluates a published cell-level electrochemical model (Chen2020 LG M50 "
    "parameter set, Single Particle Model) at a user-chosen C-rate. It does not take "
    "calcination temperature, slurry carbon loading, or other processing parameters as inputs, "
    "and it is not used to rank experiment candidates."
)


def pybamm_status() -> dict[str, Any]:
    try:
        import pybamm  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "reason": f"PyBaMM is not installed ({exc}). Core planner still works.",
            "install": "pip install -r backend/requirements-optional.txt",
            "note": PYBAMM_NOTE,
        }
    return {"available": True, "note": PYBAMM_NOTE, "parameter_set": "Chen2020", "model": "SPM"}


def run_pybamm_example(c_rate: float = 1.0, temperature_C: float = 25.0) -> dict[str, Any]:
    status = pybamm_status()
    if not status["available"]:
        return {"ok": False, **status}
    import pybamm

    model = pybamm.lithium_ion.SPM()
    params = pybamm.ParameterValues("Chen2020")
    params.update({"Ambient temperature [K]": 273.15 + temperature_C})
    experiment = pybamm.Experiment([f"Discharge at {c_rate}C until 2.5 V"])
    sim = pybamm.Simulation(model, parameter_values=params, experiment=experiment)
    solution = sim.solve()
    capacity = float(solution["Discharge capacity [A.h]"].entries[-1])
    voltage_end = float(solution["Voltage [V]"].entries[-1])
    return {
        "ok": True,
        "source": "simulated",
        "label": "PyBaMM Chen2020 SPM demonstration (not a processing-parameter prediction)",
        "parameter_set": "Chen2020",
        "parameter_set_citation": "Chen et al., J. Electrochem. Soc. 167 080534 (2020), DOI 10.1149/1945-7111/ab9050",
        "pybamm_citation": "Sulzer et al., JOSS 6(70) 3051 (2021), DOI 10.21105/joss.03051",
        "c_rate": c_rate,
        "temperature_C": temperature_C,
        "discharge_capacity_Ah": round(capacity, 5),
        "end_voltage_V": round(voltage_end, 4),
        "nominal_capacity_Ah": 5.0,
        "note": PYBAMM_NOTE,
        "docs": "https://docs.pybamm.org/en/stable/source/user_guide/fundamentals/index.html",
    }


def materials_project_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "configured": bool(settings.materials_project_api_key.strip()),
        "note": (
            "Optional computed-materials lookup. Results are DFT-derived Materials Project "
            "properties, not measured battery performance. Core workflow does not require a key."
        ),
        "docs": "https://docs.materialsproject.org/downloading-data/using-the-api/getting-started",
        "dashboard": "https://next-gen.materialsproject.org/api",
    }


def lookup_formula(formula: str) -> dict[str, Any]:
    settings = get_settings()
    status = materials_project_status()
    if not status["configured"]:
        return {
            "ok": False,
            "error": "MATERIALS_PROJECT_API_KEY is not set. Core planner still works.",
            **status,
        }
    params = {
        "formula": formula,
        "fields": "material_id,formula_pretty,band_gap,formation_energy_per_atom,energy_above_hull,is_stable,theoretical",
        "_limit": 5,
    }
    headers = {"X-API-KEY": settings.materials_project_api_key, "Accept": "application/json"}
    url = settings.materials_project_base_url.rstrip("/") + "/materials/summary/"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            return {
                "ok": False,
                "error": f"Materials Project HTTP {response.status_code}",
                **status,
            }
        payload = response.json()
        data = payload.get("data") or payload.get("results") or []
        records = []
        for item in data[:5]:
            mid = item.get("material_id")
            records.append(
                {
                    "material_id": mid,
                    "formula": item.get("formula_pretty"),
                    "band_gap_eV": item.get("band_gap"),
                    "formation_energy_eV_atom": item.get("formation_energy_per_atom"),
                    "energy_above_hull_eV_atom": item.get("energy_above_hull"),
                    "is_stable": item.get("is_stable"),
                    "theoretical": item.get("theoretical"),
                    "source_url": f"https://next-gen.materialsproject.org/materials/{mid}" if mid else None,
                }
            )
        return {
            "ok": True,
            "formula_query": formula,
            "records": records,
            "provenance": (
                "Materials Project summary endpoint. Cite Jain et al., APL Mater. 1, 011002 (2013) "
                "DOI 10.1063/1.4812323. Properties are computed, not measured cell data."
            ),
            **status,
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"Materials Project network error: {exc}", **status}
