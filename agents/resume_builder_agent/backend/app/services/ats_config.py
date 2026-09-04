SCORING_VERSION = "1.0.0"

JOB_MATCH_WEIGHTS = {
    "skills": 30,
    "context_relevance": 20,
    "experience": 15,
    "education_certifications": 10,
    "completeness": 10,
    "content_quality": 5,
    "parseability": 10,
}

QUALITY_WEIGHTS = {
    "section_completeness": 25,
    "content_clarity": 20,
    "bullet_quality": 20,
    "skills_organization": 15,
    "parseability": 15,
    "contact_quality": 5,
}

SKILL_ALIASES = {
    # Marketing and growth
    "seo": "SEO", "search engine optimization": "SEO",
    "sem": "SEM", "search engine marketing": "SEM",
    "google analytics": "Google Analytics", "ga4": "Google Analytics",
    "google ads": "Google Ads", "adwords": "Google Ads",
    "content marketing": "Content Marketing", "content strategy": "Content Strategy",
    "social media marketing": "Social Media Marketing", "social media": "Social Media Marketing",
    "email marketing": "Email Marketing", "crm": "CRM", "hubspot": "HubSpot",
    "campaign management": "Campaign Management", "brand management": "Brand Management",
    "marketing automation": "Marketing Automation", "copywriting": "Copywriting",
    "market research": "Market Research", "digital marketing": "Digital Marketing",
    "google tag manager": "Google Tag Manager", "wordpress": "WordPress",
    # Data and analytics
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "ms excel": "Microsoft Excel",
    "excel": "Microsoft Excel",
    "pivot tables": "Excel Pivot Tables", "excel pivot tables": "Excel Pivot Tables",
    "google sheets": "Google Sheets", "looker": "Looker", "looker studio": "Looker Studio",
    "statistics": "Statistics", "statistical analysis": "Statistical Analysis",
    "data visualization": "Data Visualization", "data visualisation": "Data Visualization",
    "data cleaning": "Data Cleaning", "etl": "ETL", "data warehousing": "Data Warehousing",
    "bigquery": "BigQuery", "big query": "BigQuery", "spss": "SPSS", "sas": "SAS",
    "predictive modeling": "Predictive Modeling", "predictive modelling": "Predictive Modeling",
    "regression analysis": "Regression Analysis", "r": "R",
    "mysql": "MySQL",
    "mysql database": "MySQL",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "powerbi": "Power BI",
    "power bi": "Power BI",
    "ms power bi": "Power BI",
    "python": "Python",
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "scikit learn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "sql": "SQL",
    "tableau": "Tableau",
    # Business, operations, sales, finance, and people teams
    "project management": "Project Management", "stakeholder management": "Stakeholder Management",
    "business analysis": "Business Analysis", "presentation skills": "Presentation Skills",
    "financial modeling": "Financial Modeling", "financial modelling": "Financial Modeling",
    "salesforce": "Salesforce", "jira": "Jira", "agile": "Agile", "scrum": "Scrum",
    "sales management": "Sales Management", "lead generation": "Lead Generation",
    "customer relationship management": "CRM", "account management": "Account Management",
    "business development": "Business Development", "operations management": "Operations Management",
    "supply chain management": "Supply Chain Management", "process improvement": "Process Improvement",
    "human resources": "Human Resources", "recruiting": "Recruiting", "talent acquisition": "Talent Acquisition",
    "payroll": "Payroll", "performance management": "Performance Management",
    "budgeting": "Budgeting", "forecasting": "Forecasting", "financial analysis": "Financial Analysis",
    # Design and product
    "figma": "Figma", "adobe photoshop": "Adobe Photoshop", "illustrator": "Adobe Illustrator",
    "ui design": "UI Design", "ux design": "UX Design", "user research": "User Research",
    "product management": "Product Management", "product strategy": "Product Strategy",
}

ACTION_VERBS = {
    "achieved", "analyzed", "automated", "built", "created", "delivered",
    "designed", "developed", "implemented", "improved", "led", "managed",
    "optimized", "reduced", "reported", "streamlined",
}

STOP_WORDS = {
    "a", "an", "and", "are", "as", "be", "by", "candidate", "for", "from",
    "have", "in", "is", "job", "of", "or", "our", "role", "the", "to",
    "with", "work", "you", "your",
}
