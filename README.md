Overview
This dataset captures geographical knowledge embedded in Li Shizhen’s Bencao Gangmu (1596). It contains every identifiable place name mentioned in the text, along with its context, assigned category, and—where possible—modern geographic coordinates. The data supports computational analysis of spatial patterns in pre-modern pharmacological knowledge.

File Inventory
The repository is structured as follows:

File/Directory	Description
BenCaoGangMu.txt	Full digital text of the Bencao Gangmu used as the source for extraction.
extract_toponyms.py	Python script that performs rule-based extraction of Chinese place names from the source text. It generates raw_toponyms.csv.
disambiguation_rules.csv	Table of disambiguation rules (e.g., distinguishing place names from personal names or common nouns). Each row contains a pattern, a condition, and the action to be taken.
positive_context_keywords.csv	List of keywords (e.g., 山, 水, 州, 县) used to identify and validate toponym candidates during extraction and filtering.
raw_toponyms.csv	Output of extraction. Each row is a toponym occurrence, with columns: text_ID, chapter, entry_name, full_sentence, toponym, and annotator_notes.
analyze_toponyms.py	Main analysis script that reads raw_toponyms.csv, applies disambiguation rules and keyword matching, classifies toponyms (administrative, physical, man-made, mythical), and optionally performs georeferencing. Outputs cleaned_toponyms.csv and summary statistics.
cleaned_toponyms.csv	Final dataset used for statistical tests and mapping. Variables include: toponym_ID, normalised_name, category, subcategory, latitude, longitude, coordinate_source, confidence_level (high/medium/low), and notes.
make_figures.py	Python script to generate all figures and maps from cleaned_toponyms.csv (e.g., kernel density maps, bar charts of category frequency).
README.md	Documentation explaining the repository structure, required Python libraries, execution order, and how to reproduce the results.
Usage Notes

All text and data files are UTF-8 encoded to ensure full compatibility with Chinese characters.

Run the scripts in this order: (1) extract_toponyms.py, (2) analyze_toponyms.py, (3) make_figures.py. The disambiguation_rules.csv and positive_context_keywords.csv are called automatically within the pipeline.

For toponyms that could not be confidently georeferenced, latitude and longitude fields are left empty, and the reason is recorded in the “notes” column of cleaned_toponyms.csv.

The dataset is designed for reuse in other digital humanities or historical GIS studies. We encourage adaptation of the rule tables for different classical Chinese texts.
