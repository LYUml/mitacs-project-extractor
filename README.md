# Mitacs Project Extractor

[中文](README.zh-CN.md)

Extracts Mitacs Globalink project cards into clean CSV and JSON files. It supports the filters used by the website and reads ten projects per page.

```bash
pip install -r requirements.txt
python mitacs_extractor.py --output-dir data
```

```text
mitacs-project-extractor/
├── data/
│   ├── crawl_metadata.json
│   ├── mitacs_projects.csv
│   └── mitacs_projects.json
├── mitacs_extractor.py
├── requirements.txt
├── README.md
└── README.zh-CN.md
```
