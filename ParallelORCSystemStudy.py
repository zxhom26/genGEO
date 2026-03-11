import os
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.fullSystemORC import FullSystemORC
from src.fullSystemSolver import FullSystemSolver
from models.wellFieldType import WellFieldType
from models.optimizationType import OptimizationType
from models.simulationParameters import SimulationParameters

# create output folder
output_folder = 'thesis_results'
os.makedirs(output_folder, exist_ok=True)

# initialize parameters template
params_template = SimulationParameters(
    working_fluid='water',
    orc_fluid='R245fa',
    wellFieldType=WellFieldType.Doublet,
    cost_year=2019,
    opt_mode=OptimizationType.MaximizePower,
    max_pump_dP=20.e6,
    k_rock=2.08,
    rho_rock=2550.,
)

# read wells CSV
base_path = Path(__file__).parent
csv_path = base_path / "test_wells.csv"
df_wells = pd.read_csv(csv_path, header=0, index_col=0)

def simulate_well(row):
    """Simulate a single well and return results."""
    try:
        print(f"Simulating Well {row.Index}...")

        # clone template parameters for each well
        params = SimulationParameters(**params_template.__dict__)

        # assign well-specific parameters
        if pd.isna(row.depth):
            raise ValueError("Depth is NaN, cannot simulate well")
        params.depth = row.depth
        params.dT_dz = row.harrison_gradient / 1000. if pd.notna(row.harrison_gradient) else 0.035
        params.T_surface_rock = row.surface_temp if pd.notna(row.surface_temp) else 15
        params.reservoir_thickness = row.depth if pd.notna(row.depth) else 100.
        params.k_rock = row.k if pd.notna(row.k) else 2.08

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
        print(f"Error caught for well {row.Index}: {e}")
        lcoe_b = lcoe_g = power = optMdot = 0.
        error_str = str(e).replace("\n", "").replace(",", " - ")

    return row.Index, optMdot, lcoe_b, lcoe_g, power, error_str

# run simulations in parallel
results = []
with ThreadPoolExecutor(max_workers=6) as executor:  # adjust workers to your CPU
    futures = {executor.submit(simulate_well, row): row.Index for row in df_wells.itertuples()}
    for future in as_completed(futures):
        results.append(future.result())

# write results to CSV
output_file_path = os.path.join(output_folder, 'gen_estimates.csv')
with open(output_file_path, 'w') as output_file:
    output_file.write("well,optMdot,lcoe_b,lcoe_g,power,error\n")
    for res in results:
        output_file.write(','.join([str(i) for i in res]) + "\n")