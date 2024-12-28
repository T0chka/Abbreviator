# Abbreviation Table Generator

This Python app extracts abbreviations from Word documents and generates a table with their descriptions.

## Features:
- Parse documents to extract abbreviations.
- Generate abbreviation tables from input Word docs.
- CSV storage for previously used abbreviations.

## How to Run:
1. Extract abbreviations:
   ```bash
   python src/extract/extract_abbs.py

## Project structure:

abbreviation_app/
│
├── src/                     # Main application source code
│   ├── extract/             # Scripts for parsing docs and extracting abbreviations
│   │   └── extract_abbs.py  # Script to extract abbreviations (Step 1)
│   │
│   ├── process/             # Application logic for processing input docs
│   │   └── process_doc.py   # Main app logic to generate abbreviation table (Step 2)
│   │
│   └── utils/               # Utility functions (e.g., CSV handling, logging)
│       └── helpers.py       
│
├── tests/                   # Unit tests and debugging space
│   ├── test_extract.py      
│   ├── test_process.py      
│   └── sample_docs/         # Test Word docs for internal testing
│
├── data/                    # Stores abbreviation CSV dictionary (abb_dict)
│   └── abb_dict.csv         
│
├── requirements.txt         # Python dependencies
├── README.md                # Project overview and instructions
├── .gitignore               # Files to exclude from Git
├── LICENSE                  # Project license (optional)
└── main.py      



