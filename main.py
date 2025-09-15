import numpy as np
import pandas as pd
import casadi as ca
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, time
import tenseal as ts
import logging
import os
import random
from dataclasses import dataclass
from typing import List, Dict, Optional
from pyfmi import load_fmu
import json
from pykalman import KalmanFilter

# =============================================================================
# File Paths
# =============================================================================
AR_MODEL_PATH1 = "models/ar_model_parameters_bldg1.json"
AR_MODEL_PATH2 = "models/ar_model_parameters_bldg2.json"
AR_MODEL_PATH3 = "models/ar_model_parameters_bldg3.json"
AR_MODEL_PATH4 = "models/ar_model_parameters_bldg4.json"

FMU_PATH1 = "fmus/bldg1.fmu"
FMU_PATH2 = "fmus/bldg2.fmu"
FMU_PATH3 = "fmus/bldg3.fmu"
FMU_PATH4 = "fmus/bldg4.fmu"

INPUT_FILE1 = "data/bldg1_inputs.csv"
OUTPUT_FILE1 = "data/bldg1_outputs.csv"
INPUT_FILE2 = "data/bldg2_inputs.csv"
OUTPUT_FILE2 = "data/bldg2_outputs.csv"
INPUT_FILE3 = "data/bldg3_inputs.csv"
OUTPUT_FILE3 = "data/bldg3_outputs.csv"
INPUT_FILE4 = "data/bldg4_inputs.csv"
OUTPUT_FILE4 = "data/bldg4_outputs.csv"

HVAC_OUTPUT_FILE1 = "data/bldg1_hvac_outputs.csv"
HVAC_OUTPUT_FILE2 = "data/bldg2_hvac_outputs.csv"
HVAC_OUTPUT_FILE3 = "data/bldg3_hvac_outputs.csv"
HVAC_OUTPUT_FILE4 = "data/bldg4_hvac_outputs.csv"

# =============================================================================
# Simulation and ADMM Parameters
# =============================================================================
PREDICTION_HORIZON = 16

PROCESS_NOISE_SCALE = 1e-3
MEASUREMENT_NOISE = 0.1

PRICE_PERIODS = {
    'OFF_PEAK': {'rate': 0.065},  # Lower off-peak rate
    'MID_PEAK': {'rate': 0.145},  # Higher mid-peak rate
    'ON_PEAK': {'rate': 0.235}    # Significantly higher on-peak rate
}

WEEKDAY_PERIODS = [
    {'start': time(0, 0), 'end': time(7, 0), 'period': 'OFF_PEAK'},
    {'start': time(7, 0), 'end': time(10, 0), 'period': 'ON_PEAK'},
    {'start': time(10, 0), 'end': time(17, 0), 'period': 'MID_PEAK'},
    {'start': time(17, 0), 'end': time(21, 0), 'period': 'ON_PEAK'},
    {'start': time(21, 0), 'end': time(23, 59, 59), 'period': 'OFF_PEAK'}
]

WEEKEND_PERIODS = [
    {'start': time(0, 0), 'end': time(23, 59, 59), 'period': 'OFF_PEAK'}
]

BLDG1_COMFORTABLE_TEMP_MIN = 19.0
BLDG1_COMFORTABLE_TEMP_MAX = 23.0
BLDG1_DEFAULT_SETPOINT = 21.0
BLDG1_U_LB = 19.0
BLDG1_U_UB = 23.0

BLDG2_COMFORTABLE_TEMP_MIN = 17.0
BLDG2_COMFORTABLE_TEMP_MAX = 22.0
BLDG2_DEFAULT_SETPOINT = 20.0
BLDG2_U_LB = 17.0
BLDG2_U_UB = 22.0

BLDG3_COMFORTABLE_TEMP_MIN = 19.0
BLDG3_COMFORTABLE_TEMP_MAX = 22.0
BLDG3_DEFAULT_SETPOINT = 21.0
BLDG3_U_LB = 19.0
BLDG3_U_UB = 22.0

BLDG4_COMFORTABLE_TEMP_MIN = 19.0
BLDG4_COMFORTABLE_TEMP_MAX = 22.0
BLDG4_DEFAULT_SETPOINT = 21.0
BLDG4_U_LB = 19.0
BLDG4_U_UB = 22.0


# RHO = 10.0
RHO = 1

# EPSILON = 1e-3
EPSILON = 1e-2

# MAX_ADMM_ITER = 200
MAX_ADMM_ITER = 400

P_MAX = 14.0


BIG_NUMBER = 1e6

BASE_DATE = datetime(2018, 1, 1, 0, 0, 0)
SIMULATION_START_DATETIME = datetime(2018, 2, 20, 0, 0, 0)
SIMULATION_DURATION_DAYS = 1
START_TIME = (SIMULATION_START_DATETIME - BASE_DATE).total_seconds()
STOP_TIME = START_TIME + (SIMULATION_DURATION_DAYS * 24 * 3600)
STEP_SIZE = 900

# =============================================================================
# System Matrices for Building 1
# =============================================================================
A1_ORIG = np.array([
    [0.3078, -0.0353, -0.0193],
    [0.2607, -0.0501,  0.1021],
    [0.7746,  0.3579,  0.6080]
])
B1_ORIG = np.array([
    [ 0.0005, -0.0121, -0.0007, -0.0098,  0.0001, -0.0001,  0.0,    -0.0,    -0.0002, -0.0   ],
    [-0.0005,  0.0029, -0.0034,  0.0206, -0.0009, -0.0005,  0.0001,  0.0,    -0.0029, -0.0015],
    [-0.0073,  0.0393,  0.0087, -0.0694,  0.0006,  0.0007, -0.0,     0.0,    -0.0009,  0.0001]
])
C1_ORIG = np.array([
    [-18.0853, -0.5825,  0.1888]
])
D1_ORIG = np.array([
    [ 0.0245,  0.6385, -0.0288, -0.1244,  0.0025, -0.0021,  0.0001, -0.0, -0.0013,  0.0008]
])
K1 = np.array([[-0.0318], [ 0.0863], [ 0.2342]]).flatten()

# =============================================================================
# System Matrices for Building 2
# =============================================================================
A2_ORIG = np.array([
    [ 0.4103, -0.0014, -0.0012],
    [-1.2718,  0.6993,  0.3081],
    [-0.3558,  0.0936, -0.1095]
])
B2_ORIG = np.array([
    [ 0.0004, -0.0113, -0.0005, -0.0077, -0.0001, -0.0,    -0.0,     0.0,    -0.0001, -0.0   ],
    [ 0.006 , -0.0501, -0.006 ,  0.0597,  0.0002, -0.0006,  0.0 ,    -0.0,     0.0014,  0.0003],
    [-0.0221,  0.002 ,  0.0202, -0.0164, -0.0016, -0.0003, -0.0 ,    -0.0,    -0.0061, -0.001 ]
])
C2_ORIG = np.array([
    [-16.9809, -0.4941,  0.3203]
])
D2_ORIG = np.array([
    [ 0.0175,  0.6401, -0.0205, -0.1167, -0.0017, -0.0022, -0.0, 0.0, -0.0024,  0.0003]
])
K2 = np.array([[-0.0296], [-0.0364], [-0.0075]]).flatten()

# =============================================================================
# System Matrices for Building 3 (ID 202)
# =============================================================================
A3_ORIG = np.array([
    [ 0.0303,  0.0025,  0.0379],
    [ 0.2097,  0.015,  -0.0824],
    [ 0.5688,  0.0727, -0.441 ]
])
B3_ORIG = np.array([
    [ 0.0005, -0.0038, -0.0004, -0.0084,  0.    , -0.0002, -0.    ,  0.    ,  0.    ,  0.    ],
    [ 0.0007,  0.0347, -0.0012, -0.1093,  0.0002, -0.0014,  0.    , -0.    ,  0.0001, -0.    ],
    [-0.0098, -0.001 ,  0.0087,  0.019 , -0.001 , -0.0009, -0.    , -0.    , -0.0002, -0.0004]
])
C3_ORIG = np.array([
    [-4.4664,  0.3932, -0.0045]
])
D3_ORIG = np.array([
    [ 0.0005,  0.9691, -0.0004,  0.0054, -0.    , -0.0006, -0.    ,  0.    ,  0.    ,  0.    ]
])
K3 = np.array([[-0.0063], [ 0.012 ], [-0.0601]]).flatten()

# =============================================================================
# System Matrices for Building 4 (ID 57693)
# =============================================================================
A4_ORIG = np.array([
    [-0.0389,  0.0271,  0.0279],
    [ 0.5482, -0.3143, -0.0861],
    [-0.148 ,  0.3717, -0.0069]
])
B4_ORIG = np.array([
    [-0.0002, -0.0075,  0.0002, -0.0043, -0.    ,  0.    , -0.    ,  0.    ,  0.    , -0.    ],
    [-0.009 , -0.0062,  0.0118,  0.0492,  0.001 ,  0.0006, -0.    ,  0.    , -0.0012, -0.0005],
    [ 0.0159, -0.0227, -0.0193,  0.0523,  0.0001, -0.0009,  0.    , -0.    ,  0.0008,  0.001 ]
])
C4_ORIG = np.array([
    [-7.6556, -0.0377, -0.0549]
])
D4_ORIG = np.array([
    [ 0.0002,  0.9373,  0.0001, -0.0072,  0.    ,  0.0001, -0.    ,  0.    ,  0.0003,  0.0001]
])
K4 = np.array([[-0.0108], [-0.1315], [-0.1718]]).flatten()

# =============================================================================
# Price and Disturbance Functions
# =============================================================================
def get_price_period(current_time):
    current_time_of_day = current_time.time()
    is_weekend = current_time.weekday() >= 5
    periods = WEEKEND_PERIODS if is_weekend else WEEKDAY_PERIODS
    for period in periods:
        if period['start'] <= current_time_of_day <= period['end']:
            return period['period']
    return 'OFF_PEAK'

def get_price_rate(current_time):
    return PRICE_PERIODS[get_price_period(current_time)]['rate']

def build_disturbance_horizon_from_csv(data, current_index, horizon_length):
    cols = [
        'T_outdoor_dry',
        'Single_setpoint',
        'T_outdoor_wet',
        'T_waterMains',
        'T_sky',
        'People_count',
        'Diffuse_solar_radiation',
        'Direct_solar_radiation',
        'Wind_speed',
        'Relative_humidity'
    ]
    d_horizon = np.zeros((len(cols), horizon_length))
    current_index = max(0, min(current_index, len(data) - 1))
    for i in range(horizon_length):
        idx = current_index + i if (current_index + i) < len(data) else len(data) - 1
        d_horizon[:, i] = data.loc[idx, cols].values
    return d_horizon

# =============================================================================
# Logging Setup
# =============================================================================
def setup_logging(log_filepath=None, console_level=logging.INFO, file_level=logging.INFO):
    logger = logging.getLogger("mpc_controller")
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    if log_filepath:
        file_handler = logging.FileHandler(log_filepath)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
    return logger

# =============================================================================
# FMU Simulation Class
# =============================================================================
class FMUSimulation:
    def __init__(
        self,
        fmu_path,
        start_time,
        stop_time,
        step_size=900,
        variable_mapping=None,
        preconditioned_fmu=None
    ):
        self.fmu_path = fmu_path
        self.start_time = start_time
        self.stop_time = stop_time
        self.step_size = step_size
        self.variable_mapping = variable_mapping or {}
        self.logger = logging.getLogger("mpc_controller")
        if (stop_time - start_time) % 86400 != 0:
            self.stop_time = start_time + 86400 * ((stop_time - start_time) // 86400)
            if self.stop_time < stop_time:
                self.stop_time += 86400
        if fmu_path and fmu_path.strip():
            if preconditioned_fmu is not None:
                self.fmu = preconditioned_fmu
                self.fmu.setup_experiment(start_time=self.start_time, stop_time=self.stop_time)
                self.fmu.initialize()
            else:
                self.fmu = load_fmu(self.fmu_path)
                self.fmu.setup_experiment(start_time=self.start_time, stop_time=self.stop_time)
                self.fmu.initialize()
        else:
            self.fmu = None
        self.sim_time = self.start_time

    def get_variable(self, var_name):
        if self.fmu is None:
            return 0.0
        return self.fmu.get(self.variable_mapping.get(var_name, var_name))[0]

    def set_variable(self, var_name, value):
        if self.fmu is None:
            return
        self.fmu.set(self.variable_mapping.get(var_name, var_name), value)

    def step(self):
        if self.fmu is None:
            self.sim_time += self.step_size
            if self.sim_time >= self.stop_time:
                return False
            return True
        if self.sim_time >= self.stop_time:
            return False
        self.fmu.do_step(current_t=self.sim_time, step_size=self.step_size, new_step=True)
        self.sim_time += self.step_size
        return True

    def terminate(self):
        if self.fmu is not None:
            self.fmu.terminate()

    def get_fmu_measurements(self):
        if self.fmu is None:
            return {
                'T_outdoor_dry': 20.0,
                'T_outdoor_wet': 18.0,
                'T_waterMains': 15.0,
                'T_sky': 10.0,
                'People_count': 2.0,
                'Diffuse_solar_radiation': 0.0,
                'Direct_solar_radiation': 0.0,
                'Wind_speed': 0.5,
                'Relative_humidity': 50.0,
                'zone_temp': 20.0,
                'Single_setpoint': 20.0,
                'P_hvac_heating': 0.0,
                'P_hvac_cooling': 0.0
            }
        try:
            m = {
                'OutTempDry': self.get_variable('OutTempDry'),
                'OutTempWet': self.get_variable('OutTempWet'),
                'MainsWaterTemp': self.get_variable('MainsWaterTemp'),
                'SkyTemp': self.get_variable('SkyTemp'),
                'PeopleCount': self.get_variable('PeopleCount'),
                'DiffuseRad': self.get_variable('DiffuseRad'),
                'DirectRad': self.get_variable('DirectRad'),
                'WindSpeed': self.get_variable('WindSpeed'),
                'RelativeHumidity': self.get_variable('RelativeHumidity'),
                'ZoneTempFMU': self.get_variable('ZoneTempFMU'),
                'ZoneSetpoint': self.get_variable('ZoneSetpoint'),
                'HeatPumpHeatingRate': self.get_variable('HeatPumpHeatingRate'),
                'HeatPumpCoolingRate': self.get_variable('HeatPumpCoolingRate')
            }
            return {
                'T_outdoor_dry': m['OutTempDry'],
                'T_outdoor_wet': m['OutTempWet'],
                'T_waterMains': m['MainsWaterTemp'],
                'T_sky': m['SkyTemp'],
                'People_count': m['PeopleCount'],
                'Diffuse_solar_radiation': m['DiffuseRad'],
                'Direct_solar_radiation': m['DirectRad'],
                'Wind_speed': m['WindSpeed'],
                'Relative_humidity': m['RelativeHumidity'],
                'zone_temp': m['ZoneTempFMU'],
                'Single_setpoint': m['ZoneSetpoint'],
                'P_hvac_heating': m['HeatPumpHeatingRate'] / 1000.0,
                'P_hvac_cooling': m['HeatPumpCoolingRate'] / 1000.0
            }
        except:
            self.logger.error("Error getting FMU measurements")
            return None

    def apply_control(self, setpoint):
        if self.fmu is None:
            return
        self.set_variable('SingleSetpoint', setpoint)

# =============================================================================
# DSO Class
# =============================================================================
@dataclass
class DSO:
    context_full: ts.Context
    scale: int = 10**3

    @classmethod
    def create_full_context(cls, poly_modulus_degree=8192, plain_modulus=1032193, scale=10**3):
        ctx = ts.context(
            ts.SCHEME_TYPE.BFV,
            poly_modulus_degree=poly_modulus_degree,
            plain_modulus=plain_modulus
        )
        ctx.generate_galois_keys()
        return cls(context_full=ctx, scale=scale)

    def create_public_context(self) -> ts.Context:
        public_ctx = self.context_full.copy()
        public_ctx.make_context_public()
        return public_ctx

    def decrypt_aggregate(self, enc_sum: ts.BFVVector) -> float:
        decrypted_list = enc_sum.decrypt(secret_key=self.context_full.secret_key())
        return decrypted_list[0] / self.scale

# =============================================================================
# Central Hierarchical ADMM Coordinator
# =============================================================================

class HierarchicalADMMCoordinator:
    def __init__(
        self,
        num_buildings,
        prediction_horizon,
        power_limit=P_MAX,
        penalty_param=RHO,
        max_iterations=50,
        tolerance=1e-4,
        public_ctx=None,
        dso=None
    ):
        self.num_buildings = num_buildings
        self.Np = prediction_horizon
        self.power_limit = power_limit
        self.rho = penalty_param
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.public_ctx = public_ctx
        self.dso = dso
        self.current_step = 0

        self.z = {i: np.zeros(prediction_horizon) for i in range(num_buildings)}
        self.lambda_bar = np.zeros(prediction_horizon)
        self.Pi = np.zeros(prediction_horizon)
        self.a_bar = np.zeros(prediction_horizon)
        self.a_bar_prev = np.zeros(prediction_horizon)

    def homomorphic_add(self, enc_a, enc_b):
        return enc_a + enc_b

    def solve_central_step(self, enc_powers, current_iter=0, max_iter=MAX_ADMM_ITER):
        # Decrypt and process encrypted power predictions
        z_sum = np.zeros(self.Np)
        for step in range(self.Np):
            decrypted_sum = self.dso.decrypt_aggregate(enc_powers[step])
            z_sum[step] = decrypted_sum
        
        # Standard ADMM projection onto the feasible set
        # Use a constant power limit instead of time-varying limits
        projected_sum = np.zeros(self.Np)
        for t in range(self.Np):
            # Simple shifted sum with dual variable
            shifted_sum = z_sum[t] + (1/self.rho) * self.lambda_bar[t]
            
            # Basic projection onto the power constraint
            if shifted_sum > self.power_limit:
                projected_sum[t] = self.power_limit
            else:
                projected_sum[t] = shifted_sum
        
        # Update dual variables
        self.lambda_bar_prev = self.lambda_bar.copy()
        self.lambda_bar = self.lambda_bar + self.rho * (z_sum - projected_sum)
        
        # Update consensus variable
        self.a_bar_prev = self.a_bar
        self.a_bar = projected_sum
        self.Pi = self.a_bar
        
        # Track the current step
        self.current_step += 1
        
        # Return updated guidance
        return self.Pi, self.lambda_bar

    # def solve_central_step(self, enc_powers, current_iter=0, max_iter=MAX_ADMM_ITER):
    #     # Decrypt and process encrypted power predictions
    #     z_sum = np.zeros(self.Np)
    #     for step in range(self.Np):
    #         decrypted_sum = self.dso.decrypt_aggregate(enc_powers[step])
    #         z_sum[step] = decrypted_sum
        
    #     # Get current time
    #     time_current = SIMULATION_START_DATETIME + timedelta(seconds=self.current_step * STEP_SIZE)
        
    #     # Define time-varying power limits based on ToU periods
    #     dynamic_power_limits = np.zeros(self.Np)
    #     for i in range(self.Np):
    #         forecast_time = time_current + timedelta(seconds=STEP_SIZE * i)
    #         period = get_price_period(forecast_time)
            
    #         if period == 'OFF_PEAK':
    #             dynamic_power_limits[i] = self.power_limit * 1.5  # 50% higher during off-peak
    #         elif period == 'MID_PEAK':
    #             dynamic_power_limits[i] = self.power_limit * 1.0  # Standard during mid-peak
    #         else:  # ON_PEAK
    #             dynamic_power_limits[i] = self.power_limit * 0.6  # 40% lower during on-peak
        
    #     # Adaptive softness: starts softer and becomes stricter as iterations progress
    #     initial_softness = 0.3
    #     final_softness = 0.05
    #     progress_ratio = min(1.0, current_iter / (0.7 * max_iter))
    #     softness_factor = initial_softness - (initial_softness - final_softness) * progress_ratio
        
    #     # Project using dynamic power limits
    #     projected_sum = np.zeros(self.Np)
    #     for t in range(self.Np):
    #         shifted_sum = z_sum[t] + (1/self.rho) * self.lambda_bar[t]
            
    #         if shifted_sum > dynamic_power_limits[t]:
    #             excess = shifted_sum - dynamic_power_limits[t]
    #             # Higher penalty for larger violations
    #             violation_ratio = excess / dynamic_power_limits[t]
    #             base_penalty = 1.0 / (1.0 + softness_factor * self.rho)
    #             # Additional penalty for large violations
    #             additional_penalty = 1.0 - np.exp(-5.0 * violation_ratio)
    #             penalty = base_penalty + additional_penalty * (1.0 - base_penalty)
    #             projected_sum[t] = dynamic_power_limits[t] + excess * (1.0 - penalty)
    #         else:
    #             projected_sum[t] = shifted_sum
        
    #     # Update dual variables and consensus
    #     self.lambda_bar_prev = self.lambda_bar.copy()
    #     self.lambda_bar = self.lambda_bar + self.rho * (z_sum - projected_sum)
        
    #     self.a_bar_prev = self.a_bar
    #     self.a_bar = projected_sum
    #     self.Pi = self.a_bar
        
    #     # Track the current step for time-based calculations
    #     self.current_step += 1
        
    #     # Return updated guidance
    #     return self.Pi, self.lambda_bar

    def update_rho(self, primal_res, dual_res, tau=1.5, mu=10.0):
        if primal_res > mu * dual_res:
            self.rho = self.rho * tau
            self.lambda_bar = self.lambda_bar * tau
        elif dual_res > mu * primal_res:
            self.rho = self.rho / tau
            self.lambda_bar = self.lambda_bar / tau
        return self.rho

    def check_convergence(self, z_new, z_old):
        z_sum = np.zeros(self.Np)
        for i in range(self.num_buildings):
            z_sum += z_new[i]
        constraint_violation = np.maximum(0, z_sum - self.power_limit)
        max_violation = np.max(constraint_violation)
        primal_res = max_violation
        dual_res = self.rho * np.linalg.norm(self.a_bar - self.a_bar_prev)
        logger = logging.getLogger("mpc_controller")
        logger.info(f"Constraint violation = {primal_res:.6f}, Dual residual = {dual_res:.6f}")
        return (primal_res < self.tolerance) and (dual_res < self.tolerance)

    def broadcast_guidance(self):
        return self.Pi, self.lambda_bar


# =============================================================================
# Privacy-Preserving Agent
# =============================================================================
class PrivacyPreservingAgent:
    def __init__(self, agent_id: int, public_ctx: ts.Context, scale: int = 10**3):
        self.agent_id = agent_id
        self.public_ctx = public_ctx
        self.scale = scale

    def encrypt_power(self, power: float) -> ts.BFVVector:
        power_int = int(round(power * self.scale))
        return ts.bfv_vector(self.public_ctx, [power_int])

    def add_encrypted_power(self, my_power: float, previous_cipher: ts.BFVVector) -> ts.BFVVector:
        my_cipher = self.encrypt_power(my_power)
        return previous_cipher + my_cipher

def perform_random_chain_summation(agents, power_predictions, permutation=None):
    num_agents = len(agents)
    if permutation is None:
        permutation = list(range(num_agents))
        random.shuffle(permutation)
    horizon_length = len(power_predictions[0])
    encrypted_sums = []
    for step in range(horizon_length):
        first_agent_idx = permutation[0]
        first_agent = agents[first_agent_idx]
        current_cipher = first_agent.encrypt_power(power_predictions[first_agent_idx][step])
        for i in range(1, num_agents):
            agent_idx = permutation[i]
            agent = agents[agent_idx]
            current_cipher = agent.add_encrypted_power(
                power_predictions[agent_idx][step],
                current_cipher
            )
        encrypted_sums.append(current_cipher)
    return encrypted_sums

# =============================================================================
# Data Loading Utilities
# =============================================================================
def load_data(input_file_path, output_file_path):
    input_data = pd.read_csv(input_file_path)
    output_data = pd.read_csv(output_file_path)
    required_columns = [
        'T_outdoor_dry',
        'Single_setpoint',
        'T_outdoor_wet',
        'T_waterMains',
        'T_sky',
        'People_count',
        'Diffuse_solar_radiation',
        'Direct_solar_radiation',
        'Wind_speed',
        'Relative_humidity'
    ]
    for col in required_columns:
        if col not in input_data.columns:
            raise ValueError(f"Required column '{col}' not found in input data")
    data = pd.DataFrame()
    for col in required_columns:
        data[col] = input_data[col]
    data['LIVING SPACE:Zone Mean Air Temperature [C](TimeStep)'] = \
        output_data['LIVING SPACE:Zone Mean Air Temperature [C](TimeStep)']
    return data

# =============================================================================
# MPC Problem Construction 
# =============================================================================

def build_mpc_problem_qp_hierarchical(
    Np,
    A_ca,
    B_ca,
    C_ca,
    D_ca,
    ar_model_params,
    U_LB,
    U_UB,
    COMFORTABLE_TEMP_MIN,
    COMFORTABLE_TEMP_MAX
):
    nx = A_ca.shape[0]
    nu = 1
    u = ca.SX.sym('u', Np)
    # Slack variables removed as they are no longer used
    x0 = ca.SX.sym('x0', nx)
    u_prev = ca.SX.sym('u_prev', 1)
    d = []
    for k in range(Np):
        d.append(ca.SX.sym(f'd_{k}', 10))
    prices = ca.SX.sym('prices', Np)
    p_hvac_prev = ca.SX.sym('p_hvac_prev', 1)
    hour_sin = ca.SX.sym('hour_sin', Np)
    hour_cos = ca.SX.sym('hour_cos', Np)
    day_sin = ca.SX.sym('day_sin', Np)
    day_cos = ca.SX.sym('day_cos', Np)
    Pi = ca.SX.sym('Pi', Np)
    rho = ca.SX.sym('rho', 1)
    lambda_bar = ca.SX.sym('lambda_bar', Np)
    x = [x0]
    y = []
    hvac_power = []
    intercept = ar_model_params['intercept']
    coefficients = ar_model_params['coefficients']

    g = []
    lbg = []
    ubg = []


    for k in range(Np):
        u_full = ca.SX.zeros(10)
        for i in range(10):
            if i == 1:
                u_full[i] = u[k]
            else:
                u_full[i] = d[k][i]
        x_next = ca.mtimes(A_ca, x[k]) + ca.mtimes(B_ca, u_full)
        x.append(x_next)
        y_k = ca.mtimes(C_ca, x[k]) + ca.mtimes(D_ca, u_full)
        y.append(y_k)
        
        # Hard constraint on zone temperature without slack variables
        g.append(y[k])
        lbg.append(COMFORTABLE_TEMP_MIN)
        ubg.append(COMFORTABLE_TEMP_MAX)

        temp_diff = y[k] - d[k][0]
        setpoint_diff = y[k] - u[k]
        total_solar_radiation = d[k][6] + d[k][7]
        p_hvac = intercept
        feat_order = [
            ('T_indoor', y[k]),
            ('T_outdoor_dry', d[k][0]),
            ('Single_setpoint', u[k]),
            ('T_outdoor_wet', d[k][2]),
            ('T_waterMains', d[k][3]),
            ('T_sky', d[k][4]),
            ('People_count', d[k][5]),
            ('Diffuse_solar_radiation', d[k][6]),
            ('Direct_solar_radiation', d[k][7]),
            ('Wind_speed', d[k][8]),
            ('Relative_humidity', d[k][9]),
            ('P_hvac_lag_1', p_hvac_prev if k == 0 else hvac_power[k-1]),
            ('hour_sin', hour_sin[k]),
            ('hour_cos', hour_cos[k]),
            ('day_of_week_sin', day_sin[k]),
            ('day_of_week_cos', day_cos[k]),
            ('temp_diff', temp_diff),
            ('setpoint_diff', setpoint_diff),
            ('total_solar_radiation', total_solar_radiation)
        ]
        for feat, val in feat_order:
            if feat in coefficients:
                p_hvac += coefficients[feat] * val
        p_hvac = ca.fmax(0, p_hvac)
        # g.append(p_hvac)
        # lbg.append(0)
        # ubg.append(BIG_NUMBER)
        hvac_power.append(p_hvac)

    cost_scale = 10.0
    obj = 0
    for k in range(Np):
        weight = 1.0 / (1.0 + 0.05 * k)

        # Energy cost term
        obj += cost_scale * weight * prices[k] * hvac_power[k] * (STEP_SIZE / 3600.0)

    # # Setpoint change penalty
    # obj += 0.001 * (u[0] - u_prev[0])**2
    # for k in range(1, Np):
    #     obj += 0.0001 * (u[k] - u[k-1])**2

    # obj += 0.1 * (u[0] - u_prev[0])**2
    # for k in range(1, Np):
    #     obj += 0.1 * (u[k] - u[k-1])**2

    # ADMM term
    admm_term = 0
    for k in range(Np):
        admm_term += lambda_bar[k] * (hvac_power[k] - Pi[k])
        admm_term += (rho[0]/2) * (hvac_power[k] - Pi[k])**2
    obj += admm_term


    dec_vars = u
    p = ca.vertcat(
        x0,
        u_prev,
        *d,
        prices,
        p_hvac_prev,
        hour_sin,
        hour_cos,
        day_sin,
        day_cos,
        Pi,
        lambda_bar,
        rho
    )
    nlp = {
        'x': dec_vars,
        'f': obj,
        'g': ca.vertcat(*g),
        'p': p
    }
    opts = {
        'print_time': 0,
        'verbose': False,
        'ipopt.max_iter': 500,
        'ipopt.print_level': 0,
        'ipopt.acceptable_tol': 1e-4,
        'ipopt.acceptable_obj_change_tol': 1e-4
    }
    solver = ca.nlpsol('mpc_solver', 'ipopt', nlp, opts)
    lbx = [U_LB] * Np
    ubx = [U_UB] * Np
    return {
        'solver': solver,
        'nx': nx,
        'nu': nu,
        'Np': Np,
        'lbx': lbx,
        'ubx': ubx,
        'lbg': lbg,
        'ubg': ubg
    }

# =============================================================================
# MPC Controller with ADMM
# =============================================================================
class MPCControllerWithADMM:
    def __init__(
        self,
        A,
        B,
        C,
        D,
        K,
        historical_data=None,
        Np=24,
        Ts=900,
        start_index=0,
        U_LB=19.0,
        U_UB=23.0,
        COMFORTABLE_TEMP_MIN=19.0,
        COMFORTABLE_TEMP_MAX=23.0,
        ar_model_path=None,
        hierarchical_mode=True
    ):
        self.A = A
        self.B = B
        self.C = C
        self.D = D
        self.Np = Np
        self.Ts = Ts
        self.historical_data = historical_data
        self.x_hat = np.zeros(A.shape[0])
        self.P_hat = np.eye(A.shape[0])
        self.u_previous = 0.0
        self.p_hvac_previous = 0.0
        self.current_step = start_index
        self.logger = logging.getLogger("mpc_controller")
        self.hierarchical_mode = hierarchical_mode
        process_noise = np.eye(A.shape[0]) * PROCESS_NOISE_SCALE
        measurement_noise = np.array([[MEASUREMENT_NOISE]])
        self.kf = KalmanFilter(
            transition_matrices=A,
            observation_matrices=C,
            observation_offsets=np.zeros(C.shape[0]),
            transition_offsets=np.zeros(A.shape[0]),
            transition_covariance=process_noise,
            observation_covariance=measurement_noise,
            initial_state_mean=np.zeros(A.shape[0]),
            initial_state_covariance=np.eye(A.shape[0])
        )
        self.A_ca = ca.DM(A)
        self.B_ca = ca.DM(B)
        self.C_ca = ca.DM(C)
        self.D_ca = ca.DM(D)
        self.U_LB = U_LB
        self.U_UB = U_UB
        self.COMFORTABLE_TEMP_MIN = COMFORTABLE_TEMP_MIN
        self.COMFORTABLE_TEMP_MAX = COMFORTABLE_TEMP_MAX

        if ar_model_path:
            self.ar_model_params = self.load_ar_model_parameters(ar_model_path)
        else:
            self.ar_model_params = {"intercept": 0.0, "coefficients": {}}

        if hierarchical_mode:
            self.qp = build_mpc_problem_qp_hierarchical(
                Np,
                self.A_ca,
                self.B_ca,
                self.C_ca,
                self.D_ca,
                self.ar_model_params,
                U_LB,
                U_UB,
                COMFORTABLE_TEMP_MIN,
                COMFORTABLE_TEMP_MAX
            )
        self.ar_power_predictions = []

    def load_ar_model_parameters(self, model_path):
        with open(model_path, 'r') as f:
            return json.load(f)

    def initialize_state(self, measurements=None, historical_data=None):
        if measurements is not None:
            self.x_hat = np.zeros(self.A.shape[0])
            self.P_hat = np.eye(self.A.shape[0])
            y_meas = measurements['zone_temp']
            u_vector = np.array([
                measurements['T_outdoor_dry'],
                0.0,
                measurements['T_outdoor_wet'],
                measurements['T_waterMains'],
                measurements['T_sky'],
                measurements['People_count'],
                measurements['Diffuse_solar_radiation'],
                measurements['Direct_solar_radiation'],
                measurements['Wind_speed'],
                measurements['Relative_humidity']
            ], dtype=float)
            self.x_hat, self.P_hat = self.kf.filter_update(
                self.x_hat,
                self.P_hat,
                observation=y_meas,
                transition_offset=self.B @ u_vector,
                observation_offset=self.D @ u_vector
            )
        elif historical_data is not None:
            self.x_hat = self.estimate_initial_state_from_data(historical_data)
            self.P_hat = np.eye(self.A.shape[0])
        else:
            self.x_hat = np.zeros(self.A.shape[0])
            self.P_hat = np.eye(self.A.shape[0])

    def estimate_initial_state_from_data(self, data, N_init=10):
        A_est, B_est, C_est, D_est = self.A, self.B, self.C, self.D
        U = data[[
            'T_outdoor_dry',
            'Single_setpoint',
            'T_outdoor_wet',
            'T_waterMains',
            'T_sky',
            'People_count',
            'Diffuse_solar_radiation',
            'Direct_solar_radiation',
            'Wind_speed',
            'Relative_humidity'
        ]].values[:N_init]
        Y = data['LIVING SPACE:Zone Mean Air Temperature [C](TimeStep)'].values[:N_init]
        M_rows = []
        r_vec = []
        for k in range(N_init):
            A_pow = np.linalg.matrix_power(A_est, k)
            M_rows.append(C_est @ A_pow)
            s = 0.0
            for j in range(k):
                s += (C_est @ np.linalg.matrix_power(A_est, k - 1 - j) @ B_est @ U[j]).item() + \
                     (D_est @ U[j]).item()
            r_vec.append(Y[k] - s)
        M = np.vstack(M_rows)
        r = np.array(r_vec)
        x0_est, _, _, _ = np.linalg.lstsq(M, r, rcond=None)
        return x0_est.reshape(-1)

    def solve_local_admm_step(self, measurements, current_time, Pi, lambda_bar, global_rho=RHO):
        self.current_step += 1
        u_vector = np.array([
            measurements['T_outdoor_dry'],
            self.u_previous,
            measurements['T_outdoor_wet'],
            measurements['T_waterMains'],
            measurements['T_sky'],
            measurements['People_count'],
            measurements['Diffuse_solar_radiation'],
            measurements['Direct_solar_radiation'],
            measurements['Wind_speed'],
            measurements['Relative_humidity']
        ], dtype=float)
        y_meas = measurements['zone_temp']
        self.x_hat, self.P_hat = self.kf.filter_update(
            self.x_hat,
            self.P_hat,
            observation=y_meas,
            transition_offset=self.B @ u_vector,
            observation_offset=self.D @ u_vector
        )

        if self.historical_data is not None:
            d_horizon = build_disturbance_horizon_from_csv(
                self.historical_data,
                self.current_step,
                self.Np
            )
        else:
            repeated = np.array([
                measurements['T_outdoor_dry'],
                0.0,
                measurements['T_outdoor_wet'],
                measurements['T_waterMains'],
                measurements['T_sky'],
                measurements['People_count'],
                measurements['Diffuse_solar_radiation'],
                measurements['Direct_solar_radiation'],
                measurements['Wind_speed'],
                measurements['Relative_humidity']
            ]).reshape(-1, 1)
            d_horizon = np.tile(repeated, self.Np)

        price_horizon = np.zeros(self.Np)
        for i in range(self.Np):
            price_horizon[i] = get_price_rate(current_time + timedelta(seconds=self.Ts * i))

        hour_sin = np.zeros(self.Np)
        hour_cos = np.zeros(self.Np)
        day_sin = np.zeros(self.Np)
        day_cos = np.zeros(self.Np)
        for i in range(self.Np):
            ft = current_time + timedelta(seconds=self.Ts * i)
            h = ft.hour
            dow = ft.weekday()
            hour_sin[i] = np.sin(2 * np.pi * h / 24)
            hour_cos[i] = np.cos(2 * np.pi * h / 24)
            day_sin[i] = np.sin(2 * np.pi * dow / 7)
            day_cos[i] = np.cos(2 * np.pi * dow / 7)

        p_vec = [self.x_hat.flatten(), np.array([self.u_previous])]
        for i in range(self.Np):
            p_vec.append(d_horizon[:, i])
        p_vec.extend([
            price_horizon,
            np.array([self.p_hvac_previous]),
            hour_sin,
            hour_cos,
            day_sin,
            day_cos,
            Pi,
            lambda_bar,
            np.array([global_rho])
        ])
        p = np.concatenate([np.atleast_1d(p_item).flatten() for p_item in p_vec])

        x0_guess = np.ones(self.Np) * self.u_previous
        # slack_guess = np.zeros(2 * self.Np)
        # x0_guess = np.concatenate([x0_guess, slack_guess])

        try:
            sol = self.qp['solver'](
                p=p,
                lbx=self.qp['lbx'],
                ubx=self.qp['ubx'],
                lbg=self.qp['lbg'],
                ubg=self.qp['ubg'],
                x0=x0_guess
            )
            sol_x = sol['x'].full().flatten()
            u_opt = sol_x[:self.Np]
            u_mpc = float(u_opt[0])
            self.u_previous = u_mpc

            power_predictions = []
            for k, setpoint in enumerate(u_opt):
                future_time = current_time + timedelta(seconds=self.Ts * k)
                hour = future_time.hour
                dow = future_time.weekday()
                hour_sin_k = np.sin(2 * np.pi * hour / 24)
                hour_cos_k = np.cos(2 * np.pi * hour / 24)
                day_sin_k = np.sin(2 * np.pi * dow / 7)
                day_cos_k = np.cos(2 * np.pi * dow / 7)
                temp_diff = measurements['zone_temp'] - measurements['T_outdoor_dry']
                setpoint_diff = measurements['zone_temp'] - setpoint
                total_solar_radiation = measurements['Diffuse_solar_radiation'] + \
                                        measurements['Direct_solar_radiation']
                p_hvac = self.ar_model_params['intercept']
                feats = {
                    'T_indoor': measurements['zone_temp'],
                    'T_outdoor_dry': measurements['T_outdoor_dry'],
                    'Single_setpoint': setpoint,
                    'T_outdoor_wet': measurements['T_outdoor_wet'],
                    'T_waterMains': measurements['T_waterMains'],
                    'T_sky': measurements['T_sky'],
                    'People_count': measurements['People_count'],
                    'Diffuse_solar_radiation': measurements['Diffuse_solar_radiation'],
                    'Direct_solar_radiation': measurements['Direct_solar_radiation'],
                    'Wind_speed': measurements['Wind_speed'],
                    'Relative_humidity': measurements['Relative_humidity'],
                    'P_hvac_lag_1': self.p_hvac_previous if k == 0 else power_predictions[-1],
                    'hour_sin': hour_sin_k,
                    'hour_cos': hour_cos_k,
                    'day_of_week_sin': day_sin_k,
                    'day_of_week_cos': day_cos_k,
                    'temp_diff': temp_diff,
                    'setpoint_diff': setpoint_diff,
                    'total_solar_radiation': total_solar_radiation
                }
                for f, v in feats.items():
                    if f in self.ar_model_params['coefficients']:
                        p_hvac += self.ar_model_params['coefficients'][f] * v
                p_hvac = max(0, p_hvac)
                power_predictions.append(p_hvac)

            self.p_hvac_previous = power_predictions[0]
            self.ar_power_predictions.append(power_predictions[0])
            measured_hvac_power = measurements['P_hvac_heating'] + abs(measurements['P_hvac_cooling'])

            self.logger.info(
                f"Time: {current_time}, Zone Temp: {y_meas:.2f}°C, Setpoint: {u_mpc:.2f}°C, "
                f"Price: ${price_horizon[0]:.3f}/kWh, AR Power[0]: {power_predictions[0]:.2f} kW, "
                f"Last measured Power: {measured_hvac_power:.2f} kW"
            )
            return u_mpc, u_opt, power_predictions[0], power_predictions

        except Exception as e:
            self.logger.error(f"MPC solver error: {str(e)}")
            return self.u_previous, np.ones(self.Np) * self.u_previous, self.p_hvac_previous, [self.p_hvac_previous] * self.Np

# =============================================================================
# Historical Data Loading 
# =============================================================================
def load_historical_data(input_file, output_file, hvac_output_file=None):
    input_data = pd.read_csv(input_file)
    output_data = pd.read_csv(output_file)
    has_hvac_data = False
    if hvac_output_file:
        try:
            hvac_data = pd.read_csv(hvac_output_file)
            has_hvac_data = 'P_hvac' in hvac_data.columns
        except Exception as e:
            print(f"Error loading HVAC data file: {e}")
            hvac_data = None
    h = {
        'times': [],
        'zone_temp': [],
        'outdoor_temp': [],
        'hvac_power': [],
        'heating_setpoint': [],
        'cooling_setpoint': []
    }
    days_offset = (SIMULATION_START_DATETIME - datetime(2018, 1, 1, 0, 0, 0)).days
    hours_offset = SIMULATION_START_DATETIME.hour
    minutes_offset = SIMULATION_START_DATETIME.minute
    steps_per_day = 24 * 4
    start_index = days_offset * steps_per_day + hours_offset * 4 + minutes_offset // 15
    if start_index >= len(input_data):
        start_index = 0
    start_time_hist = SIMULATION_START_DATETIME
    for i in range(start_index, len(input_data)):
        rel_idx = i - start_index
        t = start_time_hist + timedelta(seconds=rel_idx * STEP_SIZE)
        h['times'].append(t)
        h['zone_temp'].append(output_data['LIVING SPACE:Zone Mean Air Temperature [C](TimeStep)'].iloc[i])
        h['outdoor_temp'].append(input_data['T_outdoor_dry'].iloc[i])
        if has_hvac_data and hvac_data is not None and i < len(hvac_data):
            h['hvac_power'].append(hvac_data['P_hvac'].iloc[i])
        else:
            temp_diff = abs(
                output_data['LIVING SPACE:Zone Mean Air Temperature [C](TimeStep)'].iloc[i] -
                input_data['T_outdoor_dry'].iloc[i]
            )
            h['hvac_power'].append(max(0, 0.5 + 0.1 * temp_diff))
        h['heating_setpoint'].append(21.0)
        h['cooling_setpoint'].append(21.0)
    return h

# =============================================================================
# Plotting
# =============================================================================
def plot_admm_mpc_results(results, metrics, save_path=None):
    """
    Generate consolidated plots for ADMM MPC simulation results with historical comparison.
    
    Parameters:
        results (dict): Dictionary containing simulation results and historical data.
        metrics (dict): Dictionary containing performance metrics.
        save_path (str, optional): File path (including filename and extension) to save the figure.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import logging

    logger = logging.getLogger("mpc_controller")
    times = results['times']

    # Extract building keys (assumed to be in the format 'y_sim_storeX' where X is a number)
    building_keys = [key for key in results.keys() if key.startswith('y_sim_store') and key[len('y_sim_store'):].isdigit()]
    building_keys.sort(key=lambda k: int(k[len('y_sim_store'):]))
    n_buildings = len(building_keys)

    # Check for historical data - more robust check that looks for any building's historical data
    has_historical = False
    hist_power_keys = []
    for i in range(1, n_buildings + 1):
        hist_key = f'historical_power{i}'
        if hist_key in results:
            has_historical = True
            hist_power_keys.append(hist_key)
    
    # Total number of subplot rows: one per building plus four additional rows for system power, 
    # historical comparison, price, and ADMM residuals
    n_rows = n_buildings + (4 if has_historical else 3)

    # Create subplot specifications: enable secondary y-axis for building plots
    specs = []
    for i in range(n_rows):
        if i < n_buildings:
            specs.append([{"secondary_y": True}])
        else:
            specs.append([{}])

    # Define subplot titles
    subplot_titles = []
    for key in building_keys:
        building_id = key[len('y_sim_store'):]
        subplot_titles.append(f"Building {building_id}")
    
    if has_historical:
        subplot_titles.extend(["System Power vs Limit", "Historical vs Simulated Power", "Electricity Price", "ADMM Residuals"])
    else:
        subplot_titles.extend(["System Power vs Limit", "Electricity Price", "ADMM Residuals"])

    # Create the figure with subplots
    fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                        specs=specs, subplot_titles=subplot_titles)
    fig.update_layout(title_text="ADMM MPC Building Control Results", showlegend=True)

    # Plot building data (first n_buildings rows) with dual y-axes
    for idx, key in enumerate(building_keys):
        row = idx + 1
        zone_temp = results[key]
        setpoint_key = key.replace("y_sim_store", "u_sim_store")
        power_key = key.replace("y_sim_store", "power_store")
        if setpoint_key in results and power_key in results:
            setpoint = results[setpoint_key]
            power = results[power_key]
            # Plot zone temperature and setpoint on the primary y-axis
            fig.add_trace(
                go.Scatter(x=times, y=zone_temp, name=f"B{key[len('y_sim_store'):]} Zone Temp", line=dict(color='red')),
                row=row, col=1, secondary_y=False
            )
            fig.add_trace(
                go.Scatter(x=times, y=setpoint, name=f"B{key[len('y_sim_store'):]} Setpoint", line=dict(color='blue', dash='dash')),
                row=row, col=1, secondary_y=False
            )
            # Plot power on the secondary y-axis
            fig.add_trace(
                go.Scatter(x=times, y=power, name=f"B{key[len('y_sim_store'):]} Power", line=dict(color='green')),
                row=row, col=1, secondary_y=True
            )
            
            # Add historical power data if available for this building
            bldg_num = int(key[len('y_sim_store'):])
            hist_power_key = f'historical_power{bldg_num}'
            if hist_power_key in results and len(results[hist_power_key]) > 0:
                # Ensure the historical data is the same length as the simulation data
                hist_power = results[hist_power_key]
                if len(hist_power) > len(times):
                    hist_power = hist_power[:len(times)]
                elif len(hist_power) < len(times):
                    # Pad with last value if shorter
                    last_val = hist_power[-1] if hist_power else 0
                    hist_power = hist_power + [last_val] * (len(times) - len(hist_power))
                
                fig.add_trace(
                    go.Scatter(
                        x=times, 
                        y=hist_power, 
                        name=f"B{bldg_num} Hist. Power", 
                        line=dict(color='darkgreen', dash='dot')
                    ),
                    row=row, col=1, secondary_y=True
                )
            
            fig.update_yaxes(title_text="Temperature (°C)", row=row, col=1, secondary_y=False)
            fig.update_yaxes(title_text="Power (kW)", row=row, col=1, secondary_y=True)
        else:
            logger.warning(f"Missing setpoint or power data for building key {key}.")

    # Plot System Power vs Limit (row n_buildings + 1)
    row = n_buildings + 1
    total_power = np.zeros(len(times))
    for key in building_keys:
        power_key = key.replace("y_sim_store", "power_store")
        if power_key in results:
            total_power += np.array(results[power_key])
    fig.add_trace(
        go.Scatter(x=times, y=total_power, name="Total Power", line=dict(color='blue')),
        row=row, col=1
    )
    power_limit_line = [P_MAX] * len(times)
    fig.add_trace(
        go.Scatter(x=times, y=power_limit_line, name="Power Limit", line=dict(color='red', dash='dash')),
        row=row, col=1
    )
    fig.update_yaxes(title_text="Power (kW)", row=row, col=1)

    # Plot Historical vs Simulated Power Comparison (row n_buildings + 2, only if historical data exists)
    if has_historical:
        row = n_buildings + 2
        
        # Calculate total historical power (sum of all available historical power data)
        total_hist_power = np.zeros(len(times))
        for hist_key in hist_power_keys:
            if hist_key in results and len(results[hist_key]) > 0:
                hist_data = results[hist_key]
                # Make sure the historical data is the same length as simulation data
                if len(hist_data) > len(times):
                    hist_data = hist_data[:len(times)]
                elif len(hist_data) < len(times):
                    last_val = hist_data[-1] if hist_data else 0
                    hist_data = hist_data + [last_val] * (len(times) - len(hist_data))
                total_hist_power += np.array(hist_data)
        
        # Add traces for historical and simulated total power
        fig.add_trace(
            go.Scatter(x=times, y=total_power, name="Total Simulated Power", line=dict(color='blue')),
            row=row, col=1
        )
        fig.add_trace(
            go.Scatter(x=times, y=total_hist_power, name="Total Historical Power", line=dict(color='purple')),
            row=row, col=1
        )
        fig.update_yaxes(title_text="Power (kW)", row=row, col=1)
        
        # Plot Electricity Price (row n_buildings + 3 if historical data exists)
        price_row = row + 1
    else:
        # Plot Electricity Price (row n_buildings + 2 if no historical data)
        price_row = row + 1
    
    # Plot Electricity Price
    price_data = [get_price_rate(t) for t in times]
    fig.add_trace(
        go.Scatter(x=times, y=price_data, name="Electricity Price", line=dict(color='purple')),
        row=price_row, col=1
    )
    fig.update_yaxes(title_text="Price ($/kWh)", row=price_row, col=1)

    # Plot ADMM Residuals (last row)
    residual_row = price_row + 1
    if 'primal_residuals' in results and 'dual_residuals' in results:
        fig.add_trace(
            go.Scatter(x=times, y=results['primal_residuals'], name="Primal Residual", line=dict(color='blue')),
            row=residual_row, col=1
        )
        fig.add_trace(
            go.Scatter(x=times, y=results['dual_residuals'], name="Dual Residual", line=dict(color='red')),
            row=residual_row, col=1
        )
        fig.update_yaxes(title_text="Residuals", row=residual_row, col=1, type="log")
    else:
        logger.error("Missing ADMM residuals in results for plotting.")

    # Final layout adjustments
    fig.update_xaxes(title_text="Time", row=n_rows, col=1)
    fig.update_layout(
        height=250 * n_rows,
        width=1000,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
        hovermode="x unified"
    )

    # Save the figure if a save path is provided
    if save_path:
        try:
            fig.write_image(save_path)
            logger.info(f"Figure saved to {save_path}")
        except Exception as e:
            logger.error(f"Error saving figure: {str(e)}")

    fig.show()
    
    # -------------------------------------------------------------------------
    # Log summary metrics
    # -------------------------------------------------------------------------
    logger.info("----- SIMULATION RESULTS SUMMARY -----")
    logger.info(f"Peak System Power: {metrics.get('peak_power', 0):.2f} kW")
    logger.info(f"Power Limit Violations: {metrics.get('power_violation_rate', 0):.2f}%")
    
    if 'admm_convergence_rate' in metrics:
        logger.info(f"ADMM Convergence Rate: {metrics['admm_convergence_rate']:.2f}%")
        logger.info(f"ADMM Avg Iterations: {metrics['admm_avg_iterations']:.1f}")
    
    logger.info("\nBuilding Performance Summary:")
    # Create a formatted table structure for logs
    headers = ["Building", "Comfort Viol. (%)", "Track. Error (°C)", "Energy (kWh)", "Cost ($)"]
    logger.info("  ".join(headers))
    logger.info("-" * 80)
    
    # Extract building IDs from metrics keys
    building_ids = sorted(list(set([
        key.split('_')[0][len('Building'):] 
        for key in metrics.keys()
        if key.startswith('Building') and '_' in key
    ])))
    
    for b in building_ids:
        prefix = f"Building{b}"
        values = [
            f"B{b}".ljust(10),
            f"{metrics.get(prefix+'_comfort_violation_rate', 0):.2f}%".ljust(18),
            f"{metrics.get(prefix+'_avg_tracking_error', 0):.2f}".ljust(18),
            f"{metrics.get(prefix+'_total_energy', 0):.2f}".ljust(14),
            f"${metrics.get(prefix+'_total_cost', 0):.2f}"
        ]
        logger.info("  ".join(values))
    
    # If historical data is available, calculate and log comparison metrics
    if has_historical:
        # Calculate total historical power properly accounting for all buildings
        total_hist_power = np.zeros(len(times))
        available_hist_buildings = []
        for i in range(1, n_buildings + 1):
            hist_power_key = f'historical_power{i}'
            if hist_power_key in results and len(results[hist_power_key]) > 0:
                available_hist_buildings.append(i)
                hist_data = results[hist_power_key]
                if len(hist_data) > len(times):
                    hist_data = hist_data[:len(times)]
                elif len(hist_data) < len(times):
                    last_val = hist_data[-1] if hist_data else 0
                    hist_data = hist_data + [last_val] * (len(times) - len(hist_data))
                total_hist_power += np.array(hist_data)
        
        # Calculate total simulated power for the same buildings 
        # that have historical data for fair comparison
        total_power = np.zeros(len(times))
        for i in available_hist_buildings:
            power_key = f'power_store{i}'
            if power_key in results:
                total_power += np.array(results[power_key])
        
        peak_hist_power = max(total_hist_power) if len(total_hist_power) > 0 else 0
        avg_hist_power = np.mean(total_hist_power) if len(total_hist_power) > 0 else 0
        peak_sim_power = max(total_power) if len(total_power) > 0 else 0
        avg_sim_power = np.mean(total_power) if len(total_power) > 0 else 0
        peak_reduction = ((peak_hist_power - peak_sim_power) / peak_hist_power * 100) if peak_hist_power > 0 else 0
        avg_reduction = ((avg_hist_power - avg_sim_power) / avg_hist_power * 100) if avg_hist_power > 0 else 0
        
        logger.info("\nHistorical vs. Simulated Power Comparison:")
        logger.info(f"Buildings with historical data: {', '.join([str(b) for b in available_hist_buildings])}")
        logger.info(f"Historical Peak Power: {peak_hist_power:.2f} kW")
        logger.info(f"Simulated Peak Power: {peak_sim_power:.2f} kW")
        logger.info(f"Peak Power Reduction: {peak_reduction:.2f}%")
        logger.info(f"Historical Avg Power: {avg_hist_power:.2f} kW")
        logger.info(f"Simulated Avg Power: {avg_sim_power:.2f} kW")
        logger.info(f"Avg Power Reduction: {avg_reduction:.2f}%")
    
    logger.info("----- END OF SUMMARY -----\n")

# =============================================================================
# Performance Metrics
# =============================================================================
def compute_performance_metrics(results):
    times = results['times']
    buildings = set()
    for key in results.keys():
        if key.startswith('y_sim_store_'):
            # Extract the building name after the last underscore.
            bldg_id = key.split('_')[-1]
            buildings.add(bldg_id)
    buildings = sorted(list(buildings))

    bldg_constraints = {
        '2721': (BLDG1_COMFORTABLE_TEMP_MIN, BLDG1_COMFORTABLE_TEMP_MAX),
        '2722': (BLDG2_COMFORTABLE_TEMP_MIN, BLDG2_COMFORTABLE_TEMP_MAX),
        '202': (BLDG3_COMFORTABLE_TEMP_MIN, BLDG3_COMFORTABLE_TEMP_MAX),
        '57693': (BLDG4_COMFORTABLE_TEMP_MIN, BLDG4_COMFORTABLE_TEMP_MAX)
    }
    power_stores = []
    total_power = [0.0]*len(times)
    for b in buildings:
        power_store = results[f'power_store{b}']
        power_stores.append(power_store)
        for i in range(len(times)):
            total_power[i] += power_store[i]

    admm_metrics = {}
    if all(k in results for k in ['admm_converged','admm_iterations','primal_residuals','dual_residuals']):
        admm_converged = results['admm_converged']
        admm_iterations = results['admm_iterations']
        primal_residuals = results['primal_residuals']
        dual_residuals = results['dual_residuals']
        try:
            convergence_rate = (sum(admm_converged) / len(admm_converged) * 100) if admm_converged else 0
            avg_iterations = (sum(admm_iterations) / len(admm_iterations)) if admm_iterations else 0
            avg_primal_residual = (sum(primal_residuals) / len(primal_residuals)) if primal_residuals else float('inf')
            avg_dual_residual = (sum(dual_residuals) / len(dual_residuals)) if dual_residuals else float('inf')
            max_primal_residual = max(primal_residuals) if primal_residuals else float('inf')
            max_dual_residual = max(dual_residuals) if dual_residuals else float('inf')
            admm_metrics = {
                'admm_convergence_rate': convergence_rate,
                'admm_avg_iterations': avg_iterations,
                'admm_avg_primal_residual': avg_primal_residual,
                'admm_avg_dual_residual': avg_dual_residual,
                'admm_max_primal_residual': max_primal_residual,
                'admm_max_dual_residual': max_dual_residual,
                'admm_total_iterations': sum(admm_iterations),
                'admm_converged_steps': sum(admm_converged),
                'admm_total_steps': len(admm_converged)
            }
        except Exception as e:
            logger = logging.getLogger("mpc_controller")
            logger.warning(f"Error computing ADMM metrics: {str(e)}")

    building_metrics = {}
    for b in buildings:
        y_store = results[f'y_sim_store{b}']
        u_store = results[f'u_sim_store{b}']
        p_store = results[f'power_store{b}']
        T_min, T_max = bldg_constraints[b]

        violations = 0
        tolerance = 0.1  # Small tolerance for floating-point errors
        for val in y_store:
            if val < (T_min - tolerance) or val > (T_max + tolerance):
                violations += 1
        comfort_violation_rate = (violations / len(y_store) * 100) if len(y_store) > 0 else 0

        tracking_err = [abs(y - sp) for y, sp in zip(y_store, u_store)]
        avg_tracking_error = sum(tracking_err)/len(tracking_err) if len(tracking_err) > 0 else 0

        total_energy = 0
        total_cost = 0
        for i, t in enumerate(times):
            price = get_price_rate(t)
            energy = p_store[i]*(STEP_SIZE/3600.0)
            total_energy += energy
            total_cost += price*energy

        building_metrics[b] = {
            'comfort_violation_rate': comfort_violation_rate,
            'avg_tracking_error': avg_tracking_error,
            'total_energy': total_energy,
            'total_cost': total_cost
        }

    peak_power = max(total_power) if len(total_power) > 0 else 0
    power_violations = sum(1 for p in total_power if p > P_MAX)
    power_violation_rate = (power_violations / len(total_power) * 100) if len(total_power) > 0 else 0

    metrics = {
        'peak_power': peak_power,
        'power_violation_rate': power_violation_rate
    }
    metrics.update(admm_metrics)
    for b, vals in building_metrics.items():
        prefix = f'Building{b}'
        metrics[f'{prefix}_comfort_violation_rate'] = vals['comfort_violation_rate']
        metrics[f'{prefix}_avg_tracking_error'] = vals['avg_tracking_error']
        metrics[f'{prefix}_total_energy'] = vals['total_energy']
        metrics[f'{prefix}_total_cost'] = vals['total_cost']
    return metrics

def save_simulation_results_to_csv(results, output_dir=None):
    if output_dir is None:
        output_dir = os.getcwd()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(output_dir, exist_ok=True)
    logger = logging.getLogger("mpc_controller")

    buildings = []
    for key in results.keys():
        if key.startswith('y_sim_store'):
            buildings.append(key[-1])
    buildings = sorted(list(set(buildings)), key=lambda x: int(x))

    building_data = pd.DataFrame()
    building_data['timestamp'] = [t.strftime("%Y-%m-%d %H:%M:%S") for t in results['times']]

    for b in buildings:
        building_data[f'zone_temp_bldg{b}'] = results[f'y_sim_store{b}']
        building_data[f'setpoint_bldg{b}'] = results[f'u_sim_store{b}']
        building_data[f'power_bldg{b}'] = results[f'power_store{b}']

    building_csv_path = os.path.join(output_dir, f"building_data_{timestamp}.csv")
    building_data.to_csv(building_csv_path, index=False)
    logger.info(f"Saved building data to {building_csv_path}")

    admm_csv_path = None
    if all(k in results for k in ['admm_iterations', 'primal_residuals', 'dual_residuals']):
        admm_data = pd.DataFrame()
        admm_data['timestamp'] = [t.strftime("%Y-%m-%d %H:%M:%S") for t in results['times']]
        admm_data['primal_residual'] = results['primal_residuals']
        admm_data['dual_residual'] = results['dual_residuals']
        if 'rho_values' in results:
            admm_data['rho'] = results['rho_values']
        admm_csv_path = os.path.join(output_dir, f"admm_residuals_{timestamp}.csv")
        admm_data.to_csv(admm_csv_path, index=False)
        logger.info(f"Saved ADMM residuals and parameters to {admm_csv_path}")

    # =============================================================================
    # New: Save per-iteration residuals for each time step
    # =============================================================================
    if 'all_primal_residuals' in results and 'all_dual_residuals' in results:
        iteration_rows = []
        # 'all_primal_residuals' and 'all_dual_residuals' are lists over time steps;
        # each entry is a list of residuals over ADMM iterations.
        # So all_primal_residuals[time_step] = [primal_res_iter_1, ..., primal_res_iter_N]
        # Similarly for all_dual_residuals.
        # The length of these sublists can differ by time step if early convergence stops ADMM.
        for t_idx, (primal_list, dual_list) in enumerate(zip(results['all_primal_residuals'], 
                                                            results['all_dual_residuals'])):
            # Combine iteration data
            iteration_count = len(primal_list)
            for i_idx in range(iteration_count):
                iteration_rows.append({
                    "time_step": t_idx,
                    "admm_iteration": i_idx+1,
                    "primal_residual": primal_list[i_idx],
                    "dual_residual": dual_list[i_idx]
                })
        iteration_df = pd.DataFrame(iteration_rows)
        iteration_csv_path = os.path.join(output_dir, f"admm_per_iteration_residuals_{timestamp}.csv")
        iteration_df.to_csv(iteration_csv_path, index=False)
        logger.info(f"Saved per-iteration ADMM residuals to {iteration_csv_path}")

    return {
        "building_csv": building_csv_path,
        "admm_csv": admm_csv_path
    }

# =============================================================================
# Run Hierarchical Encrypted ADMM Simulation
# =============================================================================
def run_hierarchical_encrypted_admm_simulation(dso, coordinator, agents, controllers, sims, hvac_files=None, building_names=None):
    logger = logging.getLogger("mpc_controller")
    if hvac_files is None:
        hvac_files = [None]*len(controllers)

    # Use building names if provided, otherwise use numeric indices
    if building_names is None:
        building_names = {i+1: str(i+1) for i in range(len(controllers))}
    
    times = []
    y_sim_store = {i+1: [] for i in range(len(controllers))}
    u_sim_store = {i+1: [] for i in range(len(controllers))}
    power_store = {i+1: [] for i in range(len(controllers))}

    admm_iterations_per_step = []
    admm_converged_per_step = []
    primal_residuals = []
    dual_residuals = []
    rho_values = []

    # New: store all iteration residuals for each time step
    all_primal_residuals = []
    all_dual_residuals = []

    time_current = SIMULATION_START_DATETIME
    sim_duration = SIMULATION_DURATION_DAYS * 24 * 3600
    n_sim_steps = int(sim_duration / STEP_SIZE)

    hvac_data_list = []
    for path in hvac_files:
        if path is not None and path.strip():
            try:
                hvac_data_list.append(pd.read_csv(path))
            except Exception as e:
                logger.error(f"Error loading HVAC data file {path}: {str(e)}")
                hvac_data_list.append(None)
        else:
            hvac_data_list.append(None)

    for step in range(n_sim_steps):
        measurements_all = []
        for sim in sims:
            if sim is not None:
                meas = sim.get_fmu_measurements()
                if meas is None:
                    measurements_all.append(None)
                else:
                    measurements_all.append(meas)
            else:
                measurements_all.append({
                    'T_outdoor_dry': 20.0,
                    'T_outdoor_wet': 18.0,
                    'T_waterMains': 15.0,
                    'T_sky': 10.0,
                    'People_count': 2.0,
                    'Diffuse_solar_radiation': 0.0,
                    'Direct_solar_radiation': 0.0,
                    'Wind_speed': 0.5,
                    'Relative_humidity': 50.0,
                    'zone_temp': 20.0,
                    'Single_setpoint': 20.0,
                    'P_hvac_heating': 0.0,
                    'P_hvac_cooling': 0.0
                })

        if any(m is None for m in measurements_all):
            break

        z_prev = {i: np.zeros(coordinator.Np) for i in range(len(controllers))}
        z_new = {i: np.zeros(coordinator.Np) for i in range(len(controllers))}
        converged = False
        primal_res = 0
        dual_res = 0

        # For storing iteration-level primal and dual residuals at this time step
        time_step_primal_list = []
        time_step_dual_list = []

        for admm_iter in range(coordinator.max_iterations):
            for i in range(len(controllers)):
                z_prev[i] = z_new[i].copy()

            Pi, lambda_bar = coordinator.broadcast_guidance()
            setpoints = []
            setpoint_trajectories = []
            powers = []
            power_trajectories = []

            for i, controller in enumerate(controllers):
                sp, sp_traj, pw, pw_traj = controller.solve_local_admm_step(
                    measurements_all[i],
                    time_current,
                    Pi,
                    lambda_bar,
                    coordinator.rho
                )
                setpoints.append(sp)
                setpoint_trajectories.append(sp_traj)
                powers.append(pw)
                power_trajectories.append(pw_traj)
                z_new[i] = np.array(pw_traj)

            permutation = list(range(len(agents)))
            random.shuffle(permutation)
            enc_sum_horizon = perform_random_chain_summation(agents, power_trajectories, permutation)
            coordinator.solve_central_step(enc_sum_horizon, current_iter=admm_iter, max_iter=coordinator.max_iterations)

            if admm_iter > 0:
                total_power_step = sum(z_new[i] for i in range(len(controllers)))
                constraint_violation = np.maximum(0, total_power_step - coordinator.power_limit)
                primal_res = np.max(constraint_violation)
                dual_res = coordinator.rho * np.linalg.norm(coordinator.a_bar - coordinator.a_bar_prev)
                # coordinator.update_rho(primal_res, dual_res)
                
            # Store the iteration-level residuals for this time step
            time_step_primal_list.append(primal_res)
            time_step_dual_list.append(dual_res)

            if admm_iter > 0 and coordinator.check_convergence(z_new, z_prev):
                converged = True
                logger.info(f"Time {time_current}: ADMM converged after {admm_iter+1} iterations")
                break

        # log when ADMM does not converge
        if not converged:
            logger.info(f"Time {time_current}: ADMM did not converge after {coordinator.max_iterations} iterations")
            
        # After finishing all iterations for this time step, store the final iteration count etc.
        admm_iterations_per_step.append(admm_iter + 1)
        admm_converged_per_step.append(converged)
        primal_residuals.append(primal_res if admm_iter >= 0 else 0)
        dual_residuals.append(dual_res if admm_iter >= 0 else 0)
        rho_values.append(coordinator.rho)

        # Append the full iteration-level logs for this time step
        all_primal_residuals.append(time_step_primal_list)
        all_dual_residuals.append(time_step_dual_list)

        for i, sim in enumerate(sims):
            if sim is not None:
                sim.apply_control(setpoints[i])
    
        times.append(time_current)
        # Store results by index and by building name
        for i in range(len(controllers)):
            bldg_num = i+1  # Numeric key (1, 2, 3, 4)
            bldg_name = building_names[bldg_num]  # String key ("2721", "2722", etc.)
            y_sim_store[bldg_num].append(measurements_all[i]['zone_temp'])
            u_sim_store[bldg_num].append(setpoints[i])
            measured_power = measurements_all[i]['P_hvac_heating'] + abs(measurements_all[i]['P_hvac_cooling'])
            power_store[bldg_num].append(measured_power)

        stepped = True
        for sim in sims:
            if sim is not None:
                if not sim.step():
                    stepped = False
        if not stepped:
            break

        time_current += timedelta(seconds=STEP_SIZE)

    for sim in sims:
        if sim is not None:
            sim.terminate()
    results = {
        'times': times,
        'admm_iterations': admm_iterations_per_step,
        'admm_converged': admm_converged_per_step,
        'primal_residuals': primal_residuals,
        'dual_residuals': dual_residuals,
        'rho_values': rho_values,
        'all_primal_residuals': all_primal_residuals,
        'all_dual_residuals': all_dual_residuals
    }
    # Add both numeric and named identifiers to results
    for i in range(len(controllers)):
        bldg_num = i+1
        bldg_name = building_names[bldg_num]
        # Store with numeric index (for compatibility)
        results[f'y_sim_store{bldg_num}'] = y_sim_store[bldg_num]
        results[f'u_sim_store{bldg_num}'] = u_sim_store[bldg_num]
        results[f'power_store{bldg_num}'] = power_store[bldg_num]
        # # Also store with building name
        # results[f'y_sim_store_{bldg_name}'] = y_sim_store[bldg_num]
        # results[f'u_sim_store_{bldg_name}'] = u_sim_store[bldg_num]
        # results[f'power_store_{bldg_name}'] = power_store[bldg_num]
        # results[f'power_store{bldg_name}'] = power_store[bldg_num]


    if len(times) > 0:
        hist_times = times.copy()
        
        # Process all hvac files, not just the first two
        for i, hvac_data in enumerate(hvac_data_list):
            bldg_num = i + 1
            if hvac_data is not None and 'P_hvac' in hvac_data.columns:
                hist_power = []
                for j in range(len(times)):
                    idx = j % len(hvac_data) if len(hvac_data) > 0 else 0
                    hist_power.append(hvac_data['P_hvac'].iloc[idx])
                results[f'historical_power{bldg_num}'] = hist_power
        
        results['historical_times'] = hist_times

    return results

# =============================================================================
# Main Function
# =============================================================================
def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"privacy_preserving_encrypted_admm_mpc_{timestamp}.log"
    current_dir = os.getcwd()
    log_filepath = os.path.join(current_dir, log_filename)
    logger = setup_logging(log_filepath)
    logger.info("Starting Privacy-Preserving Encrypted ADMM MPC Simulation...")

    dso = DSO.create_full_context(poly_modulus_degree=8192, plain_modulus=1032193, scale=10**3)
    public_ctx = dso.create_public_context()

    building_names = {
        1: "2721",  # Building 1 to 2721
        2: "2722",  # Building 2 to 2722 
        3: "202",   # Building 3 to 202
        4: "57693"  # Building 4 to 57693
    }

    num_buildings = 4
    agents = [PrivacyPreservingAgent(agent_id=i, public_ctx=public_ctx, scale=dso.scale) for i in range(num_buildings)]
    coordinator = HierarchicalADMMCoordinator(
        num_buildings=num_buildings,
        prediction_horizon=PREDICTION_HORIZON,
        power_limit=P_MAX,
        penalty_param=RHO,
        max_iterations=MAX_ADMM_ITER,
        tolerance=EPSILON,
        public_ctx=public_ctx,
        dso=dso
    )

    sim1 = FMUSimulation(FMU_PATH1, START_TIME, STOP_TIME, STEP_SIZE)
    sim2 = FMUSimulation(FMU_PATH2, START_TIME, STOP_TIME, STEP_SIZE)
    sim3 = FMUSimulation(FMU_PATH3, START_TIME, STOP_TIME, STEP_SIZE) if FMU_PATH3 else None
    sim4 = FMUSimulation(FMU_PATH4, START_TIME, STOP_TIME, STEP_SIZE) if FMU_PATH4 else None
    sims = [sim1, sim2, sim3, sim4]

    forecast_data1 = load_data(INPUT_FILE1, OUTPUT_FILE1)
    forecast_data2 = load_data(INPUT_FILE2, OUTPUT_FILE2)
    forecast_data3 = load_data(INPUT_FILE3, OUTPUT_FILE3)
    forecast_data4 = load_data(INPUT_FILE4, OUTPUT_FILE4)

    days_offset = (SIMULATION_START_DATETIME - datetime(2018, 1, 1, 0, 0, 0)).days
    hours_offset = SIMULATION_START_DATETIME.hour
    minutes_offset = SIMULATION_START_DATETIME.minute
    steps_per_day = 24 * 4
    simulation_start_index = days_offset * steps_per_day + hours_offset * 4 + minutes_offset // 15

    controller1 = MPCControllerWithADMM(
        A1_ORIG, B1_ORIG, C1_ORIG, D1_ORIG, K1,
        historical_data=forecast_data1,
        Np=PREDICTION_HORIZON,
        Ts=STEP_SIZE,
        start_index=simulation_start_index,
        U_LB=BLDG1_U_LB,
        U_UB=BLDG1_U_UB,
        COMFORTABLE_TEMP_MIN=BLDG1_COMFORTABLE_TEMP_MIN,
        COMFORTABLE_TEMP_MAX=BLDG1_COMFORTABLE_TEMP_MAX,
        ar_model_path=AR_MODEL_PATH1
    )
    controller2 = MPCControllerWithADMM(
        A2_ORIG, B2_ORIG, C2_ORIG, D2_ORIG, K2,
        historical_data=forecast_data2,
        Np=PREDICTION_HORIZON,
        Ts=STEP_SIZE,
        start_index=simulation_start_index,
        U_LB=BLDG2_U_LB,
        U_UB=BLDG2_U_UB,
        COMFORTABLE_TEMP_MIN=BLDG2_COMFORTABLE_TEMP_MIN,
        COMFORTABLE_TEMP_MAX=BLDG2_COMFORTABLE_TEMP_MAX,
        ar_model_path=AR_MODEL_PATH2
    )
    controller3 = MPCControllerWithADMM(
        A3_ORIG, B3_ORIG, C3_ORIG, D3_ORIG, K3,
        historical_data=forecast_data3,
        Np=PREDICTION_HORIZON,
        Ts=STEP_SIZE,
        start_index=simulation_start_index,
        U_LB=BLDG3_U_LB,
        U_UB=BLDG3_U_UB,
        COMFORTABLE_TEMP_MIN=BLDG3_COMFORTABLE_TEMP_MIN,
        COMFORTABLE_TEMP_MAX=BLDG3_COMFORTABLE_TEMP_MAX,
        ar_model_path=AR_MODEL_PATH3
    )
    controller4 = MPCControllerWithADMM(
        A4_ORIG, B4_ORIG, C4_ORIG, D4_ORIG, K4,
        historical_data=forecast_data4,
        Np=PREDICTION_HORIZON,
        Ts=STEP_SIZE,
        start_index=simulation_start_index,
        U_LB=BLDG4_U_LB,
        U_UB=BLDG4_U_UB,
        COMFORTABLE_TEMP_MIN=BLDG4_COMFORTABLE_TEMP_MIN,
        COMFORTABLE_TEMP_MAX=BLDG4_COMFORTABLE_TEMP_MAX,
        ar_model_path=AR_MODEL_PATH4
    )
    controllers = [controller1, controller2, controller3, controller4]

    controller1.initialize_state(historical_data=forecast_data1)
    controller2.initialize_state(historical_data=forecast_data2)
    controller3.initialize_state(historical_data=forecast_data3)
    controller4.initialize_state(historical_data=forecast_data4)

    hvac_files = [
        HVAC_OUTPUT_FILE1,
        HVAC_OUTPUT_FILE2,
        HVAC_OUTPUT_FILE3,
        HVAC_OUTPUT_FILE4
    ]

    logger.info("Running hierarchical encrypted ADMM MPC simulation for 4 buildings...")
    results = run_hierarchical_encrypted_admm_simulation(
        dso,
        coordinator,
        agents,
        controllers,
        sims,
        hvac_files=hvac_files,
        building_names=building_names
    )
    logger.info("Computing performance metrics...")
    metrics = compute_performance_metrics(results)
    for key, value in metrics.items():
        logger.info(f"{key}: {value}")

    if 'admm_converged' in results:
        total_steps = len(results['admm_converged'])
        converged_steps = sum(results['admm_converged'])
        logger.info(
            f"ADMM Convergence Summary: {converged_steps}/{total_steps} steps converged "
            f"({converged_steps/total_steps*100:.1f}%)"
        )
        from collections import Counter
        iter_counts = Counter(results['admm_iterations'])
        logger.info("ADMM Iteration Distribution:")
        for iters, count in sorted(iter_counts.items()):
            logger.info(
                f"{iters} iterations: {count} times "
                f"({count/total_steps*100:.1f}%)"
            )

    logger.info("Saving simulation results to CSV files...")
    output_dir = os.path.join(current_dir, f"simulation_results_{timestamp}")
    csv_paths = save_simulation_results_to_csv(results, output_dir)
    logger.info(f"All simulation data saved to {output_dir}")
    # logger.info("Generating result plots...")
    plot_admm_mpc_results(results, metrics)
    logger.info("Simulation complete.")

if __name__ == "__main__":
    main()
