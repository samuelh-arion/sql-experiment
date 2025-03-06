# SQL Query Generation Experiment

This project evaluates and compares different approaches for generating SQL queries from natural language questions, with a focus on employee-related data queries.

## Overview

This experiment compares a baseline approach against an improved method for translating natural language queries into SQL. The project includes tools for:

- Processing natural language queries
- Generating SQL using different agent approaches
- Evaluating query accuracy
- Visualizing results with charts and graphs

## Project Structure

- `agent.py` - Implements LangChain agents for SQL generation
- `create-charts.py` - Generates visualization charts of experiment results
- `process_questions.py` - Processes the test dataset and generates results
- `process_questions_expanded.py` - Processes the expanded dataset
- `prompts.py` - Contains prompt templates for the agents
- `expand-dataset.py` - Utility for expanding the test dataset
- `requirements.txt` - Lists all Python dependencies
- `tools/` - Contains tools used by the agents
- `charts/` - Generated charts and visualizations
- `configuration/` - Project configuration
- `data_generation/` - Data generation utilities

## Key Datasets

- `dataset.csv` - Core test dataset with natural language questions
- `dataset-expanded.csv` - Expanded test dataset
- `results.json` - Results from the core dataset
- `results_expanded.json` - Results from the expanded dataset

## Setup and Installation

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env-example` to `.env` and add your OpenAI API key:
   ```
   OPENAI_KEY=your_openai_api_key
   ```

## Usage

### Running the Experiment

1. To process the core dataset:

   ```
   python process_questions.py
   ```

2. To process the expanded dataset:

   ```
   python process_questions_expanded.py
   ```

3. To generate charts and visualizations:
   ```
   python create-charts.py
   ```

## Charts and Visualizations

The `create-charts.py` script generates various visualizations including:

- Accuracy comparisons between baseline and improved approaches
- Query distribution analysis
- Error analysis
- Combined accuracy charts

All visualizations are saved to the `charts/` directory.
