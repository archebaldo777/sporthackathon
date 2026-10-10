"""Справочники платформы: направления (отрасли ИТ), специализации, грейды, компетенции, онтология навыков,
дисциплины ФСП. Справочник версионируется вместе с кодом и отдаётся фронтенду через GET /api/v1/catalog.
"""
from __future__ import annotations

CATALOG_VERSION = "2026.10"

# ---------------------------------------------------------------- направления (отрасль ИТ)
DIRECTIONS = {
    "development": "Разработка ПО",
    "data": "Данные и ИИ",
    "infra": "Инфраструктура",
    "quality": "Качество ПО",
    "security": "Кибербезопасность",
}

# ---------------------------------------------------------------- грейды
# Порог (cut) — минимальная способность θ (шкала IRT, N(0,1) для популяции ИТ-специалистов),
# center — типичный уровень грейда, с него стартует адаптивный тест.
GRADES = {
    "intern": {"name": "Стажёр", "order": 0, "cut": -2.0, "center": -1.5, "years": "до 1 года"},
    "junior": {"name": "Junior", "order": 1, "cut": -1.0, "center": -0.5, "years": "1–2 года"},
    "middle": {"name": "Middle", "order": 2, "cut": 0.0, "center": 0.5, "years": "2–5 лет"},
    "senior": {"name": "Senior", "order": 3, "cut": 1.0, "center": 1.5, "years": "5+ лет"},
}
GRADE_ORDER = ["intern", "junior", "middle", "senior"]

# ---------------------------------------------------------------- специализации
# blueprint — доля заданий по компетенциям в тесте (контентная балансировка CAT)
SPECIALIZATIONS: dict[str, dict] = {
    "backend": {
        "name": "Backend-разработка",
        "short": "Backend",
        "direction": "development",
        "langs": ["python", "java", "go", "javascript", "csharp", "kotlin", "php"],
        "blueprint": {"lang": 0.25, "algorithms": 0.15, "databases": 0.2, "web": 0.15, "architecture": 0.15, "devops_basics": 0.1},
        "core_skills": ["SQL", "PostgreSQL", "REST API", "Docker", "Git", "Linux", "Redis", "Kafka", "Микросервисы"],
    },
    "frontend": {
        "name": "Frontend-разработка",
        "short": "Frontend",
        "direction": "development",
        "langs": ["javascript"],
        "frameworks": ["react", "vue", "angular"],
        "blueprint": {"lang": 0.25, "css": 0.15, "browser": 0.15, "framework": 0.15, "web": 0.15, "algorithms": 0.15},
        "core_skills": ["JavaScript", "TypeScript", "React", "HTML", "CSS", "Webpack", "Vite", "REST API", "Git"],
    },
    "mobile": {
        "name": "Мобильная разработка",
        "short": "Mobile",
        "direction": "development",
        "langs": ["kotlin", "swift", "dart"],
        "blueprint": {"lang": 0.25, "mobile_platform": 0.3, "architecture": 0.15, "web": 0.1, "algorithms": 0.2},
        "core_skills": ["Kotlin", "Swift", "Android SDK", "iOS SDK", "Jetpack Compose", "SwiftUI", "Flutter", "REST API", "Git"],
    },
    "ml": {
        "name": "Data Science / ML",
        "short": "ML",
        "direction": "data",
        "langs": ["python"],
        "blueprint": {"ml_theory": 0.25, "ml_math": 0.25, "lang": 0.15, "statistics": 0.15, "databases": 0.1, "algorithms": 0.1},
        "core_skills": ["Python", "Машинное обучение", "scikit-learn", "PyTorch", "Pandas", "NumPy", "SQL", "Статистика"],
    },
    "data_analyst": {
        "name": "Аналитика данных",
        "short": "Data Analyst",
        "direction": "data",
        "langs": ["python"],
        "blueprint": {"databases": 0.3, "statistics": 0.25, "product_metrics": 0.2, "visualization": 0.1, "lang": 0.15},
        "core_skills": ["SQL", "Python", "Pandas", "A/B-тестирование", "Статистика", "Power BI", "Tableau", "Excel", "ClickHouse"],
    },
    "devops": {
        "name": "DevOps / SRE",
        "short": "DevOps",
        "direction": "infra",
        "langs": ["python"],
        "blueprint": {"linux": 0.2, "networking": 0.2, "containers": 0.2, "ci_cd": 0.15, "sre": 0.15, "lang": 0.1},
        "core_skills": ["Linux", "Docker", "Kubernetes", "CI/CD", "Terraform", "Ansible", "Prometheus", "Grafana", "Bash", "Сети"],
    },
    "qa": {
        "name": "QA / Тестирование",
        "short": "QA",
        "direction": "quality",
        "langs": ["python", "java", "javascript"],
        "blueprint": {"test_design": 0.3, "web": 0.2, "databases": 0.15, "qa_process": 0.15, "lang": 0.1, "performance": 0.1},
        "core_skills": ["Тест-дизайн", "Автотесты", "Pytest", "Selenium", "Postman", "SQL", "REST API", "JMeter", "Allure"],
    },
    "infosec": {
        "name": "Информационная безопасность",
        "short": "InfoSec",
        "direction": "security",
        "langs": ["python"],
        "blueprint": {"web_security": 0.25, "crypto": 0.2, "networking": 0.2, "linux": 0.15, "forensics": 0.2},
        "core_skills": ["OWASP", "Пентест", "Burp Suite", "Криптография", "Сети", "Linux", "SIEM", "Python", "Анализ инцидентов"],
    },
}

LANGS = {
    "python": "Python",
    "java": "Java",
    "go": "Go",
    "javascript": "JavaScript / TypeScript",
    "csharp": "C#",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "php": "PHP",
    "dart": "Dart (Flutter)",
}

# ---------------------------------------------------------------- компетенции (темы теста)
# verifies — навыки онтологии, которые подтверждаются результатом по компетенции.
COMPETENCIES: dict[str, dict] = {
    "lang": {"name": "Язык программирования", "verifies": []},  # навык зависит от выбранного языка
    "algorithms": {"name": "Алгоритмы и структуры данных", "verifies": ["Алгоритмы"]},
    "databases": {"name": "Базы данных и SQL", "verifies": ["SQL"]},
    "web": {"name": "HTTP и API", "verifies": ["REST API", "HTTP"]},
    "architecture": {"name": "Архитектура и проектирование", "verifies": ["System Design", "Микросервисы"]},
    "devops_basics": {"name": "Git, Docker, Linux", "verifies": ["Git", "Docker"]},
    "css": {"name": "Вёрстка и CSS", "verifies": ["CSS", "HTML"]},
    "browser": {"name": "Браузер и DOM", "verifies": ["DOM", "Web API"]},
    "framework": {"name": "UI-фреймворки", "verifies": []},  # зависит от фреймворка
    "mobile_platform": {"name": "Мобильные платформы", "verifies": []},  # зависит от платформы
    "ml_theory": {"name": "Машинное обучение", "verifies": ["Машинное обучение", "scikit-learn"]},
    "ml_math": {"name": "Метрики и математика ML", "verifies": ["Метрики ML"]},
    "statistics": {"name": "Статистика и A/B-тесты", "verifies": ["Статистика", "A/B-тестирование"]},
    "product_metrics": {"name": "Продуктовые метрики", "verifies": ["Продуктовая аналитика"]},
    "visualization": {"name": "Визуализация и BI", "verifies": ["Визуализация данных"]},
    "linux": {"name": "Linux и скрипты", "verifies": ["Linux", "Bash"]},
    "networking": {"name": "Сети", "verifies": ["Сети", "TCP/IP"]},
    "containers": {"name": "Контейнеры и оркестрация", "verifies": ["Docker", "Kubernetes"]},
    "ci_cd": {"name": "CI/CD и Git", "verifies": ["CI/CD", "Git"]},
    "sre": {"name": "SRE и мониторинг", "verifies": ["Мониторинг", "SRE"]},
    "test_design": {"name": "Тест-дизайн", "verifies": ["Тест-дизайн"]},
    "qa_process": {"name": "Процессы QA", "verifies": ["Процессы QA"]},
    "performance": {"name": "Нагрузочное тестирование", "verifies": ["Нагрузочное тестирование"]},
    "web_security": {"name": "Безопасность веб-приложений", "verifies": ["OWASP", "Веб-безопасность"]},
    "crypto": {"name": "Криптография", "verifies": ["Криптография"]},
    "forensics": {"name": "Анализ инцидентов", "verifies": ["Анализ инцидентов", "SIEM"]},
}

LANG_SKILL = {
    "python": "Python",
    "java": "Java",
    "go": "Go",
    "javascript": "JavaScript",
    "csharp": "C#",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "php": "PHP",
    "dart": "Dart",
}
FRAMEWORK_SKILL = {"react": "React", "vue": "Vue", "angular": "Angular"}
PLATFORM_SKILL = {"kotlin": "Android SDK", "swift": "iOS SDK", "dart": "Flutter"}

# ---------------------------------------------------------------- онтология навыков
# (каноническое имя, группа, синонимы, связанные навыки)
_SKILLS: list[tuple[str, str, list[str], list[str]]] = [
    # языки
    ("Python", "lang", ["python3", "питон", "py"], ["Django", "FastAPI", "Flask"]),
    ("Java", "lang", ["java se", "java ee", "джава"], ["Kotlin", "Spring"]),
    ("Kotlin", "lang", ["котлин"], ["Java"]),
    ("Go", "lang", ["golang", "го"], []),
    ("JavaScript", "lang", ["js", "javascript", "ecmascript", "es6", "джаваскрипт"], ["TypeScript", "Node.js"]),
    ("TypeScript", "lang", ["ts", "typescript"], ["JavaScript"]),
    ("C#", "lang", ["c sharp", "csharp", ".net", "dotnet", "asp.net"], ["Java"]),
    ("C++", "lang", ["cpp", "c plus plus", "плюсы"], ["C"]),
    ("C", "lang", ["си"], ["C++"]),
    ("PHP", "lang", ["php7", "php8"], ["Laravel", "Symfony"]),
    ("Swift", "lang", ["swiftui swift"], ["Objective-C"]),
    ("Objective-C", "lang", ["objc", "objective c"], ["Swift"]),
    ("Dart", "lang", [], ["Flutter"]),
    ("Rust", "lang", [], ["C++"]),
    ("Ruby", "lang", ["ruby on rails", "rails"], []),
    ("Scala", "lang", [], ["Java", "Spark"]),
    ("Bash", "lang", ["shell", "sh", "zsh", "shell-скрипты"], ["Linux"]),
    ("SQL", "db", ["sql", "t-sql", "pl/sql", "plpgsql"], ["PostgreSQL", "MySQL"]),
    # backend-фреймворки
    ("Django", "framework", ["django rest framework", "drf"], ["Python", "FastAPI"]),
    ("FastAPI", "framework", [], ["Python", "Django", "Flask"]),
    ("Flask", "framework", [], ["Python", "FastAPI"]),
    ("Spring", "framework", ["spring boot", "spring framework", "springboot"], ["Java", "Kotlin"]),
    ("Node.js", "framework", ["nodejs", "node", "express", "nestjs", "nest.js"], ["JavaScript", "TypeScript"]),
    ("Laravel", "framework", [], ["PHP"]),
    ("Symfony", "framework", [], ["PHP"]),
    ("gRPC", "tool", ["grpc", "protobuf"], ["REST API"]),
    ("GraphQL", "tool", ["graphql"], ["REST API"]),
    ("REST API", "concept", ["rest", "restful", "rest api", "openapi", "swagger"], ["HTTP", "GraphQL"]),
    ("HTTP", "concept", ["http/2", "https"], ["REST API"]),
    ("Микросервисы", "concept", ["microservices", "микросервисная архитектура", "микросервисы"], ["System Design"]),
    ("System Design", "concept", ["system design", "проектирование систем", "архитектура систем"], ["Микросервисы"]),
    ("Алгоритмы", "concept", ["алгоритмы и структуры данных", "algorithms", "структуры данных"], []),
    # базы данных и очереди
    ("PostgreSQL", "db", ["postgres", "postgresql", "psql", "постгрес"], ["SQL", "MySQL"]),
    ("MySQL", "db", ["mariadb"], ["SQL", "PostgreSQL"]),
    ("MongoDB", "db", ["mongo"], []),
    ("Redis", "db", [], ["Memcached"]),
    ("ClickHouse", "db", ["clickhouse", "кликхаус"], ["SQL"]),
    ("Elasticsearch", "db", ["elastic", "opensearch", "elk"], []),
    ("Oracle", "db", ["oracle db"], ["SQL"]),
    ("Kafka", "tool", ["apache kafka", "кафка"], ["RabbitMQ"]),
    ("RabbitMQ", "tool", ["rabbit"], ["Kafka"]),
    # frontend
    ("React", "framework", ["react.js", "reactjs", "react native"], ["Redux", "Next.js"]),
    ("Vue", "framework", ["vue.js", "vuejs", "vue3", "nuxt"], ["React"]),
    ("Angular", "framework", ["angularjs"], ["RxJS", "TypeScript"]),
    ("Redux", "tool", ["redux toolkit", "mobx", "zustand"], ["React"]),
    ("Next.js", "framework", ["nextjs"], ["React"]),
    ("RxJS", "tool", [], ["Angular"]),
    ("HTML", "lang", ["html5", "вёрстка", "верстка"], ["CSS"]),
    ("CSS", "lang", ["css3", "scss", "sass", "less", "tailwind", "flexbox"], ["HTML"]),
    ("Webpack", "tool", ["vite", "rollup", "esbuild"], ["Vite"]),
    ("Vite", "tool", [], ["Webpack"]),
    ("DOM", "concept", ["dom api"], ["Web API"]),
    ("Web API", "concept", ["browser api", "web apis"], ["DOM"]),
    ("Jest", "tool", ["vitest", "testing library"], []),
    ("Figma", "tool", [], []),
    # mobile
    ("Android SDK", "framework", ["android", "андроид"], ["Kotlin", "Jetpack Compose"]),
    ("iOS SDK", "framework", ["ios", "uikit", "айос"], ["Swift", "SwiftUI"]),
    ("Jetpack Compose", "framework", ["compose"], ["Android SDK"]),
    ("SwiftUI", "framework", [], ["iOS SDK"]),
    ("Flutter", "framework", [], ["Dart"]),
    ("Coroutines", "concept", ["kotlin coroutines", "корутины", "flow"], ["Kotlin"]),
    # data / ml
    ("Машинное обучение", "concept", ["machine learning", "ml", "машинное обучение", "мл"], ["Deep Learning", "scikit-learn"]),
    ("Deep Learning", "concept", ["глубокое обучение", "нейронные сети", "neural networks", "dl"], ["PyTorch", "TensorFlow"]),
    ("NLP", "concept", ["natural language processing", "обработка естественного языка", "llm", "трансформеры"], ["Deep Learning"]),
    ("Computer Vision", "concept", ["cv", "компьютерное зрение", "opencv"], ["Deep Learning"]),
    ("scikit-learn", "tool", ["sklearn", "scikit learn"], ["Машинное обучение"]),
    ("PyTorch", "tool", ["torch"], ["Deep Learning", "TensorFlow"]),
    ("TensorFlow", "tool", ["keras", "tf"], ["Deep Learning", "PyTorch"]),
    ("CatBoost", "tool", ["xgboost", "lightgbm", "градиентный бустинг"], ["Машинное обучение"]),
    ("Pandas", "tool", ["pandas", "пандас"], ["NumPy", "Python"]),
    ("NumPy", "tool", ["numpy"], ["Pandas"]),
    ("Spark", "tool", ["pyspark", "apache spark"], ["Hadoop"]),
    ("Hadoop", "tool", ["hdfs", "hive"], ["Spark"]),
    ("Airflow", "tool", ["apache airflow"], ["ETL"]),
    ("ETL", "concept", ["elt", "dwh", "хранилище данных"], ["Airflow"]),
    ("MLOps", "concept", ["mlflow", "kubeflow"], ["Машинное обучение"]),
    ("Метрики ML", "concept", ["roc-auc", "precision", "recall", "f1"], ["Машинное обучение"]),
    ("Статистика", "concept", ["математическая статистика", "статистический анализ", "statistics", "теория вероятностей"], ["A/B-тестирование"]),
    ("A/B-тестирование", "concept", ["a/b", "ab-тесты", "a/b тесты", "ab testing", "a/b-тесты", "a/b testing"], ["Статистика"]),
    ("Продуктовая аналитика", "concept", ["product analytics", "продуктовые метрики", "unit-экономика", "юнит-экономика"], ["A/B-тестирование"]),
    ("Визуализация данных", "concept", ["data visualization", "дашборды", "dashboards"], ["Power BI", "Tableau"]),
    ("Power BI", "tool", ["powerbi"], ["Визуализация данных", "Tableau"]),
    ("Tableau", "tool", [], ["Визуализация данных", "Power BI"]),
    ("Superset", "tool", ["apache superset", "datalens", "metabase"], ["Визуализация данных"]),
    ("Excel", "tool", ["google sheets", "эксель"], []),
    # devops
    ("Linux", "infra", ["unix", "ubuntu", "debian", "centos", "линукс"], ["Bash"]),
    ("Docker", "infra", ["docker-compose", "docker compose", "контейнеризация", "докер"], ["Kubernetes"]),
    ("Kubernetes", "infra", ["k8s", "кубернетес", "helm", "openshift"], ["Docker"]),
    ("CI/CD", "infra", ["ci", "cd", "gitlab ci", "github actions", "jenkins", "teamcity"], ["Git"]),
    ("Git", "tool", ["github", "gitlab", "bitbucket", "гит"], ["CI/CD"]),
    ("Terraform", "infra", ["iac", "infrastructure as code", "pulumi"], ["Ansible"]),
    ("Ansible", "infra", ["puppet", "chef", "saltstack"], ["Terraform"]),
    ("Prometheus", "infra", ["victoriametrics", "alertmanager"], ["Grafana", "Мониторинг"]),
    ("Grafana", "infra", [], ["Prometheus", "Мониторинг"]),
    ("Мониторинг", "concept", ["observability", "мониторинг", "логирование", "zabbix"], ["Prometheus", "SRE"]),
    ("SRE", "concept", ["site reliability", "slo", "sla"], ["Мониторинг"]),
    ("Nginx", "infra", ["haproxy", "envoy"], ["Linux"]),
    ("Сети", "concept", ["networking", "сетевые технологии", "компьютерные сети"], ["TCP/IP"]),
    ("TCP/IP", "concept", ["tcp", "udp", "dns", "osi"], ["Сети"]),
    ("Облака", "infra", ["aws", "gcp", "azure", "yandex cloud", "яндекс облако", "vk cloud", "cloud"], ["Kubernetes"]),
    # qa
    ("Тест-дизайн", "concept", ["тест дизайн", "техники тест-дизайна", "test design", "тест-кейсы", "чек-листы"], ["Ручное тестирование"]),
    ("Ручное тестирование", "concept", ["manual testing", "функциональное тестирование"], ["Тест-дизайн"]),
    ("Автотесты", "concept", ["автоматизация тестирования", "test automation", "автотестирование"], ["Pytest", "Selenium"]),
    ("Pytest", "tool", ["pytest", "unittest"], ["Автотесты", "Python"]),
    ("Selenium", "tool", ["selenide", "playwright", "cypress", "webdriver"], ["Автотесты"]),
    ("Postman", "tool", ["insomnia", "rest assured", "restassured"], ["REST API"]),
    ("JMeter", "tool", ["k6", "locust", "gatling", "яндекс.танк"], ["Нагрузочное тестирование"]),
    ("Нагрузочное тестирование", "concept", ["load testing", "performance testing", "нагрузочное"], ["JMeter"]),
    ("Allure", "tool", ["testops", "testrail", "qase"], ["Автотесты"]),
    ("Процессы QA", "concept", ["qa process", "жизненный цикл дефекта", "баг-трекинг", "jira"], ["Тест-дизайн"]),
    # security
    ("OWASP", "concept", ["owasp top 10", "owasp"], ["Веб-безопасность"]),
    ("Веб-безопасность", "concept", ["web security", "xss", "sql injection", "csrf", "безопасность веб-приложений"], ["OWASP"]),
    ("Пентест", "concept", ["pentest", "penetration testing", "тестирование на проникновение", "red team"], ["Burp Suite"]),
    ("Burp Suite", "tool", ["burp", "owasp zap", "zap"], ["Пентест"]),
    ("Криптография", "concept", ["cryptography", "шифрование", "pki", "tls"], []),
    ("SIEM", "tool", ["splunk", "max patrol", "maxpatrol", "elk siem", "wazuh"], ["Анализ инцидентов"]),
    ("Анализ инцидентов", "concept", ["incident response", "форензика", "forensics", "soc", "dfir"], ["SIEM"]),
    ("Reverse Engineering", "concept", ["реверс", "reverse", "ida pro", "ghidra"], ["C"]),
    ("CTF", "concept", ["capture the flag", "ctf"], ["Пентест"]),
    # общее
    ("Agile", "process", ["scrum", "kanban", "скрам"], []),
    ("ООП", "concept", ["oop", "объектно-ориентированное программирование", "solid"], []),
    ("Паттерны проектирования", "concept", ["design patterns", "gof", "паттерны"], ["ООП"]),
    ("Clean Architecture", "concept", ["чистая архитектура", "ddd", "mvvm", "mvi", "mvp"], ["Паттерны проектирования"]),
]

SKILLS: dict[str, dict] = {
    name: {"name": name, "group": group, "aliases": aliases, "related": related} for name, group, aliases, related in _SKILLS
}

# ---------------------------------------------------------------- дисциплины ФСП (официальный перечень)
FSP_DISCIPLINES: dict[str, dict] = {
    "algorithmic": {
        "name": "Алгоритмическое программирование",
        "relevance": {"backend": 0.9, "frontend": 0.6, "mobile": 0.6, "ml": 0.85, "data_analyst": 0.6, "devops": 0.5, "qa": 0.5, "infosec": 0.6},
        "skills": ["Алгоритмы"],  # конкретные языки подтверждает только стек результата, а не дисциплина
    },
    "product": {
        "name": "Продуктовое программирование",
        "relevance": {"backend": 1.0, "frontend": 1.0, "mobile": 1.0, "ml": 0.75, "data_analyst": 0.65, "devops": 0.75, "qa": 0.8, "infosec": 0.6},
        "skills": [],
    },
    "security": {
        "name": "Программирование систем информационной безопасности",
        "relevance": {"backend": 0.6, "frontend": 0.4, "mobile": 0.4, "ml": 0.4, "data_analyst": 0.4, "devops": 0.75, "qa": 0.55, "infosec": 1.0},
        "skills": ["CTF", "Веб-безопасность", "Криптография"],
    },
    "robotics": {
        "name": "Программирование робототехники",
        "relevance": {"backend": 0.55, "frontend": 0.35, "mobile": 0.6, "ml": 0.7, "data_analyst": 0.4, "devops": 0.5, "qa": 0.45, "infosec": 0.4},
        "skills": [],
    },
    "uav": {
        "name": "Программирование беспилотных авиационных систем",
        "relevance": {"backend": 0.55, "frontend": 0.35, "mobile": 0.6, "ml": 0.75, "data_analyst": 0.45, "devops": 0.5, "qa": 0.45, "infosec": 0.45},
        "skills": ["Computer Vision"],
    },
}

# Актуальность дисциплины для специализации. Все дисциплины ФСП равноценны (рейтинга дисциплин и турниров нет), но, как
# предложили организаторы, результат специалиста по ИБ на соревновании по ИБ релевантнее его же результата по робототехнике.
# Поэтому вклад результата умножается на коэффициент актуальности: три понятных уровня с мягким шагом — любой результат ФСП
# учитывается, непрофильный — с весом 0.6. Если стек решения совпадает с навыками запроса, результат считается профильным.
DISCIPLINE_FIT = {"profile": 1.0, "adjacent": 0.8, "other": 0.6}
DISCIPLINE_FIT_NAMES = {"profile": "профильная дисциплина", "adjacent": "смежная дисциплина", "other": "непрофильная дисциплина"}


def discipline_fit(discipline: str, spec: str | None) -> str:
    """profile | adjacent | other — по матрице relevance (≥ 0.85 — профильная, ≥ 0.55 — смежная)."""
    if not spec:
        return "profile"
    r = FSP_DISCIPLINES.get(discipline, {}).get("relevance", {}).get(spec)
    if r is None:
        return "adjacent"
    return "profile" if r >= 0.85 else "adjacent" if r >= 0.55 else "other"


FSP_LEVELS = {
    "regional": {"name": "Региональный", "weight": 1.0},
    "interregional": {"name": "Межрегиональный", "weight": 1.6},
    "national": {"name": "Всероссийский", "weight": 2.6},
    "international": {"name": "Международный", "weight": 3.2},
}

# ---------------------------------------------------------------- прочее
WORK_FORMATS = {"office": "Офис", "hybrid": "Гибрид", "remote": "Удалённо"}

DOMAINS = {
    "fintech": "Финтех и банки",
    "ecommerce": "E-commerce и ритейл",
    "gamedev": "Геймдев",
    "govtech": "Госсектор",
    "edtech": "Образование",
    "healthtech": "Медицина",
    "telecom": "Телеком",
    "industrial": "Промышленность",
    "media": "Медиа и развлечения",
    "logistics": "Логистика и транспорт",
    "security": "Кибербезопасность",
    "it_services": "ИТ-услуги и аутсорс",
}

TEAM_ROLES = {
    "developer": "Исполнитель",
    "mentor": "Ментор / наставник",
    "teamlead": "Тимлид",
    "techlead": "Техлид / архитектор",
    "pm": "Менеджер / владелец продукта",
}

SOFT_SKILLS = [
    "Коммуникабельность",
    "Работа в команде",
    "Лидерство",
    "Менторство",
    "Самоорганизация",
    "Ответственность",
    "Аналитическое мышление",
    "Обучаемость",
    "Публичные выступления",
    "Управление временем",
    "Критическое мышление",
    "Стрессоустойчивость",
]

SEARCH_STATUSES = {
    "active": "Активно ищу работу",
    "open": "Открыт к предложениям",
    "not_looking": "Не ищу (скрыт из поиска)",
}

DECLINE_REASONS = {
    "salary": "Не устраивает зарплата",
    "format": "Не подходит формат работы",
    "domain": "Неинтересна сфера / продукт",
    "stack": "Не подходит стек",
    "timing": "Сейчас не ищу",
    "company": "Не интересна компания",
    "other": "Другое",
}

# Медианы рыночных зарплат (₽/мес, gross), по открытым обзорам рынка 2025–2026 — для подсказок и антифрода
MARKET_SALARY: dict[str, dict[str, int]] = {
    "backend": {"intern": 60000, "junior": 120000, "middle": 250000, "senior": 400000},
    "frontend": {"intern": 55000, "junior": 110000, "middle": 230000, "senior": 370000},
    "mobile": {"intern": 60000, "junior": 120000, "middle": 250000, "senior": 400000},
    "ml": {"intern": 70000, "junior": 140000, "middle": 280000, "senior": 450000},
    "data_analyst": {"intern": 55000, "junior": 100000, "middle": 190000, "senior": 320000},
    "devops": {"intern": 60000, "junior": 120000, "middle": 260000, "senior": 420000},
    "qa": {"intern": 45000, "junior": 80000, "middle": 170000, "senior": 280000},
    "infosec": {"intern": 60000, "junior": 120000, "middle": 240000, "senior": 380000},
}

CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород", "Самара",
    "Ростов-на-Дону", "Краснодар", "Томск", "Пермь", "Воронеж", "Уфа", "Иннополис", "Владивосток", "Калининград",
    "Челябинск", "Омск", "Красноярск", "Волгоград", "Саратов", "Тюмень", "Ижевск", "Барнаул", "Ульяновск", "Иркутск",
    "Хабаровск", "Ярославль", "Махачкала", "Оренбург", "Кемерово", "Рязань", "Астрахань", "Пенза", "Липецк", "Киров",
    "Тула", "Чебоксары", "Курск", "Ставрополь", "Сочи", "Белгород", "Владимир", "Архангельск", "Калуга", "Смоленск",
    "Мурманск", "Петрозаводск", "Сургут", "Якутск", "Севастополь", "Симферополь", "Таганрог", "Великий Новгород", "Псков",
    "Тверь", "Иваново", "Брянск", "Орёл", "Тамбов", "Курган", "Сыктывкар", "Йошкар-Ола", "Набережные Челны", "Тольятти",
    "Магнитогорск", "Новокузнецк", "Новороссийск", "Зеленоград", "Долгопрудный", "Королёв", "Обнинск", "Дубна",
]
# англоязычные и разговорные написания городов (резюме на английском, «Питер», «СПб»)
CITY_ALIASES = {
    "Moscow": "Москва", "Saint Petersburg": "Санкт-Петербург", "Saint-Petersburg": "Санкт-Петербург", "St. Petersburg": "Санкт-Петербург",
    "St Petersburg": "Санкт-Петербург", "SPb": "Санкт-Петербург", "СПб": "Санкт-Петербург", "Питер": "Санкт-Петербург",
    "Novosibirsk": "Новосибирск", "Yekaterinburg": "Екатеринбург", "Ekaterinburg": "Екатеринбург", "Kazan": "Казань",
    "Nizhny Novgorod": "Нижний Новгород", "Samara": "Самара", "Rostov-on-Don": "Ростов-на-Дону", "Krasnodar": "Краснодар",
    "Tomsk": "Томск", "Perm": "Пермь", "Voronezh": "Воронеж", "Ufa": "Уфа", "Innopolis": "Иннополис", "Vladivostok": "Владивосток",
    "Kaliningrad": "Калининград", "Chelyabinsk": "Челябинск", "Omsk": "Омск", "Krasnoyarsk": "Красноярск", "Tula": "Тула",
    "Makhachkala": "Махачкала", "Tyumen": "Тюмень", "Irkutsk": "Иркутск", "Yaroslavl": "Ярославль", "Sochi": "Сочи",
}


def grade_name(code: str | None) -> str:
    return GRADES[code]["name"] if code in GRADES else "—"


def spec_name(code: str | None) -> str:
    return SPECIALIZATIONS[code]["name"] if code in SPECIALIZATIONS else "—"


def category_label(spec: str | None, grade: str | None) -> str:
    if not spec or not grade:
        return "Категория не присвоена"
    return f"{SPECIALIZATIONS[spec]['short']} · {GRADES[grade]['name']}"


def competency_skills(competency: str, lang: str | None = None, spec: str | None = None, framework: str | None = None) -> list[str]:
    """Какие навыки подтверждает хороший результат по компетенции (с учётом трека кандидата)."""
    base = list(COMPETENCIES.get(competency, {}).get("verifies", []))
    if competency == "lang" and lang in LANG_SKILL:
        base.append(LANG_SKILL[lang])
        if lang == "javascript":
            base.append("TypeScript")
    if competency == "framework" and framework in FRAMEWORK_SKILL:
        base.append(FRAMEWORK_SKILL[framework])
    if competency == "mobile_platform" and lang in PLATFORM_SKILL:
        base.append(PLATFORM_SKILL[lang])
    return base


def public_catalog() -> dict:
    return {
        "version": CATALOG_VERSION,
        "directions": [{"code": k, "name": v} for k, v in DIRECTIONS.items()],
        "specializations": [
            {
                "code": k,
                "name": v["name"],
                "short": v["short"],
                "direction": v["direction"],
                "langs": v["langs"],
                "frameworks": v.get("frameworks", []),
                "blueprint": v["blueprint"],
                "core_skills": v["core_skills"],
            }
            for k, v in SPECIALIZATIONS.items()
        ],
        "grades": [{"code": k, **{kk: vv for kk, vv in v.items() if kk in ("name", "order", "years")}} for k, v in GRADES.items()],
        "langs": [{"code": k, "name": v} for k, v in LANGS.items()],
        "competencies": [{"code": k, "name": v["name"]} for k, v in COMPETENCIES.items()],
        "skills": [{"name": s["name"], "group": s["group"]} for s in SKILLS.values()],
        "fsp_disciplines": [{"code": k, "name": v["name"]} for k, v in FSP_DISCIPLINES.items()],
        "fsp_levels": [{"code": k, "name": v["name"]} for k, v in FSP_LEVELS.items()],
        "work_formats": [{"code": k, "name": v} for k, v in WORK_FORMATS.items()],
        "domains": [{"code": k, "name": v} for k, v in DOMAINS.items()],
        "team_roles": [{"code": k, "name": v} for k, v in TEAM_ROLES.items()],
        "soft_skills": SOFT_SKILLS,
        "search_statuses": [{"code": k, "name": v} for k, v in SEARCH_STATUSES.items()],
        "decline_reasons": [{"code": k, "name": v} for k, v in DECLINE_REASONS.items()],
        "market_salary": MARKET_SALARY,
        "cities": CITIES,
    }
