"""Банк шаблонов-генераторов заданий. Импорт модулей регистрирует шаблоны в REGISTRY."""
from __future__ import annotations

from dataclasses import replace

from app.testing.bank import algorithms, code_trace, data_ml, databases, extra, frontend_mobile, infra_qa_sec, web_arch  # noqa: F401
from app.testing.bank.base import REGISTRY, GenCtx, Template, check_answer, render  # noqa: F401


def alias(new_id: str, src_id: str, competency: str, specs: tuple[str, ...], level: int | None = None) -> None:
    """Повторное использование генератора в другой компетенции/специализации (общий навык)."""
    src = REGISTRY[src_id]
    REGISTRY[new_id] = replace(src, id=new_id, competency=competency, specs=specs, level=level or src.level)


# Общие для нескольких направлений навыки
alias("web.vuln_snippet", "sec.vuln_snippet", "web", ("backend", "qa"), 3)
alias("web.mitigation", "sec.mitigation", "web", ("backend", "frontend"), 3)
alias("web.jwt", "sec.jwt", "web", ("backend", "mobile"), 4)
alias("web.browser_security", "browser.security_storage", "web", ("backend", "mobile"), 3)
alias("ops.linux_chmod", "linux.chmod", "devops_basics", ("backend",), 1)
alias("ops.exit_codes", "linux.exit_codes", "devops_basics", ("backend",), 2)
alias("ops.k8s_facts", "k8s.facts", "devops_basics", ("backend",), 4)
alias("ops.semver", "ci.semver", "devops_basics", ("backend",), 2)
alias("arch.lru", "alg.lru_misses", "architecture", ("backend",), 3)
alias("mob.backoff", "arch.backoff", "architecture", ("mobile",), 3)
alias("mob.api_reliability", "http.api_reliability", "architecture", ("mobile",), 4)
alias("mob.caching", "arch.caching", "architecture", ("mobile",), 3)
alias("ml.bayes", "stats.bayes", "ml_math", ("ml",), 3)
alias("ml.impurity_math", "ml.impurity", "ml_math", ("ml",), 3)
alias("ml.ab_design", "stats.ab_design", "ml_theory", ("ml",), 4)
alias("da.simpson", "stats.simpson", "product_metrics", ("data_analyst",), 4)
alias("da.ab_test", "stats.ab_test", "product_metrics", ("data_analyst",), 3)
alias("da.viz_percentile", "stats.percentile", "visualization", ("data_analyst",), 2)
alias("sec.firewall_forensics", "net.firewall", "forensics", ("infosec",), 3)
alias("sec.cors", "http.cors_preflight", "web_security", ("infosec",), 3)
alias("sec.browser", "browser.security_storage", "web_security", ("infosec",), 2)
alias("sec.chmod_special", "linux.chmod_special", "forensics", ("infosec",), 3)
alias("qa.db_isolation", "db.lost_update", "databases", ("qa",), 4)
alias("qa.api_reliability", "http.api_reliability", "web", ("qa",), 3)
alias("qa.capacity", "arch.capacity", "performance", ("qa",), 4)
alias("devops.capacity", "arch.capacity", "sre", ("devops",), 4)
alias("devops.availability", "arch.availability", "sre", ("devops",), 3)
alias("devops.token_bucket", "arch.token_bucket", "sre", ("devops",), 4)
alias("devops.distributed", "arch.distributed", "containers", ("devops",), 4)
alias("devops.pipeline_ci", "linux.pipeline", "ci_cd", ("devops",), 2)
alias("devops.docker_cache", "docker.layer_cache", "ci_cd", ("devops",), 3)
alias("fe.jwt", "sec.jwt", "web", ("frontend",), 4)
alias("qa.jwt", "sec.jwt", "web", ("qa",), 4)


def all_templates() -> list[Template]:
    return list(REGISTRY.values())


def get_template(tid: str) -> Template:
    return REGISTRY[tid]
