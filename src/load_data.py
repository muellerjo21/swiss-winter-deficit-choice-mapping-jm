"""
Load and extract fitted coefficients from Tröndle, Mey & Lilliestam's (2025)
discrete choice model (choice-model-inference.nc).

See CLAUDE.md and the project proposal for background on the model.
"""

import arviz as az
import numpy as np
import pandas as pd


def load_beta_partworths_mean(data_path: str, country: str = "NOT_SAMPLED") -> pd.DataFrame:
    """
    Load the fitted choice model and extract posterior-MEAN beta values
    for one country (a single point estimate per attribute).

    Use this for a first, quick pass (fixed betas). See
    `load_beta_partworths_samples` for the full posterior, needed for
    uncertainty quantification (credible intervals on utility/ranking).

    Returns
    -------
    pd.DataFrame with columns: attribute, beta_mean
    """
    idata = az.from_netcdf(data_path)
    beta = idata.posterior["beta_partworths"].sel(country=country)
    beta_mean = beta.mean(dim=["chain", "draw"])
    df = beta_mean.to_dataframe(name="beta_mean").reset_index()
    return df[["attribute", "beta_mean"]]


def load_beta_partworths_samples(data_path: str, country: str = "NOT_SAMPLED") -> dict:
    """
    Load the fitted choice model and extract ALL posterior samples of beta
    for one country, one array per attribute.

    Unlike `load_beta_partworths_mean`, this keeps every individual sample
    (chain x draw = e.g. 4 x 1000 = 4000 values per attribute), so utility
    can be computed once per sample, giving a distribution of utility
    values per scenario instead of a single point estimate.

    Parameters
    ----------
    data_path : str
        Path to choice-model-inference.nc
    country : str, default "NOT_SAMPLED"
        Which country's beta samples to extract.

    Returns
    -------
    dict[str, np.ndarray]
        Keys are attribute labels (e.g. "PRICES", "TECHNOLOGY:Wind").
        Values are 1D numpy arrays of length (n_chains * n_draws), the
        full set of posterior samples for that attribute's beta.
        All arrays have the same length and the same sample order, so
        beta_samples["PRICES"][i] and beta_samples["LAND"][i] both come
        from the same posterior draw i -- keep them aligned when computing
        utility per sample.

    Notes
    -----
    Ownership is not included: the model was fitted with only 6 attribute
    parameters (5 attributes; dominant technology as 2 categorical betas
    relative to a Rooftop PV reference), confirmed by the `attribute`
    coordinate itself containing no ownership-related label. Ownership was
    excluded before fitting, not just left out of this file's selection.
    """
    idata = az.from_netcdf(data_path)
    beta = idata.posterior["beta_partworths"].sel(country=country)

    # Combine the chain and draw dimensions into one "sample" dimension,
    # so each attribute's samples are a simple 1D array.
    beta_stacked = beta.stack(sample=("chain", "draw"))

    samples = {}
    for attr in beta_stacked.coords["attribute"].values:
        samples[attr] = beta_stacked.sel(attribute=attr).values

    return samples

def load_scenarios(scenarios_path: str) -> pd.DataFrame:
    """
    Load the scenarios CSV file, which contains the attribute values for
    each scenario to be evaluated.

    Parameters
    ----------
    scenarios_path : str
        Path to scenarios.csv

    Returns
    -------
    pd.DataFrame
        Columns: scenario_id, PRICES, LAND, TECHNOLOGY, OWNERSHIP
        Each row is one scenario.
    """
    df = pd.read_csv(scenarios_path)
    return df


if __name__ == "__main__":
    DATA_PATH = "../data/raw/choice-model-inference.nc"

    print("=== Mean betas (point estimate) ===")
    print(load_beta_partworths_mean(DATA_PATH))

    print()
    print("=== Sample betas (full posterior) ===")
    samples = load_beta_partworths_samples(DATA_PATH)
    for attr, values in samples.items():
        print(f"{attr}: {len(values)} samples, mean={values.mean():.4f}, "
              f"94% HDI=[{np.percentile(values, 3):.4f}, {np.percentile(values, 97):.4f}]")
