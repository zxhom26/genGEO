import os
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
# Process Pool is multiprocessing for CPU-heavy load and Thread Pool is threading concurrency.

from src.fullSystemORC import FullSystemORC
from src.fullSystemSolver import FullSystemSolver
from models.wellFieldType import WellFieldType
from models.optimizationType import OptimizationType
from models.simulationParameters import SimulationParameters

# GLOBAL FILE PATHS
output_folder = 'thesis_results'
data_file = 'test_wells.csv'
output_file = 'gen_estimates3_multiprocessing.csv'

def simulate_well(row):
    """Simulate a single well and return results."""

    try:
        print(f"Simulating Well {row['index']}...")

        params = SimulationParameters(working_fluid='water',
                                        orc_fluid='R245fa',
                                        wellFieldType=WellFieldType.Doublet,
                                        cost_year=2019,
                                        opt_mode=OptimizationType.MaximizePower,
                                        max_pump_dP=20.e6,
                                        k_rock=2.08,
                                        rho_rock=2550.,)

        # assign well-specific parameters
        if pd.isna(row['depth']):
            raise ValueError("Depth is NaN, cannot simulate well") # fatal error
        params.depth = row['depth']

        if pd.notna(row['harrison_gradient']):
            params.dT_dz = row['harrison_gradient'] / 1000. # convert from K/km to K/m
        else:
            print(f"[Warning]: Harrison gradient is NaN for well {row['index']}, using default value of 35 K/km")
            params.dT_dz = 0.035

        if pd.notna(row['surface_temp']):
            params.T_surface_rock = row['surface_temp']
        else: 
            print(f"[Warning]: Surface temperature is NaN for well {row['index']}, using default value of 15 C")
            params.T_surface_rock = 15
        
        if pd.notna(row['depth']):
            params.reservoir_thickness = row['depth'] # Assuming reservoir thickness is equal to depth!!!!
        else:
            print(f"[Warning]: Depth is NaN for well {row['index']}, using default reservoir thickness of 100 m")
            params.reservoir_thickness = 100.

        if pd.notna(row['k']):
            params.k_rock = row['k']
        else:
            print(f"[Warning]: Permeability is NaN for well {row['index']}, using default value of 2.08 mD")
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
        print(f"Error caught for well {row['index']}: {e}")
        # Default input params and output results in case of error
        params.dT_dz = 0.0
        lcoe_b = lcoe_g = power = optMdot = 0.

        error_str = str(e).replace("\n", "").replace(",", " - ")

    return row['index'], row['depth'], row['latitude'], row['longitude'], row['bhtcorrected_temp'], params.dT_dz, row['k'], optMdot, lcoe_b, lcoe_g, power, error_str

def main():
    # create output folder
    os.makedirs(output_folder, exist_ok=True)

    # read wells CSV
    base_path = Path(__file__).parent
    csv_path = base_path / data_file
    df_wells = pd.read_csv(csv_path, header=0, index_col=0).reset_index()

    # run simulations in parallel
    results = []
    workers = max(1, os.cpu_count() - 1)
    with ProcessPoolExecutor(max_workers=workers) as executor: 
        futures = [executor.submit(simulate_well, row) for row in df_wells.to_dict(orient='records')]
        for future in as_completed(futures):
            results.append(future.result())

    # write results to CSV
    output_file_path = os.path.join(output_folder, output_file)
    with open(output_file_path, 'w') as f:
        f.write("well,depth,latitude,longitude,bhtcorrected_temp,thermal_gradient_K_m,k_mD,optMdot,lcoe_b,lcoe_g,power,error\n")
        for res in results:
            f.write(','.join([str(i) for i in res]) + "\n")


if __name__ == "__main__":
    main()