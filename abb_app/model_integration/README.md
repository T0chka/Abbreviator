# LLM Integration for Medical Abbreviation Processing

This module provides a complete workflow for training and using Large Language Models (LLMs) to process medical abbreviations as example category. The workflow includes data extraction, cleaning, training/test set preparation, model fine-tuning, and testing.

## Overview

The workflow consists of several steps:
1. Extract abbreviations and contexts from medical documents
2. Clean and validate the extracted data
3. Split data into training and test sets
4. Fine-tune the LLM model
5. Test model performance

## Available Commands

### 1. Extract Abbreviations (`extract_abbs_word_to_csv`)
Extracts abbreviations, their descriptions, and usage contexts from Word documents.

```bash
python manage.py extract_abbs_word_to_csv \
--input-dir=abb_app/data/word_files \
--output-file=abb_app/data/abb_dict_with_contexts.csv \
--max-contexts=1 \
--context-window=50
```
This command:

- Scans abb_app/data/word_files by default or directory specified with `--input-dir` for .docx files.
- Extracts abbreviations and their descriptions from abbreviation tables.
- For each abbreviation, searches for occurrences in text with a specified `--context-window` (default 50 characters) up to `--max-contexts` per document (default 1).
- Saves results to abb_app/data/abb_dict_with_contexts.csv by default or specified with `--output-file`.

Note:
- The command uses `AbbreviationTableExtractor` class to extract abbreviations and their descriptions from the document's abbreviation table which must have specific formatting and title. 
- The `TextProcessor` class is used to extract text from Word documents and to find contexts for each abbreviation. 
Please refer to the code for more details.

### 2. Clean Abbreviations (`clean_abb_dict`)
Cleans and validates abbreviations, ensuring language consistency and removing invalid entries.

```bash
python manage.py clean_abb_dict \
--input-file=abb_app/data/abb_dict_with_contexts.csv \
--output-file=abb_app/data/abb_dict_cleaned.csv
```
This command:

- Reads abb_app/data/abb_dict_with_contexts.csv by default or csv file specified with `--input-file`.
- Removes mixed-language abbreviations, one-letter abbreviations, and abbreviations with < 2 capital letters.
- Split descriptions if needed to match the abbreviation's language (e.g., English descriptions for English abbreviations).
- Includes only description containing words starting with the letters of the abbreviation.
- Saves cleaned data to abb_app/data/abb_dict_cleaned.csv by default or to path specified with `--output-file`.

### 3. Split Data (`train_test_split`)
Splits the cleaned data into training and test sets.

```bash
python manage.py train_test_split \
--input-file=abb_app/data/abb_dict_cleaned.csv \
--seed=0 \
--test-size=0.02 \
--overlap-size=5 \
--train-file=abb_app/data/train_data.csv \
--test-file=abb_app/data/test_data.csv
```
This command:

- Reads abb_app/data/abb_dict_cleaned.csv by default or csv file specified with `--input-file`.
- Sets random seed for reproducibility with `--seed` (default 0).
- Splits data into training and test sets, using `--test-size` (default 0.02) to determine the proportion of data for testing.
- Includes `--overlap-size` (default 5) examples from the training set in the test set.
- Saves training data to abb_app/data/train_data.csv by default or to path specified with `--train-file`.
- Saves test data to abb_app/data/test_data.csv by default or to path specified with `--test-file`.

### 4. Fine-tune Model (`finetune_model`)
Fine-tunes an LLM model on the training data.

```bash
python manage.py finetune_model \
--ollama-host=http://192.168.1.165:11434 \
--train-file=abb_app/data/train_data.csv \
--base-model=deepseek-r1:32b \
--new-model-name=medical
```
This command:

- Reads abb_app/data/train_data.csv by default or csv file specified with `--train-file`.
- Finetunes the base model specified with `--base-model` (default 'deepseek-r1:32b') on the training data, by generating a model-specific Modelfile file (contains training examples, hyperparameters, and instructions).
- Sends the Modelfile to the Ollama API server specified with `--ollama-host` (default 'http://192.168.1.165:11434') to create a new fine-tuned model named `medical` by default or as specified with `--new-model-name`.

### 5. Test Model (`test_model`)
Tests the fine-tuned model on the test set.

```bash
python manage.py test_model \
--ollama-host=http://192.168.1.165:11434 \
--test-file=abb_app/data/test_data.csv \
--model-name=medical \
--temperature=0.6 \
--top-p=0.6
```
This command:

- Reads abb_app/data/test_data.csv by default or csv file specified with `--test-file`.
- Tests the fine-tuned model specified with `--model-name` (default 'medical') on the test data, by generating predictions for each example using the Ollama API server specified with `--ollama-host` (default 'http://192.168.1.165:11434') and the parameters specified with `--temperature` and `--top-p` (default 0.6).

Note:
- It tries to normalize the text to compare the predictions with the expected descriptions, but it may not always work, as the predictions may contain different words or phrasing but still be correct. So the true accuracy can be only assessed by human.

Best results were achieved with the `deepseek-r1:32b` model (accuracy around 70%) using a training set of 502 examples with default parameters. Other models (llama3.1, llama3.2, deepseek-r1:7b) were not able to learn the task (accuracy around 30% and below).

## Notes

- All commands use UTF-8 encoding for file operations
- All file paths are relative to the project root
- To experiment with abbreviations related to other categories, you can modify the prompt and instructions.
