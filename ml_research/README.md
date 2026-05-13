# ML Research Sandbox

This directory contains the original Machine Learning training, data ingestion, and simulation benchmarking code from the 	emp-main development branch.

## Purpose
- **Training:** Re-train the DQN model using the 	raining/ and gent/ modules.
- **Data Generation:** Use data_pipeline/ to fetch historical weather/irradiance data from NASA Power, NSRDB, etc.
- **Benchmarking:** Use simulation/ for stochastic weather modeling and multi-day evaluation.

## Structure
- gent/: DQN and Regime-Conditioned network architectures.
- environment/: Solar tracking RL environment and state builders.
- 	raining/: Training loops, loggers, and schedulers.
- data_pipeline/: Multi-source data ingestion scripts.
- simulation/: Advanced physics simulation runners.
- config/: YAML configurations for experiments.

> **Note:** This code is isolated from the production FastAPI backend to keep the API lightweight while preserving the core engineering research.