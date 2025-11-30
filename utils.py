import openai
import os
import re
import json_repair
import pandas as pd
from omegaconf import DictConfig
import time

DATA_DIR = os.path.join(".", "data")
PREDICTION_DIR = os.path.join(".", "prediction_results")


def _get_param(config: DictConfig, key: str, default=None):
    """Fetch a parameter, preferring model-specific overrides if available."""
    model_name = getattr(config, "model_name", None)
    if model_name and model_name in config:
        model_cfg = config[model_name]
        if isinstance(model_cfg, DictConfig):
            model_kwargs = model_cfg.get("model_kwargs", {})
            if key in model_kwargs:
                return model_kwargs[key]
    return config.get(key, default)

class PathTemplate:
    """Template class for managing file paths in the project
    
    This class handles the generation of standardized file paths for various data
    and prediction files used throughout the project.
    
    Args:
        config (DictConfig): Configuration object containing year and other settings
    """
    def __init__(self, config: DictConfig):
        self.config = config
    
    @property
    def rawdata_csv(self) -> str:
        """Path to the raw state data CSV file
        
        Returns:
            str: Full path to the state data CSV for the configured year
        """
        if getattr(self.config, "population_data_path", None):
            return os.path.abspath(self.config.population_data_path)
        return os.path.join(DATA_DIR, f"state_data{self.config.year}.csv")
    
    @property
    def context_info_csv(self) -> str:
        """Path to the context information CSV file
        
        Returns:
            str: Full path to the information CSV file
        """
        if getattr(self.config, "context_info_path", None):
            return os.path.abspath(self.config.context_info_path)
        return os.path.join(DATA_DIR, "information.csv")
    
    @property
    def religion_xlsx(self) -> str:
        """Path to the religion data Excel file
        
        Returns:
            str: Full path to the religion data Excel file
        """
        if getattr(self.config, "religion_data_path", None):
            return os.path.abspath(self.config.religion_data_path)
        return os.path.join(DATA_DIR, "religion_data.xlsx")
    
    def get_output_pkl(self, run_name: str) -> str:
        """Get path for output pickle file
        
        Args:
            run_name (str): Name of the prediction run
            
        Returns:
            str: Full path to the output pickle file
        """
        filename = f"{run_name}.pkl"
        return os.path.join(PREDICTION_DIR, filename)
    
    def get_vote_csv(self, run_name: str) -> str:
        """Get path for vote results CSV file
        
        Args:
            run_name (str): Name of the prediction run
            
        Returns:
            str: Full path to the vote results CSV file
        """
        filename = f"{run_name}.csv"
        return os.path.join(PREDICTION_DIR, filename)
    
    def get_population_csv(self, run_name: str) -> str:
        """Get path for population data CSV file
        
        Args:
            run_name (str): Name of the prediction run
            
        Returns:
            str: Full path to the population data CSV file
        """
        filename = f"population_{run_name}.csv"
        return os.path.join(PREDICTION_DIR, filename)
    
    def get_prediction_csv(self, run_name: str) -> str:
        """Get path for prediction results CSV file
        
        Args:
            run_name (str): Name of the prediction run
            
        Returns:
            str: Full path to the prediction results CSV file
        """
        filename = f"prediction_{run_name}.csv"
        return os.path.join(PREDICTION_DIR, filename)

class PromptTemplate:
    """Template class for generating LLM prompts
    
    This class manages the construction of prompts for the LLM, including voter profile
    information and election context.
    
    Args:
        config (DictConfig): Configuration object containing election year, candidate names,
                           and other prompt-related settings
    
    Attributes:
        prompt_prefix (str): Standard prefix text for all prompts
        fields_of_interest (dict): Dictionary defining templates and value mappings for
                                 different demographic and contextual fields
        background (str): Election context information
        query (str): The actual question/prompt for the LLM
    """
    def __init__(self, config: DictConfig):
        self.config = config
        self.year = config.year
        self.prompt_prefix = config.prompt.prefix
        self.fields_of_interest = config.prompt.fields
        self.background = config.prompt.background.format(
            year=self.year,
            candidate_Republican=config.candidate_Republican,
            candidate_Democratic=config.candidate_Democratic
        )
        self.query = config.prompt.query.format(
            background=self.background,
            candidate_Republican=config.candidate_Republican,
            candidate_Democratic=config.candidate_Democratic
        )
        self.query = "\n" + self.query

        if config["context_info_flag"]:
            path_template = PathTemplate(config)
            infodf = pd.read_csv(path_template.context_info_csv, sep=config["SEP"], encoding='latin-1')
            self.context_info = "\n" + infodf[infodf["Title"] == str(config["context_info_title"])]["Content"].values[0]
        else:
            self.context_info = ""

class PredictionError(Exception):
    """Custom exception for handling prediction-related errors
    
    Args:
        message (str): Error message
        cost (float, optional): Associated API cost for the failed prediction
    
    Attributes:
        message (str): The error message
        cost (float): The API cost incurred before the error
    """
    def __init__(self, message: str, cost: float = None):
        self.message = message
        self.cost = cost
        super().__init__(self.message)

def predict_vote(idx: int, sample_data: pd.Series, config: DictConfig) -> dict:
    """Predict voting behavior for a single sample using LLM
    
    This function takes a single voter's data and predicts their voting behavior using an LLM.
    It handles retries on failure and calculates associated costs.
    
    Args:
        idx (int): Index of the sample being processed
        sample_data (pd.Series): Series containing voter's demographic and contextual features
        config (DictConfig): Configuration object containing model settings and parameters
        
    Returns:
        dict: Prediction results containing:
            - Model name
            - Support probabilities for each candidate
            - Final vote prediction
            - Cost and token usage
            - Original prompt and LLM response
            - Input features
            
    Raises:
        PredictionError: If prediction fails after maximum retries
    """
    costs = []
    max_retry = _get_param(config, "max_retry", 3)
    sleep_sec = _get_param(config, "sleep_sec", 1)
    for _ in range(max_retry):
        try:
            # Generate prompt
            prompt = gen_prompt(sample_data, config)

            # Build messages
            if config.system_prompt:
                messages = [{"role": "system", "content": config.system_prompt}, {"role": "user", "content": prompt}]
            else:
                messages = [{"role": "user", "content": prompt}]

            # Call LLM to get response
            response = do_query(messages, config)

            # Calculate cost and token
            if "cost_input" in config[config.model_name] and "cost_output" in config[config.model_name]:
                cost = int(response.usage.completion_tokens) * (config[config.model_name].cost_output) + int(response.usage.prompt_tokens) * (config[config.model_name].cost_input)
            else:
                cost = 0
            costs.append(cost)

            tokens = int(response.usage.total_tokens)
            
            # Parse response
            response_json = parse_response(response.choices[0].message.content, config)
            
            # Determine vote prediction
            vote_prediction = ''
            support_probs = [
                response_json[config.candidate_Republican],
                response_json[config.candidate_Democratic],
                response_json["vote for another candidate or not vote at all"]
            ]
            max_prob = max(support_probs)
            
            if response_json[config.candidate_Republican] == max_prob:
                vote_prediction = config.candidate_Republican
            elif response_json[config.candidate_Democratic] == max_prob:
                vote_prediction = config.candidate_Democratic
            else:
                vote_prediction = "Other"
                
            # Build result dictionary
            result = {
                "Model": config.model_name,
                "Support_Republican": response_json[config.candidate_Republican],
                "Support_Democratic": response_json[config.candidate_Democratic],
                "Support_Other": response_json["vote for another candidate or not vote at all"],
                "VotePrediction": vote_prediction,
                "Cost": sum(costs),
                "Tokens": tokens,
                "Prompt": prompt,
                "Response": response.choices[0].message.content
            }
            
            # Add original features
            for key in sample_data.index:
                result[key] = sample_data[key]
                
            return result
            
        except Exception as e:
            print(sample_data["State"], idx, e, ",", _, "attempts")
            time.sleep(sleep_sec)
            if _ == max_retry - 1:
                print("Failed with max_retry reached!!!")
                raise PredictionError(str(e), sum(costs))

def gen_prompt(sample_data: pd.Series, config: DictConfig) -> str:
    """Generate a prompt for the LLM based on voter data
    
    Constructs a structured prompt containing voter profile information and voting context
    using predefined templates.
    
    Args:
        sample_data (pd.Series): Series containing voter's demographic and contextual features
        config (DictConfig): Configuration object containing template settings
        
    Returns:
        str: Formatted prompt string ready for LLM input
    """
    # Build personal background information
    prompt_template = PromptTemplate(config)
    prompt = ""
    prompt += prompt_template.prompt_prefix
    
    for k in prompt_template.fields_of_interest.keys():
        if k == 'Religion' and sample_data[k] == 'None':
            continue
        if k == 'Worker_Class' and sample_data[k] == 'None':
            continue

        info_val = sample_data[k]
        elem_template = prompt_template.fields_of_interest[k]['template']
        elem_map = prompt_template.fields_of_interest[k]['valmap']
        if len(elem_map) == 0:
            prompt += elem_template.replace( 'XXX', str(info_val) )
        elif info_val in elem_map:
            prompt += elem_template.replace( 'XXX', elem_map[info_val] )

    prompt += prompt_template.context_info
    prompt += prompt_template.query

    return prompt

def do_query(messages: list, config: DictConfig) -> openai.types.chat.ChatCompletion:
    """Execute an API query to the LLM
    
    Sets up the OpenAI environment and makes an API call to get predictions.
    
    Args:
        messages (list): List of message dictionaries for the chat completion
        config (DictConfig): Configuration object containing API settings
        
    Returns:
        openai.types.chat.ChatCompletion: Raw response from the LLM
    """

    model = config.model_name
    # print(messages)

    os.environ["OPENAI_API_BASE"] = config[model].api_base
    os.environ["OPENAI_API_BASE"] = config[model].api_base
    if "api_key" in config[model]:
        os.environ["OPENAI_API_KEY"] = config[model].api_key
    else:
        os.environ["OPENAI_API_KEY"] = "sk-xxx"

    temperature = _get_param(config, "temperature", 0.7)
    timeout = _get_param(config, "request_timeout", None)

    response = openai.OpenAI(base_url=os.getenv("OPENAI_API_BASE")).chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
    )

    return response

def parse_response(content: str, config: DictConfig) -> dict:
    """Parse and validate the LLM response
    
    Extracts the JSON response from the LLM output and validates its structure and values.
    
    Args:
        content (str): Raw response content from the LLM
        config (DictConfig): Configuration object containing candidate information
        
    Returns:
        dict: Parsed and validated response containing voting probabilities and reasoning
        
    Raises:
        SystemError: If response structure is invalid
        ValueError: If response structure or probability values are invalid
    """
    
    pattern = r"```\s*(.+?)\s*```"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = content
    
    try:
        parsed_obj = json_repair.loads(json_str)
        # assert "Reason" in parsed_obj
        assert config['candidate_Republican'] in parsed_obj
        assert config['candidate_Democratic'] in parsed_obj
        assert "vote for another candidate or not vote at all" in parsed_obj
    except Exception as e:
        print(content)
        print("Can not load JSON!!!")
        print(e)
        raise SystemError("LLM Response Structure Error!!!")
    
    if round(sum(list(parsed_obj.values())[0:3]), 5) != 1:
        print(content)
        print(sum(list(parsed_obj.values())[0:3]))
        print(type(list(parsed_obj.values())[0]), type(list(parsed_obj.values())[1]), type(list(parsed_obj.values())[2]))
        raise ValueError("LLM Response Value Error!")
    
    return parsed_obj
