from typing import Union, Literal, List, Tuple, Optional
from omegaconf import OmegaConf, DictConfig
import wandb
import random
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
import os
import warnings
import argparse

from data_loader import build_population
from utils import predict_vote, PredictionError
from utils import PromptTemplate
from utils import PathTemplate, DATA_DIR, PREDICTION_DIR


class Flock:
    """Simulate and predict election results across different states."""
    
    def __init__(
        self,
        flock_config: Union[str, DictConfig, dict] = "./config/flock.yaml",
        llm_config: Union[str, DictConfig, dict] = "./config/llms.yaml",
    ):
        """Initialize Flock instance with split configs."""
        self.base_flock_config = self._load_config(flock_config)
        self.llm_config = self._load_config(llm_config)

        self.config: Optional[DictConfig] = None
        self.prediction_per_state: Optional[pd.DataFrame] = None
        self.foi_keys: Optional[List[str]] = None
        self.sim_num: Optional[int] = None
        self.year: Optional[int] = None
        self.states: Optional[List[str]] = None
        self.path_template: Optional[PathTemplate] = None
        self.run_name: Optional[str] = None

    def _load_config(self, cfg: Union[str, DictConfig, dict]) -> DictConfig:
        """Load YAML/DictConfig/dict into DictConfig."""
        if isinstance(cfg, DictConfig):
            return cfg
        if isinstance(cfg, dict):
            return OmegaConf.create(cfg)
        if isinstance(cfg, str):
            return OmegaConf.load(cfg)
        raise ValueError("config must be either a string path, dict or DictConfig object")

    def _build_runtime_config(
        self,
        vote_config: Union[str, DictConfig, dict],
        overrides: Optional[dict] = None,
    ) -> DictConfig:
        """Merge flock+vote+llm configs and apply overrides."""
        vote_cfg = self._load_config(vote_config)
        merged_config = OmegaConf.merge(self.base_flock_config, vote_cfg)
        merged_config = OmegaConf.merge(merged_config, self.llm_config)
        if overrides:
            merged_config = OmegaConf.merge(merged_config, OmegaConf.create(overrides))

        # Default to flock model_name if vote does not override
        if not merged_config.get("model_name", None):
            merged_config.model_name = self.base_flock_config.get("model_name", None)

        # Set helper flags for prompt fields
        fields_cfg = merged_config.get("prompt", {}).get("fields", {})
        merged_config.education_flag = "Education" in fields_cfg
        merged_config.religion_flag = "Religion" in fields_cfg
        return merged_config
    
    def _init_params(self):
        """Initialize parameters"""
        self.use_wandb = self.config.get("use_wandb", False)
        
        self.year = self.config["year"]
        if isinstance(self.config["state"], str):
            self.states = [state.strip() for state in self.config["state"].split(",")]
        else:
            self.states = list(self.config["state"])
            
        self.sim_num = self.config["sim_num"]
        random.seed(self.config["random_seed"])
        self.foi_keys = list(PromptTemplate(self.config).fields_of_interest.keys())
        
        # Initialize result DataFrame
        self.prediction_per_state = pd.DataFrame(columns=[
            "Model", "State", "Year", "Sim_num", "Education", "Religion",
            "Republican_support", "Democratic_support", "Other_support", 
            "Cost", "Avg. token", "Running Time"
        ])
        
        self.path_template = PathTemplate(self.config)

        if not os.path.exists(PREDICTION_DIR):
            os.makedirs(PREDICTION_DIR)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            warnings.warn(f"Directory {DATA_DIR} does not exist, created it. You need to make sure the population data and religion data exist in this directory.")
        
    def _predict_single(self, idx: int, sample_data: pd.Series) -> dict:
        """Single sample prediction"""
        try:
            # Actual prediction logic
            result = predict_vote(idx, sample_data, self.config)
            return {
                "success": True,
                "data": result,
                "error": None
            }
        except PredictionError as e:
            return {
                "success": False,
                "data": {"Cost": e.cost},
                "error": str(e)
            }
    
    def _run_serial_prediction(self, 
                             datadf: pd.DataFrame, 
                             vote_df: pd.DataFrame,
                             state: str) -> Tuple[pd.DataFrame, List[float], List[float], List[int]]:
        """Run predictions serially.
        
        Args:
            datadf: Input data for predictions
            vote_df: DataFrame to store voting results
            state: State name
            
        Returns:
            Tuple containing:
                - Updated vote DataFrame
                - List of costs
                - List of token counts
                - List of failed prediction IDs
        """
        costs = []
        tokens = []
        failed_pids = []
        
        # Use tqdm to display progress
        for idx, row in tqdm(datadf.iterrows(), total=len(datadf)):
            result = self._predict_single(idx, row)
            
            if result["success"]:
                # Update result DataFrame
                vote_df.loc[idx] = result["data"]
                costs.append(result["data"]["Cost"])
                tokens.append(result["data"]["Tokens"])
                
                # Update wandb in real-time
                # self._update_wandb_results(idx, state, vote_df)
                
                # Save vote results
                vote_df.to_csv(self.path_template.get_vote_csv(self.run_name), index=False)
            else:
                print(f"Sample {idx} failed: {result['error']}")
                failed_pids.append(idx)
                costs.append(result["data"]["Cost"])
                
        return vote_df, costs, tokens, failed_pids
    
    def _run_parallel_prediction(self, 
                               datadf: pd.DataFrame, 
                               vote_df: pd.DataFrame,
                               state: str) -> Tuple[pd.DataFrame, List[float], List[float], List[int]]:
        """Run predictions in parallel using ProcessPoolExecutor.
        
        Args:
            datadf: Input data for predictions
            vote_df: DataFrame to store voting results
            state: State name
            
        Returns:
            Tuple containing:
                - Updated vote DataFrame
                - List of costs
                - List of token counts
                - List of failed prediction IDs
        """
        costs = []
        tokens = []
        failed_pids = []
        
        # Prepare parameters for parallel processing
        args_list = [(idx, row) for idx, row in datadf.iterrows()]
        
        with ProcessPoolExecutor(max_workers=self.config.get("num_workers", 4)) as executor:
            futures = [executor.submit(self._predict_single, *args) for args in args_list]
            
            # Use tqdm to display progress
            for idx, future in enumerate(tqdm(futures)):
                result = future.result()
                if result["success"]:
                    vote_df.loc[idx] = result["data"]
                    costs.append(result["data"]["Cost"])
                    tokens.append(result["data"]["Tokens"])
                    
                    # Update wandb in real-time
                    # self._update_wandb_results(idx, state, vote_df)

                    # Save vote results
                    vote_df.to_csv(self.path_template.get_vote_csv(self.run_name),index=False)
                else:
                    print(f"Sample {idx} failed: {result['error']}")
                    failed_pids.append(idx)
                    costs.append(result["data"]["Cost"])

        return vote_df, costs, tokens, failed_pids
    
    def _update_wandb_results(self, 
                            idx: int, 
                            state: str, 
                            result_df: pd.DataFrame) -> None:
        """Update Weights & Biases with current simulation results.
        
        Args:
            idx: Current sample index
            state: State name
            result_df: DataFrame containing current results
        """
        if not self.use_wandb:
            return
        
        # Update detailed results
        table = wandb.Table(dataframe=result_df)
        wandb.log({
            f"vote_details_{state}": table,
        })
    
    def _run_simulation(self, 
                       state_idx: int, 
                       state: str, 
                       mode: Literal["parallel", "serial"] = "parallel") -> None:
        """Run election simulation for a single state.
        
        Args:
            state_idx: Index of the state in the states list
            state: Name of the state to simulate
            mode: Execution mode, either "parallel" or "serial"
        """
        run_name = f"{state_idx}_{state}_{self.year}_{self.config.sim_num}_{self.config.model_name}_{self.config.context_info_title}_Education_{self.config.education_flag}_Religion_{self.config.religion_flag}"
        self.run_name = run_name
        
        # Initialize wandb
        if self.use_wandb:
            wandb.init(
                entity=self.config.wandb_entity,
                project=self.config.wandb_project,
                name=run_name,
                config=OmegaConf.to_container(self.config, resolve=True),
            )
        
        print(f"Starting prediction for {self.year} {state} with {self.sim_num} samples......")
        print(f"Model: {self.config.model_name}")
        print(f"Education: {self.config.education_flag}")
        print(f"Religion: {self.config.religion_flag}")
        print(f"Running mode: {mode}")
        current_time = time.time()
        
        # Build simulation data
        rawdata_file = str(self.path_template.rawdata_csv)
        datadf = build_population(state, rawdata_file, 
                                     self.sim_num, self.foi_keys, self.config)
        datadf.to_csv(self.path_template.get_population_csv(self.run_name), index=False)

        # Initialize result data structure
        initial_data = {
            'Model': '',
            'Support_Republican': 0.0,
            'Support_Democratic': 0.0,
            'Support_Other': 0.0,
            'VotePrediction': '',
            **{key: '' for key in self.foi_keys},
            'Tokens': 0.0,
            'Cost': 0.0,
            'Prompt': '',
            'Response': ''
        }
        
        vote_df = pd.DataFrame([initial_data] * self.sim_num)
        
        # Select prediction method based on mode
        if mode == "parallel":
            vote_df, costs, tokens, failed_pids = self._run_parallel_prediction(
                datadf, vote_df, state
            )
        else:
            vote_df, costs, tokens, failed_pids = self._run_serial_prediction(
                datadf, vote_df, state
            )
        
        # Process final results
        self._process_results(state_idx, state, vote_df, costs, tokens, failed_pids, current_time)
        
        if self.use_wandb:
            wandb.finish()
        print("-"*20)
    
    def fit(
        self,
        config: Union[str, DictConfig, dict] = "./config/vote.yaml",
        **kwargs,
    ) -> pd.DataFrame:
        """Backward-compatible alias for vote()."""
        return self.vote(vote_config=config, **kwargs)

    def vote(
        self,
        vote_config: Union[str, DictConfig, dict] = "./config/vote.yaml",
        flock_config: Optional[Union[str, DictConfig, dict]] = None,
        llm_config: Optional[Union[str, DictConfig, dict]] = None,
        **overrides,
    ) -> pd.DataFrame:
        """Run election simulation with split configs."""
        if flock_config:
            self.base_flock_config = self._load_config(flock_config)
        if llm_config:
            self.llm_config = self._load_config(llm_config)

        runtime_config = self._build_runtime_config(vote_config, overrides)

        self.config = runtime_config
        self._init_params()
        
        print(self.states)
        for state_idx, state in enumerate(self.states):
            self._run_simulation(state_idx, state, self.config.mode)
            
        return self.prediction_per_state
    
    def _process_results(self, 
                        state_idx: int, 
                        state: str, 
                        vote_df: pd.DataFrame, 
                        costs: List[float], 
                        tokens: List[float], 
                        failed_pids: List[int], 
                        start_time: float) -> None:
        """Process and save simulation results for a state.
        
        Args:
            state_idx: Index of the state in the states list
            state: Name of the state
            vote_df: DataFrame containing voting predictions
            costs: List of API costs for each prediction
            tokens: List of token counts for each prediction
            failed_pids: List of failed prediction IDs
            start_time: Timestamp when simulation started
        """
        if isinstance(vote_df, list):
            tmp = np.zeros((self.sim_num, len(vote_df[0])))
            vote_df_tmp = pd.DataFrame(tmp, columns=vote_df[0].index)
            vote_df_tmp[:] = vote_df[:]
            vote_df = vote_df_tmp
        self._update_wandb_results(state_idx, state, vote_df)

        # If there are failed samples, remove them from results
        if len(failed_pids) > 0:
            print(f"Failed sample IDs: {failed_pids}")
            vote_df = vote_df.drop(failed_pids)
            vote_df = vote_df.reset_index(drop=True)
        
        # Calculate support rates
        support_Republican = sum(vote_df["Support_Republican"]) / len(vote_df)
        support_Democratic = sum(vote_df["Support_Democratic"]) / len(vote_df)
        support_Other = 1 - support_Democratic - support_Republican
        
        # Record results
        duration = time.time() - start_time
        formatted_duration = time.strftime("%H:%M:%S", time.gmtime(duration))
        
        self.prediction_per_state.loc[state_idx] = [
            self.config.model_name, state, self.config.year, 
            len(vote_df), self.config.education_flag, self.config.religion_flag,
            support_Republican, support_Democratic, support_Other, 
            np.sum(np.array(costs)), np.mean(np.array(tokens)), formatted_duration
        ]
        
        # Save results
        self.prediction_per_state.iloc[[state_idx]].to_csv(self.path_template.get_prediction_csv(self.run_name), index=False)
        if self.use_wandb:
            table = wandb.Table(dataframe=self.prediction_per_state.iloc[[state_idx]])
            wandb.log({"prediction_results": table})

        print(f"Finish predicting {self.config.year} {state} with {len(vote_df)} simulation samples!")
        print(f"Education: {self.config.education_flag}")
        print(f"Religion: {self.config.religion_flag}")
        print("Democratic: {}, Republican: {}".format(support_Democratic, support_Republican))
        print("Total cost: ${}".format(np.sum(np.array(costs))))
        print("Averge token: ", np.mean(np.array(tokens)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--flock",
        type=str,
        default="./config/flock.yaml",
        help="Path to flock (population/run) config",
    )
    parser.add_argument(
        "--vote",
        dest="vote_cfg",
        type=str,
        default="./config/vote.yaml",
        help="Path to vote/task config",
    )
    parser.add_argument(
        "--llms",
        type=str,
        default="./config/llms.yaml",
        help="Path to llm registry config",
    )
    parser.add_argument(
        "vote_positional",
        type=str,
        nargs="?",
        help="Optional positional vote config path",
    )

    args = parser.parse_args()

    vote_path = args.vote_positional or args.vote_cfg

    flock = Flock(flock_config=args.flock, llm_config=args.llms)
    prediction_df = flock.vote(vote_config=vote_path)
    print(prediction_df)
