"""Physical constants as Pint quantities wrapping SciPy CODATA values.

All downstream modules import the shared UnitRegistry and constants from here.
No raw floats should leak into engine code — everything carries units.
"""

import pint
from scipy import constants as sc

# Single shared registry — import this everywhere
ureg = pint.UnitRegistry()
Q_ = ureg.Quantity

# Exact physical constants as Pint quantities (CODATA 2018 exact values)
SPEED_OF_LIGHT = Q_(sc.speed_of_light, "m/s")  # 299_792_458 m/s (exact)
BOLTZMANN = Q_(sc.Boltzmann, "J/K")  # 1.380649e-23 J/K (exact)
PLANCK = Q_(sc.Planck, "J*s")  # 6.62607015e-34 J·s (exact)

# IEEE standard reference temperature
T_REF = Q_(290, "K")

# Derived: thermal noise floor at T_REF, 1 Hz bandwidth
# N = k_B * T = 1.380649e-23 * 290 = 4.00388e-21 W/Hz
# In dBm/Hz: 10 * log10(4.00388e-21 / 1e-3) = -173.977 ≈ -174 dBm/Hz
THERMAL_NOISE_FLOOR_DBM_PER_HZ = -174.0
