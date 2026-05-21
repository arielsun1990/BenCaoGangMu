# BenCaoGangMu
Toponyms in the Bencao Gangmu: A Digital Humanities Dataset
Overview
This dataset captures geographical knowledge embedded in Li Shizhen’s Bencao Gangmu (1596), a foundational text of classical Chinese materia medica. It contains every identifiable place name (toponym) mentioned in the text, along with its textual context, assigned category, and, where possible, its modern geographic coordinates. The data supports the computational analysis of spatial patterns in pre-modern pharmacological knowledge.

Data Collection and Processing
The source text was obtained from [specify digital edition, if applicable]. Using a combination of regular expression matching and manual verification, we extracted all occurrences of Chinese place names. Each toponym was then classified into a hierarchical typology: administrative regions (e.g., provinces, prefectures, counties), physical features (mountains, rivers, lakes), man-made locations (markets, temples, post stations), and mythical or uncertain places. Duplicates were removed, and orthographic variants (yitizi) were normalised.

Subsequently, a subset of place names was georeferenced using [specify gazetteer, e.g., CHGIS, CGA, or self-compiled reference] to obtain approximate latitude/longitude coordinates for spatial analysis.

Usage Notes
The dataset is formatted in UTF-8 CSV to ensure full compatibility with Chinese characters. Users can replicate our results by running the scripts in the order indicated in the repository’s README file. When a toponym could not be confidently georeferenced, its latitude and longitude fields are left empty, and the reason is recorded in the “notes” field. We encourage re-use for other digital humanities or historical GIS projects.
