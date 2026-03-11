# Licensed under LGPL 2.1, please see LICENSE for details
# https://www.gnu.org/licenses/lgpl-2.1.html
#
# The work on this project has been performed at the GEG Group at ETH Zurich:
# --> https://geg.ethz.ch
#
# The initial version of this file has been implemented by:
#
#     Philipp Schaedle (https://github.com/philippschaedle)
#     Benjamin M. Adams
#
# Further changes are done by:
#

############################
import os
import pandas as pd
from pathlib import Path

from src.fullSystemORC import FullSystemORC
from src.fullSystemSolver import FullSystemSolver
from models.wellFieldType import WellFieldType
from models.optimizationType import OptimizationType
from models.simulationParameters import SimulationParameters

# create output folder
output_folder = 'thesis_results'
if not os.path.exists(output_folder):
    os.mkdir(output_folder)

# output_file = open(os.path.join(output_folder, 'exampleORC.csv'), 'w')
with open(os.path.join(output_folder, 'gen_estimates.csv'), 'w') as output_file:
    output_file.write("optMdot,lcoe_b,lcoe_g,power,error\n") # writing header information for output file

    # initialize parameters
    params = SimulationParameters(working_fluid = 'water', 
                                orc_fluid = 'R245fa', # or R600a
                                wellFieldType = WellFieldType.Doublet,
                                cost_year = 2019,
                                opt_mode = OptimizationType.MaximizePower,
                                max_pump_dP = 20.e6, # CHECK TO MAKE SURE THIS IS A REASONABLE VALUE FOR THE PUMPING PRESSURE DROP, AS THIS WILL AFFECT WHETHER OR NOT THE SYSTEM CAN FIND A FEASIBLE SOLUTION
                                k_rock = 2.08, # W/m-K, average conductivity across all wells >120C in LA/TX
                                rho_rock = 2550.,) # kg/m^3, lower band assumption for sedimentary rock density
    '''
    working_fluid = None,
    orc_fluid = None,
    m_dot_IP = None,
    time_years = 1.,
    # subsurface model
    depth = 2500.,
    pump_depth = 500.,
    well_radius = 0.205,
    well_spacing = 707.,
    monitoring_well_radius = 0.108,
    dT_dz = 0.035,
    silica_precipitation = False, 
    T_surface_rock = 15,
    T_ambient_C = 15.,
    reservoir_thickness = 100.,
    permeability = 1.0e-15 * 15000 / 100., # permeability = transmissivity / thickness
    wellFieldType = WellFieldType._5Spot_SharedNeighbor,
    N_5spot = 1, #Square-root of numbe of 5spots which share a central plant in a Many_N configuration. e.g. N=2 is 4 5spots.
    has_surface_gathering_system = True,
    # power plant model
    max_pump_dP = 10.e6,
    eta_pump = 0.75,
    dT_approach = 7.,
    dT_pinch = 5.,
    eta_pump_orc = 0.9,
    eta_turbine_orc = 0.8,
    eta_pump_co2 = 0.9,
    eta_turbine_co2 = 0.78,
    cooling_mode = CoolingCondensingTowerMode.Wet,
    # cost model
    cost_year = 2019,
    success_rate = 0.95,
    F_OM = 0.045,
    discount_rate = 0.096,
    lifetime = 25,
    capacity_factor = 0.85,
    opt_mode = OptimizationType.MinimizeCost,
    # physical properties
    g = 9.81,                       # m/s**2
    rho_rock = 2650.,               # kg/m**3
    c_rock = 1000.,                 # J/kg-K
    k_rock = 2.1,                   # W/m-K
    useWellboreHeatLoss = True,     # bool
    well_segments = 100,            # number of well segments
    # Friction factor
    well_relative_roughness = 55 * 1e-6             # um
    '''

    # iterate over all hot wells (>120C) in LA/TX and solve the system
    base_path = Path(__file__).parent
    csv_path = base_path / "test_wells.csv" # -----------------------------MODIFY HERE WHEN WE HAVE WELLS WE WANT TO ITERATE OVER
    df_wells = pd.read_csv(csv_path, header=0, index_col=0)

    for row in df_wells.itertuples(index=True):
        try:
            # Error checking
            print("============================================================")
            print(f"Well: {row.Index}") # Well #
            print(f"Depth: {row.depth}") # m
            print(f"Gradient dT/dz: {row.harrison_gradient}") # C/km --> system expects C/m, so divide by 1000
            print(f"Surface Temp: {row.surface_temp}") # C
            print(f"Conductivity K: {row.k}") # W/m-K
            print("============================================================")

            # Set well parameters
            if pd.isna(row.depth):
                raise ValueError("Depth is NaN, cannot simulate well") # skip wells with missing depth information
            params.depth = row.depth 
            
            # Set thermodynamic parameters
            params.dT_dz = row.harrison_gradient / 1000. if pd.notna(row.harrison_gradient) else 0.035 # default value for harrison gradient
            params.T_surface_rock = row.surface_temp if pd.notna(row.surface_temp) else 15 # default value for surface temperature
            
            # Set physical property parameters
            params.reservoir_thickness = row.depth if pd.notna(row.depth) else 100. # default value for reservoir thickness
            params.k_rock = row.k if pd.notna(row.k) else 2.08 # average conductivity across all wells [W/m-K]

            # Generate the full system
            full_system = FullSystemORC.getDefaultWaterSystem(params)
            full_system_solver = FullSystemSolver(full_system)

            # Run simulation 
            output = full_system_solver.solve()
            lcoe_b = output.capital_cost_model.LCOE_brownfield.LCOE * 1e6
            lcoe_g = output.capital_cost_model.LCOE_greenfield.LCOE * 1e6
            power = output.energy_results.W_net / 1e6
            optMdot = output.optMdot
            error_str = ''

        except Exception as error:
            print("============================================================")
            print(f"Error caught for well {row.Index}")
            print(f"Error: {error}")
            print("============================================================")
            error_str = str(error).replace("\n", "").replace(",", " - ")
            lcoe_b = 0.
            lcoe_g = 0.
            power = 0.
            optMdot = 0.

        output_file.write(','.join([str(i) for i in [optMdot, lcoe_b, lcoe_g, power, """%s\n"""%error_str]]))




'''
# iterate over all depths and permeabilities and solve the system
for depth in depths:
    for permeability in permeabilities:
        print('Depth: ', depth)
        print('Permeability: ', permeability)
        params.depth = depth
        # params.permeability = permeability / 100.
        params.permeability = permeability

        try:
            output = full_system_solver.solve()
            lcoe_b = output.capital_cost_model.LCOE_brownfield.LCOE * 1e6
            lcoe_g = output.capital_cost_model.LCOE_greenfield.LCOE * 1e6
            power = output.energy_results.W_net / 1e6
            optMdot = output.optMdot
            error_str = ''

        except Exception as error:
            print("============================================================")
            print(f"Error caught for depth: {depth}, permeability: {permeability}")
            print(f"Error: {error}")
            print("============================================================")
            error_str = str(error).replace("\n", "").replace(",", " - ")
            lcoe_b = 0.
            lcoe_g = 0.
            power = 0.
            optMdot = 0.

        output_file.write(','.join([str(i) for i in [depth, permeability, optMdot, lcoe_b, lcoe_g, power, """%s\n"""%error_str]]))

output_file.close()
'''