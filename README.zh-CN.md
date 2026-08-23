# Mitacs 项目提取器

[English](README.md)

将 Mitacs Globalink 项目卡片导出为整洁的 CSV 和 JSON 文件，支持网站筛选条件，并按网页结构每页读取 10 个项目。

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
