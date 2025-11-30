import random
import numpy as np
import pandas as pd
from utils import PathTemplate


def build_population(
    state: str, 
    rawdata_file: str, 
    sim_num: int, 
    foi_keys: list, 
    config: dict
) -> pd.DataFrame:
    """
    Build a simulated population dataset for a given state with demographic characteristics.
    
    Args:
        state (str): Target state name
        rawdata_file (str): Path to raw census data file
        sim_num (int): Number of individuals to simulate
        foi_keys (list): Features of interest to include in output
        config (dict): Configuration dictionary containing:
            - year (int): Census year
            - SEP (str): CSV separator character
            - context_info_title (str): Title for context information
            
    Returns:
        pd.DataFrame: Simulated population data with demographic characteristics
    """

    # Map foi_keys to required constant variables
    variable_mapping = {
        'Race': 'Race_list',
        'Occupation': ['race_male_occ', 'race_female_occ'],
        'Industry': 'race_industry',
        'Worker_Class': 'race_worker_class',
        'Age': 'race_age',
        'Education': 'race_education',
        'Religion': 'race_religion'
    }

    # Collect variables needed based on foi_keys
    needed_variables = ['race_list']  # race_list is always required for basic demographics
    for key in foi_keys:
        if key in variable_mapping:
            if isinstance(variable_mapping[key], list):
                needed_variables.extend(variable_mapping[key])
            else:
                needed_variables.append(variable_mapping[key])
    needed_variables = list(set(needed_variables))  # Remove duplicates

    import_path = f"data.constant_{config['year']}"
    constant_module = __import__(import_path, fromlist=needed_variables)
    
    race_list = constant_module.race_list
    race_male_occ = race_female_occ = race_industry = race_worker_class = race_age = race_education = race_religion = None
    if "Occupation" in foi_keys:
        race_male_occ = constant_module.race_male_occ
        race_female_occ = constant_module.race_female_occ
    if "Industry" in foi_keys:
        race_industry = constant_module.race_industry
    if "Worker_Class" in foi_keys:
        race_worker_class = constant_module.race_worker_class
    if "Age" in foi_keys:
        race_age = constant_module.race_age
    if "Education" in foi_keys:
        race_education = constant_module.race_education
    if "Religion" in foi_keys:
        race_religion = constant_module.race_religion

    rawdatadf = pd.read_csv(rawdata_file, sep=config["SEP"], encoding='latin-1')

    path_template = PathTemplate(config)
    religion_file = str(path_template.religion_xlsx)
    religiondf = pd.read_excel(religion_file)

    if state not in rawdatadf["Geographic Area Name"].tolist() or ("Religion" in foi_keys and state not in religiondf["State"].tolist()):
        raise ValueError(f"Invalid state name: {state}, state in rawdatadf: {state in rawdatadf['Geographic Area Name'].tolist()}, state in religiondf: {state in religiondf['State'].tolist()}")

    # agent_keys = ["State", "Race", "Sex", "Occupation", "Industry", "Worker_Class" "Age", "Education", "Religion", "Context"]
    tmp = np.zeros((sim_num, len(foi_keys)))
    resdf = pd.DataFrame(tmp, columns=foi_keys, dtype="object")
    resdf.loc[:, "State"] = [state]*sim_num

    statedf = rawdatadf[rawdatadf["Geographic Area Name"] == state]
    statedf = statedf[statedf["Population Groups"].isin(race_list)]

    religiondf = religiondf[religiondf["State"] == state]
    
    # race proportion
    race_num = {}
    race_total = 0
    race_not_zero = race_list.copy()
    for race in race_list:
        if race not in statedf["Population Groups"].tolist():
            race_num[race] = 0
            race_not_zero.remove(race)
            continue
        if config["year"] == 2024:
            race_num[race] = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!Total population!!18 years and over...55"].values[0]
        elif config["year"] == 2020:
            race_num[race] = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!Total population!!18 years and over.1"].values[0]
        elif config["year"] in [2016, 2012]:
            race_num[race] = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!18 years and over.1"].values[0]
        race_total += race_num[race]
        if race_num[race] == 0:
            race_not_zero.remove(race)

    cnt = 0
    for race in race_not_zero:
        race_num[race] = int(race_num[race] * sim_num / race_total)
        if race == race_not_zero[-1]:
            race_num[race] = sim_num - cnt
        cnt += race_num[race]

    pointer = 0
    for race in race_num.keys():
        if race_num[race] == 0:
            continue
        # race_num[race] = int(race_num[race] * sim_num / race_total)
        # if race == race_list[-1]:
        #     race_num[race] = sim_num - pointer
        race_key = race.split(" alone")[0]
        if race_key in ["Some Other Race", "Some other race"]:
            race_key = "Non white, asian or black"
        resdf.loc[pointer: pointer+race_num[race]-1, "Race"] = [race_key]*race_num[race]

        # set sex
        male, female = set_sex(resdf, statedf, race, race_num, pointer, config)

        # set age
        if config["year"] == 2024:
            total_18 = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!Total population!!18 years and over...55"].values[0]
        elif config["year"] == 2020:
            total_18 = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!Total population!!18 years and over.1"].values[0]
        elif config["year"] in [2016, 2012]:
            total_18 = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!18 years and over.1"].values[0]

        if "Age" in foi_keys:
            set_age(resdf, statedf, race, race_num, pointer, config, race_age, total_18)

        # calculate employed, unemployed
        occ_total_real_num = statedf[statedf["Population Groups"] == race]["EMPLOYMENT STATUS!!Population 16 years and over"].values[0]
        
        total_employed_rate = statedf[statedf["Population Groups"] == race]["EMPLOYMENT STATUS!!Population 16 years and over!!In labor force"].values[0] * 0.01
        
        total_unemployed_rate = statedf[statedf["Population Groups"] == race]["EMPLOYMENT STATUS!!Population 16 years and over!!In labor force!!Civilian labor force!!Unemployed"].values[0] * 0.01
        
        occ_female_real_num = statedf[statedf["Population Groups"] == race]["EMPLOYMENT STATUS!!Females 16 years and over"].values[0]
        
        female_employed_rate = statedf[statedf["Population Groups"] == race]["EMPLOYMENT STATUS!!Females 16 years and over!!In labor force"].values[0] * 0.01
        
        female_unemployed_rate = statedf[statedf["Population Groups"] == race]["EMPLOYMENT STATUS!!Females 16 years and over!!In labor force!!Civilian labor force!!Unemployed"].values[0] * 0.01
        
        male_employed_rate = (occ_total_real_num * total_employed_rate - occ_female_real_num * female_employed_rate) / (occ_total_real_num - occ_female_real_num)
        
        male_unemployed_rate = (occ_total_real_num * total_unemployed_rate - occ_female_real_num * female_unemployed_rate) / (occ_total_real_num - occ_female_real_num)

        male_employed = int(male * male_employed_rate)
        male_unemployed = int(male * male_unemployed_rate)
        male_notforce = male - male_employed - male_unemployed
        
        female_employed = int(female * female_employed_rate)
        female_unemployed = int(female * female_unemployed_rate)
        female_notforce = female - female_employed - female_unemployed

        male_index = list(range(male))
        female_index = list(range(female))
        random.shuffle(male_index)
        random.shuffle(female_index)

        if "Occupation" in foi_keys:
            set_occ(resdf, statedf, race, race_num, pointer, config, race_male_occ, race_female_occ, male, female, male_employed, female_employed, male_unemployed, female_unemployed, male_index, female_index)
        
        if "Industry" in foi_keys:
            set_industry(resdf, statedf, race, race_num, pointer, config, race_industry, male, female, male_employed, female_employed, male_unemployed, female_unemployed, male_index, female_index)
        
        if "Worker_Class" in foi_keys:
            set_worker_class(resdf, statedf, race, race_num, pointer, config, race_worker_class, male, female, male_employed, female_employed, male_unemployed, female_unemployed, male_index, female_index)


        # set education
        if "Education" in foi_keys:
            set_education(resdf, statedf, race, race_num, pointer, config, race_education)

        # set religion
        if "Religion" in foi_keys:
            set_religion(resdf, religiondf, race, race_num, pointer, config, race_religion)

        pointer += race_num[race]

    return resdf


def set_sex(resdf, statedf, race, race_num, pointer, config):
    if config["year"] >= 2020:
        male = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!Total population!!18 years and over!!Male"].values[0]
    elif config["year"] == 2016:
        male = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!18 years and over!!Male"].values[0]
    elif config["year"] == 2012:
        male = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!Male.2"].values[0]
    male = int(round(male / 100 * race_num[race], 0))
    female = race_num[race] - male
    # female = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!Total population!!Female"].values[0]
    resdf.loc[pointer: pointer+male-1, "Sex"] = ["Male"] * male
    resdf.loc[pointer+male: pointer+race_num[race]-1, "Sex"] = ["Female"] * female

    return male, female

def set_age(resdf, statedf, race, race_num, pointer, config, race_age, total_18):
    age_total = 0
    age_dis = []
    total_population = statedf[statedf["Population Groups"] == race]["SEX AND AGE!!Total population"].values[0]
    for key in race_age:
        cnt = statedf[statedf["Population Groups"] == race][key].values[0]
        cnt = int(cnt / 100 * total_population / total_18 * race_num[race])
        if key == race_age[-1]:
            cnt = race_num[race] - age_total
        age_dis += [key[31:]] * cnt
        age_total += cnt

    random.shuffle(age_dis)
    resdf.loc[pointer: pointer+race_num[race]-1, "Age"] = age_dis

def set_occ(resdf, statedf, race, race_num, pointer, config, race_male_occ, race_female_occ, male, female, male_employed, female_employed, male_unemployed, female_unemployed, male_index, female_index):
    male_occ = ["Not in labor force"] * male
    female_occ = ["Not in labor force"] * female
    
    # employed
    pointer_tmp = 0
    for key in race_male_occ:
        cnt = statedf[statedf["Population Groups"] == race][key].values[0]
        cnt = int(cnt / 100 * male_employed)
        if key == race_male_occ[-1]:
            cnt = male_employed - pointer_tmp
        
        if config["year"] == 2012:
            occ_key = key[12:][:-2]
        else:
            occ_key = key[65:]
        
        male_occ_indices = male_index[pointer_tmp: pointer_tmp+cnt]
        for idx in male_occ_indices:
            male_occ[idx] = occ_key
        pointer_tmp += cnt

    pointer_tmp = 0
    for key in race_female_occ:
        cnt = statedf[statedf["Population Groups"] == race][key].values[0]
        cnt = int(cnt / 100 * female_employed)
        if key == race_female_occ[-1]:
            cnt = female_employed - pointer_tmp
        
        if config["year"] == 2012:
            occ_key = key[12:][:-2]
        else:
            occ_key = key[67:]
        
        female_occ_indices = female_index[pointer_tmp: pointer_tmp+cnt]
        for idx in female_occ_indices:
            female_occ[idx] = occ_key
        pointer_tmp += cnt
    
    # unemployed
    male_occ_indices = male_index[male_employed: male_employed+male_unemployed]
    female_occ_indices = female_index[female_employed: female_employed+female_unemployed]
    for idx in male_occ_indices:
        male_occ[idx] = "Unemployed"
    for idx in female_occ_indices:
        female_occ[idx] = "Unemployed"
    
    resdf.loc[pointer: pointer+race_num[race]-1, "Occupation"] = male_occ + female_occ

def set_industry(resdf, statedf, race, race_num, pointer, config, race_industry, male, female, male_employed, female_employed, male_unemployed, female_unemployed, male_index, female_index):
    male_industry = ["Not in labor force"] * male
    female_industry = ["Not in labor force"] * female

    # employed
    industry_male = 0
    industry_female = 0
    for key in race_industry:
        cnt = statedf[statedf["Population Groups"] == race][key].values[0]
        cnt_male = int(cnt / 100 * male_employed)
        cnt_female = int(cnt / 100 * female_employed)
        if key == race_industry[-1]:
            cnt_male = male_employed - industry_male
            cnt_female = female_employed - industry_female
        
        if config["year"] == 2012:
            ind_key = key[10:]
        else:
            ind_key = key[58:]

        male_industry_indices = male_index[industry_male: industry_male+cnt_male]
        female_industry_indices = female_index[industry_female: industry_female+cnt_female]
        for idx in male_industry_indices:
            male_industry[idx] = ind_key
        for idx in female_industry_indices:
            female_industry[idx] = ind_key
        industry_male += cnt_male
        industry_female += cnt_female

    # unemployed
    male_industry_indices = male_index[male_employed: male_employed+male_unemployed]
    female_industry_indices = female_index[female_employed: female_employed+female_unemployed]
    for idx in male_industry_indices:
        male_industry[idx] = "Unemployed"
    for idx in female_industry_indices:
        female_industry[idx] = "Unemployed"
    
    resdf.loc[pointer: pointer+race_num[race]-1, "Industry"] = male_industry + female_industry

def set_worker_class(resdf, statedf, race, race_num, pointer, config, race_worker_class, male, female, male_employed, female_employed, male_unemployed, female_unemployed, male_index, female_index):
    male_worker_class = ["None"] * male
    female_worker_class = ["None"] * female

    worker_class_male = 0
    worker_class_female = 0
    for key in race_worker_class:
        cnt = statedf[statedf["Population Groups"] == race][key].values[0]
        cnt_male = int(cnt / 100 * male_employed)
        cnt_female = int(cnt / 100 * female_employed)
        if key == race_worker_class[-1]:
            cnt_male = male_employed - worker_class_male
            cnt_female = female_employed - worker_class_female
        
        worker_class_key = key[65:]
        
        male_worker_class_indices = male_index[worker_class_male: worker_class_male+cnt_male]
        female_worker_class_indices = female_index[worker_class_female: worker_class_female+cnt_female]
        for idx in male_worker_class_indices:
            male_worker_class[idx] = worker_class_key
        for idx in female_worker_class_indices:
            female_worker_class[idx] = worker_class_key
        worker_class_male += cnt_male
        worker_class_female += cnt_female
    
    resdf.loc[pointer: pointer+race_num[race]-1, "Worker_Class"] = male_worker_class + female_worker_class

def set_education(resdf, statedf, race, race_num, pointer, config, race_education):
    education_total = 0
    education_dis = []
    for key in race_education:
        cnt = statedf[statedf["Population Groups"] == race][key].values[0]
        cnt = int(cnt / 100 * race_num[race])
        if key == race_education[-1]:
            cnt = race_num[race] - education_total
        
        if config["year"] == 2012:
            edu_key = key[24:]
        else:
            edu_key = key[54:]

        education_dis += [edu_key] * cnt
        education_total += cnt

    random.shuffle(education_dis)
    resdf.loc[pointer: pointer+race_num[race]-1, "Education"] = education_dis

def set_religion(resdf, religiondf, race, race_num, pointer, config, race_religion):
    if config["year"] >= 2020:
        religiondf = religiondf[religiondf["Year"] == 2020]
    else:
        religiondf = religiondf[religiondf["Year"] == 2010]
    religion_total = 0
    religion_dis = []
    for key in race_religion:
        if key == race_religion[-1]:
            cnt = race_num[race] - religion_total
        else:
            cnt = religiondf[key].values[0]
            cnt = int(cnt / 100 * race_num[race])
        religion_key = key
        if religion_key == "Others":
            religion_key = "Non Catholic, Protestant, Islam or Judaism"
        religion_dis += [religion_key] * cnt
        religion_total += cnt

    random.shuffle(religion_dis)
    resdf.loc[pointer: pointer+race_num[race]-1, "Religion"] = religion_dis