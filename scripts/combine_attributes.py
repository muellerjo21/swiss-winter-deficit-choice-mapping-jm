"""Fügt die Attribut-Zeilen aller Szenarien zu scenario_attributes_summary.csv zusammen."""
import pandas as pd


def combine(paths_to_scenarios: list[str], path_to_output: str) -> None:
    summary = pd.concat([pd.read_csv(p) for p in paths_to_scenarios], ignore_index=True)
    summary.sort_values("scenario_id").to_csv(path_to_output, index=False)


if __name__ == "__main__":
    combine(paths_to_scenarios=list(snakemake.input), path_to_output=snakemake.output[0])
