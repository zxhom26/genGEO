import os
import sys
import pandas as pd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
# Process Pool is multiprocessing for CPU-heavy load and Thread Pool is threading concurrency.

from src.fullSystemORC import FullSystemORC
from src.fullSystemSolver import FullSystemSolver
from models.wellFieldType import WellFieldType
from models.optimizationType import OptimizationType
from models.simulationParameters import SimulationParameters

# ----------- GLOBAL FILE PATHS ------------
# Base directory of the genGEO repository
GEN_GEO_DIR = Path(__file__).resolve().parent

# Parent GitHub directory containing both repositories
REPO_ROOT = GEN_GEO_DIR.parent

# SeniorThesis repository
THESIS_DIR = REPO_ROOT / "SeniorThesis"

# File paths
data_file = THESIS_DIR / "data" / "doe_wells_50.csv" # MODIFY FOR DIFF SUBSETS
output_folder = THESIS_DIR / "genGEO_results"
output_file = "gen_estimates9_doe_prop.csv" # MODIFY FOR NEW RESULTS

# Ensure file permissions before multiprocessing
def ensure_writable(path):
    try:
        with open(path, 'a'):
            pass
    except PermissionError:
        print(f"No write permission for {path}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error accessing {path}: {e}")
        sys.exit(1)

# Simulation function for a single well, to be run in parallel
def simulate_well(row):
    """Simulate a single well and return results."""
    # robustness for modified output variables
    thermal_gradient = 0.

    try:
        print(f"Simulating Well {row['index']}...")

        params = SimulationParameters(working_fluid='water',
                                        orc_fluid='R245fa',
                                        wellFieldType=WellFieldType.Doublet,
                                        cost_year=2019,
                                        opt_mode=OptimizationType.MaximizePower,
                                        # max_pump_dP=20.e6, # From high temp well papers
                                        # max_pump_dP=2.57e6, # Stanford paper run 8
                                        max_pump_dP=15.e6, # (Jiang, 2024) run 9
                                        rho_rock=2550.,
                                        capacity_factor = 0.90,) # DOE prop cap factor

        # assign well-specific parameters
        if pd.isna(row['depth']):
            raise ValueError("Depth is NaN, cannot simulate well") # fatal error
        params.depth = row['depth']

        if pd.notna(row['harrison_gradient']):
            params.dT_dz = row['harrison_gradient'] / 1000. # convert from C/km or K/km to K/m
        else:
            print(f"[Warning]: Harrison gradient is NaN for well {row['index']}, using default value of 35 K/km")
            params.dT_dz = 0.035
        thermal_gradient = params.dT_dz

        if pd.notna(row['surface_temp']):
            params.T_surface_rock = row['surface_temp']
        else: 
            print(f"[Warning]: Surface temperature is NaN for well {row['index']}, using default value of 15 C")
            params.T_surface_rock = 15
        
        params.reservoir_thickness = 100. # default value in case depth is NaN, but will be overwritten if depth is available
        # if pd.notna(row['depth']):
        #     params.reservoir_thickness = row['depth'] * 0.5 # ---- Assuming reservoir thickness is equal to HALF depth!!!!!! -----
        # else:
        #     print(f"[Warning]: Depth is NaN for well {row['index']}, using default reservoir thickness of 100 m")
        #     params.reservoir_thickness = 100.

        if pd.notna(row['k']):
            params.k_rock = row['k']
        else:
            print(f"[Warning]: Thermal conductivity is NaN for well {row['index']}, using default value of 2.08 W/m-K")
            params.k_rock = 2.08

        # simulate system
        full_system = FullSystemORC.getDefaultWaterSystem(params)
        solver = FullSystemSolver(full_system)
        output = solver.solve()

        lcoe_b = output.capital_cost_model.LCOE_brownfield.LCOE * 1e6
        lcoe_g = output.capital_cost_model.LCOE_greenfield.LCOE * 1e6
        power = output.energy_results.W_net / 1e6
        optMdot = output.optMdot
        error_str = ''

    except Exception as e:
        well_id = row.get("index", "unknown")
        print(f"Error caught for well {well_id}: {e}")

        # Default input params and output results in case of error
        lcoe_b = lcoe_g = power = optMdot = 0.
        error_str = str(e).replace("\n", "").replace(",", " - ")

    return row['index'], row['depth'], row['latitude'], row['longitude'], row['bhtcorrected_temp'], thermal_gradient, row['k'], optMdot, lcoe_b, lcoe_g, power, error_str

def main():
    # check permissions of output file
    output_file_path = output_folder / output_file
    ensure_writable(output_file_path)

    # create output folder
    output_folder.mkdir(parents=True, exist_ok=True)

    # read wells CSV
    df_wells = pd.read_csv(data_file, header=0, index_col=0).reset_index()

    # run simulations in parallel
    results = []
    workers = max(1, os.cpu_count() - 1)
    with ProcessPoolExecutor(max_workers=workers) as executor: 

        # futures = [executor.submit(simulate_well, row) for row in df_wells.to_dict(orient='records')]
        # for future in as_completed(futures):
        #     results.append(future.result())

        results = list(
                    executor.map(simulate_well, df_wells.to_dict(orient="records"))
                )

    # write results to CSV
    df_results = pd.DataFrame(results, columns=[
        "well","depth_m","latitude","longitude",
        "bhtcorrected_temp_C","thermal_gradient_K_m","k_W_mK",
        "optMdot","lcoe_b_USD","lcoe_g_USD","power_MW","error"
    ])
    df_results.to_csv(output_file_path, index=False)


if __name__ == "__main__":
    main()