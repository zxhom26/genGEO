############################
import os
import numpy as np

# Change: Import FullSystemORC instead of FullSystemCPG
from src.fullSystemORC import FullSystemORC
from src.fullSystemSolver import FullSystemSolver
from models.simulationParameters import SimulationParameters

logTrans = np.arange(2., 8., 1.)
permeabilities = 1e-15 * 10. ** logTrans
depths = np.arange(1000, 8000, 1000)

# create output folder
output_folder = 'results'
if not os.path.exists(output_folder):
    os.mkdir(output_folder)

# Change: Updated filename to reflect ORC data
output_file = open(os.path.join(output_folder, 'data_ORC.csv'), 'w')

# Change: Initialize parameters for ORC. 
# Water is typically the reservoir fluid, and 'r245fa' is a common ORC working fluid.
params = SimulationParameters(working_fluid = 'r245fa', capacity_factor = 0.9)

# Change: Use the ORC factory method instead of CPG
full_system = FullSystemORC.getDefaultORCSystem(params)
full_system_solver = FullSystemSolver(full_system)

# iterate over all depths and permeabilities and solve the system
for depth in depths:
    for permeability in permeabilities:
        print('Depth: ', depth)
        print('Permeability: ', permeability)
        params.depth = depth
        # Note: GenGeo sometimes scales permeability; ensure this matches your reservoir model
        params.permeability = permeability / 100.

        try:
            output = full_system_solver.solve()
            # LCOE results are generally scaled to $/MWh in these scripts
            lcoe_b = output.capital_cost_model.LCOE_brownfield.LCOE * 1e6
            lcoe_g = output.capital_cost_model.LCOE_greenfield.LCOE * 1e6
            power = output.energy_results.W_net / 1e6
            optMdot = output.optMdot
            error_str = ''

        except Exception as error:
            error_str = str(error).replace("\n", "").replace(",", " - ")
            lcoe_b = 0.
            lcoe_g = 0.
            power = 0.
            optMdot = 0.

        output_file.write(','.join([str(i) for i in [depth, permeability, optMdot, lcoe_b, lcoe_g, power, """%s\n"""%error_str]]))

output_file.close()