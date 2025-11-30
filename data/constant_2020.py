"""
Constants file containing demographic classification lists used for population analysis.
These lists include racial categories and their relationships with:
- Occupational distribution by gender
- Industry sectors
- Age groups
- Educational attainment
- Religious affiliations

Data categories are primarily based on US Census Bureau classifications, 
except for religious affiliations which are custom categories.
"""

race_list = ["White alone", "Black or African American alone", "Asian alone (400-499)", "Some other race alone"]

race_male_occ = [
    "OCCUPATION!!Male civilian employed population 16 years and over!!Management, business, science, and arts occupations",
    "OCCUPATION!!Male civilian employed population 16 years and over!!Service occupations",
    "OCCUPATION!!Male civilian employed population 16 years and over!!Sales and office occupations",
    "OCCUPATION!!Male civilian employed population 16 years and over!!Natural resources, construction, and maintenance occupations",
    "OCCUPATION!!Male civilian employed population 16 years and over!!Production, transportation, and material moving occupations",
]

race_female_occ = [
    "OCCUPATION!!Female civilian employed population 16 years and over!!Management, business, science, and arts occupations",
    "OCCUPATION!!Female civilian employed population 16 years and over!!Service occupations",
    "OCCUPATION!!Female civilian employed population 16 years and over!!Sales and office occupations",
    "OCCUPATION!!Female civilian employed population 16 years and over!!Natural resources, construction, and maintenance occupations",
    "OCCUPATION!!Female civilian employed population 16 years and over!!Production, transportation, and material moving occupations",
]

race_industry = [
    "INDUSTRY!!Civilian employed population 16 years and over!!Agriculture, forestry, fishing and hunting, and mining",
    "INDUSTRY!!Civilian employed population 16 years and over!!Construction",
    "INDUSTRY!!Civilian employed population 16 years and over!!Manufacturing",
    "INDUSTRY!!Civilian employed population 16 years and over!!Wholesale trade",
    "INDUSTRY!!Civilian employed population 16 years and over!!Retail trade",
    "INDUSTRY!!Civilian employed population 16 years and over!!Transportation and warehousing, and utilities",
    "INDUSTRY!!Civilian employed population 16 years and over!!Information",
    "INDUSTRY!!Civilian employed population 16 years and over!!Finance and insurance, and real estate and rental and leasing",
    "INDUSTRY!!Civilian employed population 16 years and over!!Professional, scientific, and management, and administrative and waste management services",
    "INDUSTRY!!Civilian employed population 16 years and over!!Educational services, and health care and social assistance",
    "INDUSTRY!!Civilian employed population 16 years and over!!Arts, entertainment, and recreation, and accommodation and food services",
    "INDUSTRY!!Civilian employed population 16 years and over!!Other services (except public administration)",
    "INDUSTRY!!Civilian employed population 16 years and over!!Public administration",
]

race_age = [
    "SEX AND AGE!!Total population!!18 to 24 years",
    "SEX AND AGE!!Total population!!25 to 34 years",
    "SEX AND AGE!!Total population!!35 to 44 years",
    "SEX AND AGE!!Total population!!45 to 54 years",
    "SEX AND AGE!!Total population!!55 to 64 years",
    "SEX AND AGE!!Total population!!65 to 74 years",
    "SEX AND AGE!!Total population!!75 years and over",
]

race_education = [
    "EDUCATIONAL ATTAINMENT!!Population 25 years and over!!Less than high school diploma",
    "EDUCATIONAL ATTAINMENT!!Population 25 years and over!!High school graduate (includes equivalency)",
    "EDUCATIONAL ATTAINMENT!!Population 25 years and over!!Some college or associate's degree",
    "EDUCATIONAL ATTAINMENT!!Population 25 years and over!!Bachelor's degree",
    "EDUCATIONAL ATTAINMENT!!Population 25 years and over!!Graduate or professional degree",
]

race_religion = [
    "Catholic",
    "Protestant",
    "Islam",
    "Judaism",
    "Others",
    "None",
]

race_worker_class = [
    "CLASS OF WORKER!!Civilian employed population 16 years and over!!Private wage and salary workers",
    "CLASS OF WORKER!!Civilian employed population 16 years and over!!Government workers",
    "CLASS OF WORKER!!Civilian employed population 16 years and over!!Self-employed workers in own not incorporated business",
    "CLASS OF WORKER!!Civilian employed population 16 years and over!!Unpaid family workers",
]