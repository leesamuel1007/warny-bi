# DS545 Warny-BI Project

## Project Procedure

### Data Loading and Preprocessing
1. Read multiple raw .csv files and multiple image data as the input dataset.
2. Verify that the image paths in the .csv files are valid.
3. Perform lightweight EDA on the raw .csv files - check for column names, inferred data types, null-like values, data distribution, skewedness, data categories, etc.
4. Generate a reviewable `schema.json` from actual CSV files. Raw CSV files are the ground truth; `schema.json` is generated for operator review and can be edited to set preferred column types, SQL types, primary keys, foreign keys, and normalization rules.
5. Perform lightweight cleaning on the raw .csv files to make them palatable for SQL parsing, database key separation, RAG, etc.
6. Save the cleaned .csv files to data/processed/**.csv.
7. Regenerate `data/processed/schema.json` from the processed CSV files for SQL table construction.

The runnable Python entrypoint is `term_project/scripts/python/preprocess_dataset.py`.
The supported preprocessing commands are:

- `validate`: verify raw CSV presence and image path references.
- `eda`: inspect raw CSV columns, inferred data types, null-like values, and distributions.
- `schema`: generate `schema.json` from a selected CSV directory.
- `clean`: apply schema-driven normalization rules and write SQL-ready processed CSV files.

### SQL Database Construction
#### Azure
1. Write SQL queries and files that will run in Azure pipeline, that read the uploaded .csv files and image files in Azure Blob Storage.
2. Then write SQL queries and files that will construct SQL Tables from the .csv files.
3. Then write SQL query that creates a single view for RAG retrieval and Azure AI Search.


#### FOSS
1. Lay out the required FOSS programs and packages required for setting up an alternative pipeline.
2. Write python class objects and run scripts (either .py or .sh) that run the programs for SQL setup.
3. Write the SQL queries and files that load the .csv files and images to SQL tables, then constructs the RAG view.

### LLM Setup - FOSS
For FOSS pipeline only, write necessary files and run scripts (either .py or .sh) that run the LLM and perform equivalent operations to text-embeddings-large and gpt-4o for parsing natural language user queries and using RAG search on the vectorized database.

### PowerBI Power Query Construction
For both pipelines, write the Power Query that allows the user to access information and query the database for questions.

### PowerBI Dashboard Construction
Either create a generative script or leave this to be hand-crafted. 
