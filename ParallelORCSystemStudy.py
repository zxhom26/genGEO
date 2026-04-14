import os
import sys
import subprocess
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
data_file = THESIS_DIR / "data" / "sabine_high_gradients.csv" # MODIFY FOR DIFF SUBSETS <----------------
output_folder = THESIS_DIR / "genGEO_results"
output_file = "gen_estimates17_sligo_hosston_100_res.csv" # MODIFY FOR NEW RESULTS <----------------

# Automatically push files to GitHub after running the script
def git_commit_and_push(repo_dir, file_path, branch="colab"):
    try:
        repo_dir = Path(repo_dir).resolve()
        file_path = Path(file_path).resolve()

        # Ensure file is inside repo (prevents accidental wrong-path commits)
        if repo_dir not in file_path.parents:
            raise ValueError(f"{file_path} is not inside repo {repo_dir}")

        rel_path = file_path.relative_to(repo_dir)

        # Checkout the correct branch
        subprocess.run(
            ["git", "-C", str(repo_dir), "checkout", branch],
            check=True
        )

        # Pull latest to avoid conflicts
        subprocess.run(
            ["git", "-C", str(repo_dir), "pull", "origin", branch],
            check=True
        )

        print("\n=== GIT DEBUG ===")
        subprocess.run(["git", "-C", str(repo_dir), "status"])
        print("Trying to add:", rel_path)
        print("=================\n")

        # Add ONLY the target file
        subprocess.run(
            ["git", "-C", str(repo_dir), "add", str(rel_path)],
            check=True
        )

        # Commit (gracefully handle no changes)
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", f"Update {rel_path}"],
            capture_output=True,
            text=True
        )

        if "nothing to commit" in (result.stdout + result.stderr).lower():
            print("No changes to commit.")
            return

        # Push to the correct branch
        subprocess.run(
            ["git", "-C", str(repo_dir), "push", "origin", branch],
            check=True
        )

        print(f"Pushed {rel_path} to {branch} successfully.")

    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
    except Exception as e:
        print(f"Error: {e}")

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
                                        # max_pump_dP=20.e6, # (Jiang, 2024) run 9
                                        max_pump_dP=20.e6, # (Jiang, 2024) run 9
                                        # permeability=1e-13, # 1e-15 m^2
                                        # permeability=1e-14, # Sli go-Hosston formation permeability, (Arzabala, 2026)
                                        permeability=5e-13, # 1e-15 m^2
                                        rho_rock=2550.,
                                        capacity_factor = 0.90,) # DOE prop cap factor

        # assign well-specific parameters
        # if pd.isna(row['depth']): # --------------------------------------------- RUN 13 SET DEPTH SPECIFICALLY TO SLIGO-HOSSTON depth 
        #     raise ValueError("Depth is NaN, cannot simulate well") # fatal error
        # params.depth = row['depth']

        params.depth = 2500. # Sligo-Hosston high permeability zone depth RUN 13 <----------------------------------

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
        
        params.reservoir_thickness = 100. # <---------------------------------- ASSUMPTION [100 - 600m thickness range in Sligo-Hosston]

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

    print("\n=== PATH DEBUG ===")
    print("GEN_GEO_DIR:", GEN_GEO_DIR)
    print("REPO_ROOT:", REPO_ROOT)
    print("THESIS_DIR:", THESIS_DIR)
    print("DATA FILE:", data_file)
    print("OUTPUT FOLDER:", output_folder)
    print("DATA EXISTS:", data_file.exists())
    print("OUTPUT FOLDER EXISTS:", output_folder.exists())
    print(f"Starting simulations for [{data_file}] with output to [{output_file_path}]...")
    print("==================\n")

    # read wells CSV
    df_wells = pd.read_csv(data_file, header=0, index_col=0).reset_index()
    print("\n=== DATA DEBUG ===")
    print("Number of wells loaded:", len(df_wells))
    print(df_wells.head())
    print("===================\n")

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
    print("=== RESULTS ===\n")
    print("Results returned:", len(results))
    print("Sample result:", results[0] if results else "NO RESULTS")
    print("=== RESULTS END ===\n")

    # write results to CSV
    df_results = pd.DataFrame(results, columns=[
        "well","depth_m","latitude","longitude",
        "bhtcorrected_temp_C","thermal_gradient_K_m","k_W_mK",
        "optMdot","lcoe_b_USD","lcoe_g_USD","power_MW","error"
    ])

    print("\n=== DATAFRAME DEBUG ===")
    print("Result rows:", len(df_results))
    print(df_results.head())
    print("======================\n")

    print("\n=== WRITE DEBUG ===")
    df_results.to_csv(output_file_path, index=False)

    print("Wrote to:", output_file_path)
    print("Exists after write:", output_file_path.exists())

    if output_file_path.exists():
        print("File size:", output_file_path.stat().st_size)
    else:
        print("FILE NOT CREATED")

    print("====================\n")

    # push to GitHub
    git_commit_and_push(THESIS_DIR, output_file_path)


if __name__ == "__main__":
    main()