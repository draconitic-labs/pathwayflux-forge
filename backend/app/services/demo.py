"""Built-in demo pathway: simplified glycolysis segment (glucose → pyruvate)."""

from __future__ import annotations

from app.models.schema import (
    Assumption,
    Cofactor,
    Compartment,
    Enzyme,
    Inhibitor,
    Metabolite,
    PathwayProject,
    ProjectMeta,
    RateLawType,
    RateParameters,
    Reaction,
    Scenario,
    ScenarioOverride,
    SimulationSettings,
    SpeciesStoich,
)


def build_glycolysis_demo() -> PathwayProject:
    """
    Educational toy model (not full stoichiometric glycolysis):

      Glucose --HK--> G6P --PFK--> FBP --ALD--> GAP --PK--> Pyruvate

    With ATP/ADP cofactors, citrate competitive inhibition on PFK,
    and scenarios: baseline / HK mutant / PFK inhibited.
    """
    cyto = Compartment(
        id="cyto",
        name="Cytosol",
        volume=1.0,
        color="#0f172a",
        x=40,
        y=40,
        width=900,
        height=520,
    )

    # Metabolites
    glc = Metabolite(
        id="glc",
        name="Glucose",
        compartment_id="cyto",
        initial_concentration=5.0,
        is_boundary=False,
        formula="C6H12O6",
        x=120,
        y=180,
    )
    g6p = Metabolite(
        id="g6p",
        name="G6P",
        compartment_id="cyto",
        initial_concentration=0.2,
        formula="C6H13O9P",
        x=300,
        y=180,
    )
    fbp = Metabolite(
        id="fbp",
        name="FBP",
        compartment_id="cyto",
        initial_concentration=0.05,
        formula="C6H14O12P2",
        x=480,
        y=180,
    )
    gap = Metabolite(
        id="gap",
        name="GAP",
        compartment_id="cyto",
        initial_concentration=0.02,
        formula="C3H7O6P",
        x=660,
        y=180,
    )
    pyr = Metabolite(
        id="pyr",
        name="Pyruvate",
        compartment_id="cyto",
        initial_concentration=0.1,
        formula="C3H4O3",
        x=840,
        y=180,
    )
    atp = Metabolite(
        id="atp",
        name="ATP",
        compartment_id="cyto",
        initial_concentration=2.5,
        is_boundary=True,  # buffered cofactor pool
        formula="C10H16N5O13P3",
        x=300,
        y=360,
    )
    adp = Metabolite(
        id="adp",
        name="ADP",
        compartment_id="cyto",
        initial_concentration=0.5,
        is_boundary=True,
        formula="C10H15N5O10P2",
        x=480,
        y=360,
    )
    cit = Metabolite(
        id="cit",
        name="Citrate",
        compartment_id="cyto",
        initial_concentration=0.0,
        is_boundary=True,
        formula="C6H8O7",
        x=480,
        y=460,
        notes="Allosteric / competitive inhibitor signal for PFK",
    )

    hk = Enzyme(id="enz_hk", name="Hexokinase", concentration=1.0, kcat=1.0)
    pfk = Enzyme(id="enz_pfk", name="PFK-1", concentration=1.0, kcat=1.0)
    ald = Enzyme(id="enz_ald", name="Aldolase", concentration=1.0, kcat=1.0)
    pk = Enzyme(id="enz_pk", name="Pyruvate kinase", concentration=1.0, kcat=1.0)

    cof_atp_hk = Cofactor(
        id="cof_atp_hk",
        name="ATP (HK cosubstrate)",
        metabolite_id="atp",
        role="cosubstrate",
    )
    cof_adp_pk = Cofactor(
        id="cof_adp_pk",
        name="ADP (PK cosubstrate)",
        metabolite_id="adp",
        role="cosubstrate",
    )

    inh_cit = Inhibitor(
        id="inh_cit",
        name="Citrate (PFK inhibitor)",
        metabolite_id="cit",
        concentration=0.0,
        ki=0.5,
        inhibition_type="competitive",
        target_reaction_ids=["rxn_pfk"],
        notes="Elevated citrate models feedback inhibition of PFK.",
    )

    rxn_hk = Reaction(
        id="rxn_hk",
        name="Hexokinase",
        substrates=[
            SpeciesStoich(metabolite_id="glc", stoichiometry=1),
            SpeciesStoich(metabolite_id="atp", stoichiometry=1),
        ],
        products=[
            SpeciesStoich(metabolite_id="g6p", stoichiometry=1),
            SpeciesStoich(metabolite_id="adp", stoichiometry=1),
        ],
        rate_law=RateLawType.MICHAELIS_MENTEN,
        parameters=RateParameters(Vmax=2.0, Km=0.5, enzyme_id="enz_hk"),
        reversible=False,
        enzyme_id="enz_hk",
        notes="Glucose + ATP → G6P + ADP (ATP is boundary).",
    )
    rxn_pfk = Reaction(
        id="rxn_pfk",
        name="PFK",
        substrates=[
            SpeciesStoich(metabolite_id="g6p", stoichiometry=1),
            SpeciesStoich(metabolite_id="atp", stoichiometry=1),
        ],
        products=[
            SpeciesStoich(metabolite_id="fbp", stoichiometry=1),
            SpeciesStoich(metabolite_id="adp", stoichiometry=1),
        ],
        rate_law=RateLawType.COMPETITIVE_INHIBITION,
        parameters=RateParameters(
            Vmax=1.5, Km=0.3, Ki=0.5, enzyme_id="enz_pfk", inhibitor_id="inh_cit"
        ),
        reversible=False,
        enzyme_id="enz_pfk",
        notes="Committed step; competitively inhibited by citrate.",
    )
    rxn_ald = Reaction(
        id="rxn_ald",
        name="Aldolase",
        substrates=[SpeciesStoich(metabolite_id="fbp", stoichiometry=1)],
        products=[SpeciesStoich(metabolite_id="gap", stoichiometry=2)],
        rate_law=RateLawType.MICHAELIS_MENTEN,
        parameters=RateParameters(Vmax=1.2, Km=0.2, enzyme_id="enz_ald"),
        reversible=False,
        enzyme_id="enz_ald",
    )
    rxn_pk = Reaction(
        id="rxn_pk",
        name="Pyruvate kinase",
        substrates=[
            SpeciesStoich(metabolite_id="gap", stoichiometry=1),
            SpeciesStoich(metabolite_id="adp", stoichiometry=1),
        ],
        products=[
            SpeciesStoich(metabolite_id="pyr", stoichiometry=1),
            SpeciesStoich(metabolite_id="atp", stoichiometry=1),
        ],
        rate_law=RateLawType.HILL,
        parameters=RateParameters(
            Vmax=2.5, K_half=0.15, n_hill=2.5, enzyme_id="enz_pk"
        ),
        reversible=False,
        enzyme_id="enz_pk",
        notes="Cooperative (Hill) sink toward pyruvate.",
    )

    baseline = Scenario(
        id="sc_baseline",
        name="Baseline",
        kind="baseline",
        description="Wild-type enzyme levels, no citrate inhibition.",
        overrides=[],
        color="#38bdf8",
    )
    mutant = Scenario(
        id="sc_mutant",
        name="HK mutant (↓kcat)",
        kind="mutant",
        description="Hexokinase catalytic efficiency reduced 5×.",
        overrides=[
            ScenarioOverride(
                target_type="enzyme_kcat",
                target_id="enz_hk",
                value=0.2,
            )
        ],
        color="#f472b6",
    )
    inhibited = Scenario(
        id="sc_inhibited",
        name="PFK inhibited",
        kind="inhibited",
        description="Citrate raised to 2 mM to inhibit PFK.",
        overrides=[
            ScenarioOverride(
                target_type="metabolite_initial",
                target_id="cit",
                value=2.0,
            ),
            ScenarioOverride(
                target_type="inhibitor_concentration",
                target_id="inh_cit",
                value=2.0,
            ),
        ],
        color="#fbbf24",
    )

    assumptions = [
        Assumption(
            id="a1",
            text="ATP and ADP are treated as buffered boundary metabolites (fixed pools).",
            category="boundary",
        ),
        Assumption(
            id="a2",
            text="This is a didactic reduced chain, not a genome-scale or full EMP pathway.",
            category="approximation",
        ),
        Assumption(
            id="a3",
            text="Concentrations in mM; time in arbitrary seconds suitable for classroom demos.",
            category="units",
        ),
        Assumption(
            id="a4",
            text="PFK inhibition modeled as competitive Michaelis–Menten vs citrate.",
            category="kinetics",
        ),
        Assumption(
            id="a5",
            text="Well-mixed single cytosolic compartment; no transport delays.",
            category="compartment",
        ),
    ]

    return PathwayProject(
        schema_version="1.0",
        meta=ProjectMeta(
            name="Demo: Glycolysis Segment",
            description=(
                "Educational ODE model of a shortened glycolytic chain "
                "(Glucose → G6P → FBP → GAP → Pyruvate) with ATP/ADP cofactors, "
                "citrate inhibition of PFK, and baseline / mutant / inhibited scenarios."
            ),
            author="PathwayFlux Forge",
            units_time="s",
            units_concentration="mM",
            tags=["demo", "glycolysis", "education"],
        ),
        compartments=[cyto],
        metabolites=[glc, g6p, fbp, gap, pyr, atp, adp, cit],
        enzymes=[hk, pfk, ald, pk],
        cofactors=[cof_atp_hk, cof_adp_pk],
        inhibitors=[inh_cit],
        reactions=[rxn_hk, rxn_pfk, rxn_ald, rxn_pk],
        scenarios=[baseline, mutant, inhibited],
        assumptions=assumptions,
        simulation=SimulationSettings(
            t_start=0.0,
            t_end=50.0,
            n_points=250,
            method="LSODA",
        ),
    )
