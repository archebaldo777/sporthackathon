"""DevOps/SRE, сети, QA и информационная безопасность."""
from __future__ import annotations

import base64
import ipaddress
import math
import random
import string

from app.testing.bank.base import GenCtx, Variant, pick_distractors, scenario_single, single, statements_multi, template

OPS = ("devops",)
NET = ("devops", "infosec")
LNX = ("devops", "infosec")
QA = ("qa",)
SEC = ("infosec",)


# ================================================================== Linux
def _perm_str(bits: int) -> str:
    return "".join(c if bits & (1 << (8 - i)) else "-" for i, c in enumerate("rwxrwxrwx"))


@template("linux.chmod", "Linux: права доступа (chmod)", "linux", LNX + ("backend",), 1, "input", time_limit=120)
def linux_chmod(rng: random.Random, ctx: GenCtx) -> Variant:
    u, g, o = rng.choice([7, 6, 5, 4]), rng.choice([5, 4, 0, 6, 7]), rng.choice([4, 0, 5, 1])
    bits = (u << 6) | (g << 3) | o
    if rng.random() < 0.5:
        return Variant(text=f"Права файла в выводе `ls -l`: `-{_perm_str(bits)}`. Какой восьмеричной записи для chmod они соответствуют?",
                       kind="input", input_type="text", answer=[f"{u}{g}{o}", f"0{u}{g}{o}"])
    return Variant(text=f"После `chmod {u}{g}{o} file` какие права покажет `ls -l` (9 символов, без типа файла)?", kind="input",
                   input_type="text", answer=[_perm_str(bits)])


@template("linux.chmod_special", "Linux: SUID, SGID, sticky bit", "linux", LNX, 3, "input", time_limit=150)
def linux_chmod_special(rng: random.Random, ctx: GenCtx) -> Variant:
    special = rng.choice([1, 2, 3, 4, 5, 6, 7])
    u, g, o = rng.choice([7, 6, 5]), rng.randint(0, 7), rng.randint(0, 7)
    perms = list(_perm_str((u << 6) | (g << 3) | o))
    if special & 4:
        perms[2] = "s" if perms[2] == "x" else "S"
    if special & 2:
        perms[5] = "s" if perms[5] == "x" else "S"
    if special & 1:
        perms[8] = "t" if perms[8] == "x" else "T"
    return Variant(text=f"Права файла: `-{''.join(perms)}`. Запишите их в четырёхзначной восьмеричной форме для chmod.", kind="input",
                   input_type="text", answer=[f"{special}{u}{g}{o}"])


@template("linux.pipeline", "Linux: конвейеры команд", "linux", LNX, 2, "input", time_limit=180)
def linux_pipeline(rng: random.Random, ctx: GenCtx) -> Variant:
    levels = ["INFO", "WARN", "ERROR"]
    services = ["auth", "billing", "search", "api"]
    lines = [f"2026-10-0{rng.randint(1, 4)} {rng.choice(levels)} {rng.choice(services)} req={rng.randint(100, 999)}" for _ in range(rng.randint(10, 12))]
    form = rng.choice(["grep_c", "uniq", "awk"])
    if form == "grep_c":
        lv, sv = rng.choice(levels), rng.choice(services)
        cmd = f"grep {lv} app.log | grep -c {sv}"
        ans = sum(1 for ln in lines if lv in ln and sv in ln)
    elif form == "uniq":
        cmd = "awk '{print $3}' app.log | sort | uniq | wc -l"
        ans = len({ln.split()[2] for ln in lines})
    else:
        lv = rng.choice(levels)
        cmd = f"awk '$2 == \"{lv}\" {{print $3}}' app.log | sort -u | wc -l"
        ans = len({ln.split()[2] for ln in lines if ln.split()[1] == lv})
    return Variant(text=f"Файл app.log:\n\nЧто выведет команда `{cmd}`?", kind="input", input_type="number", answer=ans, code="\n".join(lines),
                   code_lang="text")


@template("linux.exit_codes", "Коды завершения процессов и сигналы", "linux", LNX + ("backend",), 2, "single", time_limit=120)
def linux_exit_codes(rng: random.Random, ctx: GenCtx) -> Variant:
    sig = rng.choice([("SIGKILL", 9), ("SIGTERM", 15), ("SIGINT", 2), ("SIGSEGV", 11)])
    code = 128 + sig[1]
    hints = {"SIGKILL": " (часто — OOM killer)", "SIGTERM": "", "SIGINT": "", "SIGSEGV": "", "SIGHUP": ""}
    ans = f"{sig[0]}{hints[sig[0]]}"
    others = [f"{s}{hints[s]}" for s in ["SIGKILL", "SIGTERM", "SIGINT", "SIGSEGV", "SIGHUP"] if s != sig[0]]
    return single(f"Контейнер завершился с кодом выхода {code}. Каким сигналом, скорее всего, был завершён процесс?", ans, rng.sample(others, 3))


@template("linux.facts", "Linux: процессы и файловая система", "linux", LNX, 2, "multi", time_limit=150, method="pool")
def linux_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "SIGKILL нельзя перехватить или проигнорировать",
        "Процесс-зомби уже завершился, но родитель ещё не прочитал его код возврата",
        "Жёсткая ссылка указывает на тот же inode, что и исходный файл",
        "Удалённый, но открытый процессом файл продолжает занимать место на диске",
        "Команда `ss -tlnp` показывает слушающие TCP-порты и процессы",
        "Load average учитывает процессы в состоянии ожидания ввода-вывода (D)",
    ]
    false_pool = [
        "SIGTERM всегда немедленно уничтожает процесс без возможности обработки",
        "Символическая ссылка продолжает работать после удаления целевого файла",
        "Процесс-зомби потребляет процессорное время",
        "Права 777 на каталог /tmp безопасны и без sticky bit",
        "Команда `df` показывает размер файлов в текущем каталоге",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


@template("linux.suid_privesc", "Linux: повышение привилегий", "linux", SEC, 3, "multi", time_limit=180, method="pool")
def linux_suid(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "`find / -perm -4000 -type f` находит файлы с установленным SUID",
        "SUID-бинарник выполняется с правами владельца файла",
        "Запись в /etc/sudoers.d от непривилегированного пользователя — критическая уязвимость",
        "`sudo -l` показывает, какие команды пользователь может выполнять через sudo",
        "Скрипт в cron, запускаемый от root и доступный на запись пользователю, — вектор повышения привилегий",
    ]
    false_pool = [
        "SUID на скриптах интерпретатора всегда учитывается современными ядрами Linux",
        "SGID на каталоге не влияет на группу создаваемых в нём файлов",
        "Права 4755 означают, что файл доступен на запись всем пользователям",
        "Sticky bit на файле позволяет запускать его с правами root",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


# ================================================================== сети
@template("net.cidr_hosts", "Сети: размер подсети CIDR", "networking", NET, 2, "input", time_limit=150)
def net_cidr_hosts(rng: random.Random, ctx: GenCtx) -> Variant:
    prefix = rng.randint(22, 29)
    net = ipaddress.ip_network(f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.0/{prefix}", strict=False)
    form = rng.choice(["hosts", "broadcast"])
    if form == "hosts":
        return Variant(text=f"Сколько адресов можно назначить узлам в подсети {net} (без адреса сети и широковещательного)?", kind="input",
                       input_type="number", answer=net.num_addresses - 2)
    return Variant(text=f"Какой широковещательный (broadcast) адрес у подсети {net}?", kind="input", input_type="text",
                   answer=[str(net.broadcast_address)])


@template("net.cidr_membership", "Сети: принадлежность адреса подсети", "networking", NET, 3, "single", time_limit=180)
def net_cidr_membership(rng: random.Random, ctx: GenCtx) -> Variant:
    prefix = rng.choice([20, 21, 22, 23, 26, 27])
    base = ipaddress.ip_address(f"192.168.{rng.randint(0, 255)}.{rng.randint(0, 255)}")
    net = ipaddress.ip_network(f"{base}/{prefix}", strict=False)
    inside = net.network_address + rng.randint(1, net.num_addresses - 2)
    outs = set()
    while len(outs) < 3:
        delta = rng.choice([net.num_addresses + rng.randint(0, 40), -rng.randint(1, 60), net.num_addresses * 2 + rng.randint(0, 9)])
        cand = net.network_address + delta if delta > 0 else net.network_address - (-delta)
        if cand not in net:
            outs.add(str(cand))
    return single(f"Какой из адресов принадлежит подсети {net}?", str(inside), list(outs))


PORTS = {"SSH": 22, "HTTP": 80, "HTTPS": 443, "DNS": 53, "PostgreSQL": 5432, "MySQL": 3306, "Redis": 6379, "SMTP": 25, "RDP": 3389,
         "MongoDB": 27017, "Kafka": 9092, "LDAP": 389}


@template("net.ports", "Стандартные порты сервисов", "networking", NET, 1, "single", time_limit=90)
def net_ports(rng: random.Random, ctx: GenCtx) -> Variant:
    svc = rng.choice(list(PORTS))
    if rng.random() < 0.5:
        others = [str(p) for s, p in PORTS.items() if s != svc]
        return single(f"Какой порт по умолчанию использует {svc}?", str(PORTS[svc]), rng.sample(others, 3))
    others = [s for s in PORTS if s != svc]
    return single(f"Какой сервис по умолчанию слушает порт {PORTS[svc]}?", svc, rng.sample(others, 3))


DNS_SCEN = [
    (["Указать IPv4-адрес для домена."], "A"),
    (["Указать IPv6-адрес для домена."], "AAAA"),
    (["Сделать www.example.ru псевдонимом example.ru."], "CNAME"),
    (["Указать почтовые серверы домена."], "MX"),
    (["Разместить SPF-политику или подтверждение владения доменом."], "TXT"),
    (["Получить доменное имя по IP-адресу (обратная зона)."], "PTR"),
]


@template("net.dns", "DNS: типы записей", "networking", NET, 2, "single", time_limit=90, method="pool")
def net_dns(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, DNS_SCEN, [a for _, a in DNS_SCEN] + ["NS", "SRV"], prefix="Какую DNS-запись использовать? ")


@template("net.facts", "Сетевые протоколы", "networking", NET, 3, "multi", time_limit=180, method="pool")
def net_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "TCP гарантирует доставку и порядок байтов, UDP — нет",
        "Маршрутизация по IP-адресам происходит на сетевом (3) уровне модели OSI",
        "TLS 1.3 сокращает рукопожатие до одного round-trip при новом соединении",
        "NAT позволяет многим устройствам выходить в интернет с одного публичного адреса",
        "Состояние TIME_WAIT возникает у стороны, первой закрывшей TCP-соединение",
        "DNS по умолчанию использует UDP, но может переходить на TCP для больших ответов",
    ]
    false_pool = [
        "UDP устанавливает соединение трёхсторонним рукопожатием",
        "MAC-адреса используются для маршрутизации между разными сетями в интернете",
        "HTTP/3 работает поверх TCP",
        "Адрес 10.0.0.1 является публичным и маршрутизируется в интернете",
        "Порт — это свойство IP-адреса сетевого уровня",
    ]
    return statements_multi(rng, ["Какие утверждения о сетях верны?"], true_pool, false_pool)


@template("net.firewall", "Межсетевой экран: порядок правил", "networking", NET, 3, "input", time_limit=210)
def net_firewall(rng: random.Random, ctx: GenCtx) -> Variant:
    nets = ["10.0.0.0/8", "10.1.0.0/16", "192.168.1.0/24", "0.0.0.0/0", "10.1.2.0/24"]
    ports = [22, 80, 443, 5432, None]
    rules = []
    for _ in range(rng.randint(4, 5)):
        rules.append((rng.choice(["ACCEPT", "DROP"]), rng.choice(nets), rng.choice(ports)))
    rules.append(("DROP", "0.0.0.0/0", None))
    src = ipaddress.ip_address(rng.choice(["10.1.2.15", "10.7.3.4", "192.168.1.20", "8.8.8.8", "10.1.9.9"]))
    port = rng.choice([22, 80, 443, 5432])
    hit = next(i for i, (_, n, p) in enumerate(rules, start=1) if src in ipaddress.ip_network(n) and (p is None or p == port))
    lines = "\n".join(f"{i}. {act:<6} src={n:<15} dport={p if p else 'any'}" for i, (act, n, p) in enumerate(rules, start=1))
    return Variant(text=f"Правила проверяются сверху вниз до первого совпадения. Пакет: src = {src}, TCP dport = {port}. Номер какого правила сработает?",
                   kind="input", input_type="number", answer=hit, code=lines, code_lang="text")


NMAP_SCEN = [
    (["Быстро просканировать TCP-порты полуоткрытым сканированием без завершения рукопожатия."], "nmap -sS"),
    (["Определить версии сервисов на открытых портах."], "nmap -sV"),
    (["Просканировать UDP-порты."], "nmap -sU"),
    (["Просканировать все 65535 TCP-портов."], "nmap -p-"),
    (["Определить операционную систему хоста по особенностям стека TCP/IP."], "nmap -O"),
]


@template("sec.nmap", "Разведка: сканирование nmap", "networking", SEC, 2, "single", time_limit=90, method="pool")
def sec_nmap(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, NMAP_SCEN, [a for _, a in NMAP_SCEN] + ["nmap -sn"], prefix="Какой ключ nmap подходит? ")


# ================================================================== контейнеры и оркестрация
@template("k8s.hpa", "Kubernetes: расчёт HPA", "containers", OPS, 3, "input", time_limit=150)
def k8s_hpa(rng: random.Random, ctx: GenCtx) -> Variant:
    cur = rng.randint(2, 8)
    target = rng.choice([50, 60, 70, 80])
    metric = rng.randint(30, 160)
    mx = rng.choice([10, 12, 15])
    desired = min(mx, max(1, math.ceil(cur * metric / target)))
    return Variant(text=f"HPA: сейчас {cur} реплик, средняя загрузка CPU {metric}% при целевой {target}%, maxReplicas = {mx}, minReplicas = 1. "
                   "Сколько реплик выставит HPA по формуле desired = ceil(current × currentMetric / targetMetric)?",
                   kind="input", input_type="number", answer=desired)


@template("k8s.qos", "Kubernetes: классы QoS подов", "containers", OPS, 3, "single", time_limit=150)
def k8s_qos(rng: random.Random, ctx: GenCtx) -> Variant:
    form = rng.choice(["guaranteed", "burstable", "besteffort", "burstable2"])
    cpu, mem = rng.choice(["250m", "500m", "1"]), rng.choice(["256Mi", "512Mi", "1Gi"])
    if form == "guaranteed":
        res = f"resources:\n  requests:\n    cpu: {cpu}\n    memory: {mem}\n  limits:\n    cpu: {cpu}\n    memory: {mem}"
        ans = "Guaranteed"
    elif form == "burstable":
        res = f"resources:\n  requests:\n    cpu: {cpu}\n    memory: {mem}\n  limits:\n    memory: {mem}"
        ans = "Burstable"
    elif form == "burstable2":
        res = f"resources:\n  requests:\n    memory: {mem}"
        ans = "Burstable"
    else:
        res = "resources: {}"
        ans = "BestEffort"
    return single("Под из одного контейнера с такими ресурсами. Какой класс QoS он получит?", ans,
                  [x for x in ["Guaranteed", "Burstable", "BestEffort", "Critical"] if x != ans], code=res, code_lang="yaml")


@template("k8s.facts", "Kubernetes: объекты и поведение", "containers", OPS, 3, "multi", time_limit=180, method="pool")
def k8s_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Неудачная liveness-проба приводит к перезапуску контейнера",
        "Неудачная readiness-проба исключает под из эндпоинтов Service, но не перезапускает его",
        "StatefulSet даёт подам стабильные имена и собственные тома",
        "Превышение memory limit приводит к OOMKill контейнера",
        "Превышение CPU limit приводит к троттлингу, а не к убийству контейнера",
        "Service типа ClusterIP доступен только внутри кластера",
    ]
    false_pool = [
        "Readiness-проба перезапускает контейнер при неудаче",
        "Превышение CPU limit приводит к немедленному убийству контейнера",
        "Deployment гарантирует стабильные сетевые имена подов",
        "ConfigMap предназначен для хранения паролей в зашифрованном виде",
        "Под может одновременно работать на нескольких нодах",
    ]
    return statements_multi(rng, ["Какие утверждения о Kubernetes верны?"], true_pool, false_pool)


@template("docker.ops_facts", "Docker в эксплуатации", "containers", OPS, 2, "multi", time_limit=150, method="pool")
def docker_ops_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Multi-stage сборка уменьшает размер финального образа",
        "Запуск процесса в контейнере не от root снижает последствия компрометации",
        "Каждая инструкция RUN создаёт новый слой",
        "Именованные тома (volumes) сохраняют данные после удаления контейнера",
        "HEALTHCHECK позволяет оркестратору понять, что приложение в контейнере работает",
    ]
    false_pool = [
        "Контейнер изолирован от хоста так же надёжно, как виртуальная машина с отдельным ядром",
        "Секреты безопасно передавать через ARG в Dockerfile",
        "Тег latest гарантирует воспроизводимость сборок",
        "EXPOSE автоматически публикует порт на хосте",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


# ================================================================== CI/CD
DEPLOY_SCEN = [
    (["Новая версия сначала получает 5% трафика, метрики сравниваются со старой.", "Постепенно увеличивать долю пользователей на новой версии."], "Canary"),
    (["Две идентичные среды, переключение трафика между ними одним действием.", "Мгновенный откат переключением балансировщика на старую среду."], "Blue-green"),
    (["Инстансы обновляются по одному, сервис остаётся доступным.", "Поды постепенно заменяются новыми без даунтайма."], "Rolling update"),
    (["Функциональность включается для части пользователей без нового деплоя.", "Код уже в продакшене, но фича выключена и включается конфигурацией."], "Feature flags"),
    (["Все старые инстансы останавливаются, затем запускаются новые.", "Самый простой способ с кратковременной недоступностью."], "Recreate"),
]


@template("ci.deploy_strategies", "Стратегии деплоя", "ci_cd", OPS, 2, "single", time_limit=90, method="pool")
def ci_deploy(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, DEPLOY_SCEN, [a for _, a in DEPLOY_SCEN] + ["Shadow traffic"], prefix="Как называется стратегия? ")


@template("ci.semver", "Семантическое версионирование", "ci_cd", OPS + ("backend", "qa"), 2, "single", time_limit=90)
def ci_semver(rng: random.Random, ctx: GenCtx) -> Variant:
    M, m, p = rng.randint(1, 5), rng.randint(0, 12), rng.randint(0, 9)
    change = rng.choice(["break", "feat", "fix"])
    txt = {"break": "удалили устаревший метод публичного API", "feat": "добавили новый необязательный параметр в API (обратно совместимо)",
           "fix": "исправили ошибку без изменения API"}[change]
    ans = {"break": f"{M + 1}.0.0", "feat": f"{M}.{m + 1}.0", "fix": f"{M}.{m}.{p + 1}"}[change]
    cands = [f"{M + 1}.0.0", f"{M}.{m + 1}.0", f"{M}.{m}.{p + 1}", f"{M}.{m + 1}.{p}", f"{M + 1}.{m}.{p}"]
    return single(f"Текущая версия библиотеки {M}.{m}.{p}. В новой версии {txt}. Какой номер версии корректен по SemVer?", ans,
                  pick_distractors(rng, ans, cands, 3))


@template("ci.iac_facts", "CI/CD и инфраструктура как код", "ci_cd", OPS, 3, "multi", time_limit=180, method="pool")
def ci_iac(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "terraform plan показывает изменения инфраструктуры без их применения",
        "Состояние Terraform (state) нужно хранить удалённо с блокировкой при командной работе",
        "Ansible-плейбуки должны быть идемпотентными: повторный запуск не меняет настроенную систему",
        "Секреты в CI следует хранить в защищённых переменных или vault, а не в репозитории",
        "Артефакт сборки стоит собирать один раз и продвигать по окружениям без пересборки",
    ]
    false_pool = [
        "terraform apply не изменяет инфраструктуру, а только проверяет синтаксис",
        "Хранить terraform.tfstate в git — лучшая практика для командной работы",
        "Для каждого окружения артефакт нужно пересобирать из исходников заново",
        "Ansible требует установки агента на каждый управляемый хост",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


# ================================================================== SRE
@template("sre.error_budget", "SRE: бюджет ошибок", "sre", OPS, 3, "input", time_limit=180)
def sre_error_budget(rng: random.Random, ctx: GenCtx) -> Variant:
    slo = rng.choice([99.0, 99.5, 99.9, 99.95])
    days = 30
    budget = (100 - slo) / 100 * days * 24 * 60
    incidents = [rng.randint(1, max(2, int(budget / 4))) for _ in range(rng.randint(1, 3))]
    left = budget - sum(incidents)
    return Variant(text=f"SLO доступности — {slo}% за {days} дней. За период уже были инциденты полной недоступности длительностью "
                   f"{', '.join(map(str, incidents))} мин. Сколько минут бюджета ошибок осталось (до десятых, может быть отрицательным)?",
                   kind="input", input_type="number", answer=round(left, 1), tolerance=0.11)


@template("sre.facts", "SRE: мониторинг и инциденты", "sre", OPS, 2, "multi", time_limit=150, method="pool")
def sre_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Четыре «золотых сигнала»: задержка, трафик, ошибки, насыщение",
        "Алерты лучше строить на симптомах, видимых пользователю, а не на всех внутренних причинах",
        "Перцентили задержки информативнее среднего при длинных хвостах распределения",
        "Postmortem проводится без поиска виноватых (blameless)",
        "Метод RED: rate, errors, duration — для сервисов, обрабатывающих запросы",
    ]
    false_pool = [
        "Среднее время ответа надёжнее p99 для оценки опыта пользователей",
        "SLA обычно строже внутреннего SLO",
        "Чем больше алертов, тем надёжнее система",
        "Бюджет ошибок нужно тратить только на инциденты, а не на релизы",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


# ================================================================== QA
@template("qa.boundary_values", "Анализ граничных значений", "test_design", QA, 1, "multi", time_limit=150)
def qa_boundary(rng: random.Random, ctx: GenCtx) -> Variant:
    a = rng.randint(1, 30)
    b = a + rng.randint(10, 80)
    field = rng.choice(["возраст пользователя", "количество товаров в заказе", "длина пароля", "сумма перевода, тыс. ₽"])
    correct = [a - 1, a, b, b + 1]
    wrong = [a + rng.randint(3, 6), (a + b) // 2, b - rng.randint(3, 6), 0 if a > 2 else b + 10]
    wrong = [w for w in dict.fromkeys(wrong) if w not in correct][:3]
    opts = [(str(x), True) for x in correct] + [(str(x), False) for x in wrong]
    return Variant(text=f"Поле «{field}» принимает целые значения от {a} до {b} включительно. Какие значения проверяются по технике граничных "
                   "значений (двухточечный подход: граница и ближайшее значение за ней)?", kind="multi", options=opts,
                   hint="Отметьте все подходящие")


@template("qa.equivalence", "Классы эквивалентности", "test_design", QA, 2, "input", time_limit=180)
def qa_equivalence(rng: random.Random, ctx: GenCtx) -> Variant:
    cuts = sorted(rng.sample(range(5, 90), rng.randint(2, 3)))
    names = ["тариф «Базовый»", "тариф «Стандарт»", "тариф «Плюс»", "тариф «Премиум»"]
    ranges = [f"от 0 до {cuts[0] - 1} — {names[0]}"]
    for i in range(1, len(cuts)):
        ranges.append(f"от {cuts[i - 1]} до {cuts[i] - 1} — {names[i]}")
    ranges.append(f"от {cuts[-1]} и выше — {names[len(cuts)]}")
    valid = len(cuts) + 1
    invalid = 2  # отрицательные числа и нечисловой ввод
    return Variant(text="Стоимость подписки зависит от возраста пользователя (целое число лет):\n\n" + "\n".join(f"• {r}" for r in ranges)
                   + "\n\nОтрицательные значения и нечисловой ввод должны отклоняться. Какое минимальное число тестов нужно, чтобы покрыть "
                   "каждый класс эквивалентности (допустимые и недопустимые) одним тестом?", kind="input", input_type="number", answer=valid + invalid)


@template("qa.pairwise", "Попарное тестирование (pairwise)", "test_design", QA, 3, "single", time_limit=180)
def qa_pairwise(rng: random.Random, ctx: GenCtx) -> Variant:
    params = [("Браузер", rng.randint(2, 5)), ("ОС", rng.randint(2, 4)), ("Язык интерфейса", rng.randint(2, 5))]
    sizes = sorted((n for _, n in params), reverse=True)
    ans = sizes[0] * sizes[1]
    full = sizes[0] * sizes[1] * sizes[2]
    cands = [str(full), str(sum(sizes)), str(sizes[0] * sizes[2] + 1), str(ans + sizes[2]), str(sizes[0] + sizes[1])]
    desc = ", ".join(f"{n} — {k} значения(й)" for n, k in params)
    return single(f"Параметры конфигурации: {desc}. Какое минимальное число тестов покрывает все пары значений любых двух параметров?",
                  str(ans), pick_distractors(rng, str(ans), cands, 3))


CONDITIONS = ["клиент авторизован", "сумма заказа выше порога", "есть промокод", "доставка за город", "товар на складе",
              "оплата картой", "клиент из программы лояльности", "заказ оформлен ночью", "первая покупка", "регион с особым налогом",
              "подписка активна", "устройство — мобильное"]
MULTI = [("способ доставки", ["курьер", "самовывоз", "пункт выдачи"]), ("тип клиента", ["физлицо", "ИП", "юрлицо"]),
         ("тариф", ["базовый", "стандарт", "премиум", "корпоративный"]), ("канал", ["сайт", "приложение", "колл-центр", "партнёр"])]


@template("qa.decision_table", "Таблица решений", "test_design", QA, 2, "input", time_limit=150)
def qa_decision_table(rng: random.Random, ctx: GenCtx) -> Variant:
    binary = rng.sample(CONDITIONS, rng.randint(2, 4))
    multi = rng.sample(MULTI, rng.randint(0, 2))
    conds = [f"«{c}» (да/нет)" for c in binary] + [f"«{n}» ({len(v)} варианта: {', '.join(v)})" for n, v in multi]
    rng.shuffle(conds)
    ans = 2 ** len(binary)
    for _, v in multi:
        ans *= len(v)
    return Variant(text="Скидка в интернет-магазине зависит от условий: " + "; ".join(conds) +
                   ". Сколько правил (столбцов) будет в полной таблице решений?", kind="input", input_type="number", answer=ans)


SEVERITY = [
    (["Приложение падает при нажатии «Оплатить» у всех пользователей."], "Блокирующий (blocker)"),
    (["Опечатка в названии компании на главной странице перед запуском рекламы."], "Незначительный (minor), высокий приоритет"),
    (["Отчёт в админке иногда строится на 2 секунды дольше обычного."], "Незначительный (minor), низкий приоритет"),
    (["Пользователи не могут восстановить пароль, но могут войти через соцсети."], "Критический/серьёзный (major)"),
]


@template("qa.severity_priority", "Серьёзность и приоритет дефекта", "qa_process", QA, 1, "single", time_limit=90, method="pool")
def qa_severity(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, SEVERITY, [a for _, a in SEVERITY] + ["Тривиальный (trivial), блокирующий приоритет"],
                           prefix="Как классифицировать дефект? ")


TEST_TYPES = [
    (["Быстрая проверка, что основные функции новой сборки работают и её можно тестировать дальше."], "Smoke-тестирование"),
    (["Проверка, что исправления и новые функции не сломали существующую функциональность."], "Регрессионное тестирование"),
    (["Проверка взаимодействия модулей через их интерфейсы."], "Интеграционное тестирование"),
    (["Проверка системы заказчиком на соответствие бизнес-требованиям перед приёмкой."], "Приёмочное тестирование (UAT)"),
    (["Проверка отдельной функции или класса в изоляции от зависимостей."], "Модульное (unit) тестирование"),
]


@template("qa.test_types", "Виды и уровни тестирования", "qa_process", QA, 1, "single", time_limit=90, method="pool")
def qa_test_types(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, TEST_TYPES, [a for _, a in TEST_TYPES] + ["Исследовательское тестирование"], prefix="Как называется вид тестирования? ")


@template("qa.process_facts", "Процессы QA", "qa_process", QA, 2, "multi", time_limit=150, method="pool")
def qa_process_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Верификация отвечает на вопрос «правильно ли мы делаем продукт», валидация — «тот ли продукт мы делаем»",
        "Пирамида тестирования предполагает больше unit-тестов, чем end-to-end",
        "Баг-репорт должен содержать шаги воспроизведения, фактический и ожидаемый результат",
        "Исчерпывающее тестирование в общем случае невозможно",
        "Раннее тестирование (shift-left) снижает стоимость исправления дефектов",
    ]
    false_pool = [
        "Если все тесты прошли, в продукте нет дефектов",
        "Приоритет дефекта всегда совпадает с его серьёзностью",
        "End-to-end тесты должны составлять основу пирамиды тестирования",
        "Регрессионное тестирование проводится только один раз перед релизом",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


@template("qa.flaky", "Нестабильные (flaky) автотесты", "qa_process", QA, 3, "multi", time_limit=180, method="pool")
def qa_flaky(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Фиксированные sleep вместо явных ожиданий условий — частая причина нестабильности UI-тестов",
        "Зависимость тестов от порядка запуска и общего состояния делает их нестабильными",
        "Тесты, обращающиеся к реальным внешним сервисам, могут падать по независящим от кода причинам",
        "Изоляция тестовых данных (уникальные данные на тест) снижает нестабильность",
        "Автоматические перезапуски скрывают, но не устраняют причину нестабильности",
    ]
    false_pool = [
        "Увеличение числа ретраев — лучший способ исправить flaky-тест",
        "Параллельный запуск тестов всегда снижает нестабильность",
        "Flaky-тесты безопасно игнорировать, если они проходят хотя бы в половине запусков",
        "Явные ожидания (explicit waits) делают тесты менее стабильными, чем sleep",
    ]
    return statements_multi(rng, ["Какие утверждения о нестабильных тестах верны?"], true_pool, false_pool)


@template("perf.little", "Нагрузочное тестирование: закон Литтла", "performance", QA + OPS, 3, "input", time_limit=180)
def perf_little(rng: random.Random, ctx: GenCtx) -> Variant:
    x = rng.choice([50, 80, 100, 120, 200])
    r = rng.choice([0.2, 0.5, 0.8, 1.0, 1.5])
    z = rng.choice([1, 2, 3, 5])
    n = math.ceil(x * (r + z))
    return Variant(text=f"Нужно подать нагрузку {x} запросов/с. Среднее время ответа — {r} с, «время на размышление» пользователя между "
                   f"запросами — {z} с. Сколько виртуальных пользователей нужно в закрытой модели нагрузки (закон Литтла, округлите вверх)?",
                   kind="input", input_type="number", answer=n)


PERF_TYPES = [
    (["Нагрузку постепенно увеличивают до отказа системы, чтобы найти предел."], "Стресс-тестирование"),
    (["Систему держат под типовой нагрузкой много часов, ищут утечки памяти и деградацию."], "Тестирование стабильности (soak/endurance)"),
    (["Резко подают кратковременный всплеск трафика, например при старте распродажи."], "Спайк-тестирование"),
    (["Проверяют, что система держит ожидаемую нагрузку с целевыми временами ответа."], "Нагрузочное тестирование"),
]


@template("perf.types", "Виды тестирования производительности", "performance", QA, 2, "single", time_limit=90, method="pool")
def perf_types(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, PERF_TYPES, [a for _, a in PERF_TYPES] + ["Объёмное тестирование"], prefix="Как называется вид тестирования? ")


# ================================================================== информационная безопасность
def _vuln_snippets(rng: random.Random):
    tbl = rng.choice(["users", "accounts", "orders"])
    col = rng.choice(["login", "email", "name"])
    param = rng.choice(["q", "name", "id", "search"])
    return [
        (f'query = "SELECT * FROM {tbl} WHERE {col} = \'" + request.args["{param}"] + "\'"\ncursor.execute(query)', "SQL-инъекция"),
        (f'el = document.getElementById("greeting");\nel.innerHTML = "Привет, " + new URLSearchParams(location.search).get("{param}");',
         "XSS (межсайтовый скриптинг)"),
        (f'filename = request.args["{param}"]\nreturn open("/var/app/uploads/" + filename).read()', "Path traversal (обход каталогов)"),
        (f'host = request.form["{param}"]\nos.system("ping -c 1 " + host)', "Инъекция команд ОС"),
        (f'url = request.args["{param}"]\nreturn requests.get(url, timeout=5).text', "SSRF"),
        (f'order = db.get_order(request.args["{param}"])\nreturn jsonify(order)  # без проверки владельца', "IDOR (небезопасная прямая ссылка на объект)"),
        (f'data = base64.b64decode(request.cookies["{param}"])\nsession = pickle.loads(data)', "Небезопасная десериализация"),
        (f'return redirect(request.args["{param}"])', "Open redirect"),
    ]


@template("sec.vuln_snippet", "Уязвимость во фрагменте кода", "web_security", SEC + ("backend",), 2, "single", time_limit=120)
def sec_vuln(rng: random.Random, ctx: GenCtx) -> Variant:
    snippets = _vuln_snippets(rng)
    code, ans = rng.choice(snippets)
    return single("Какая уязвимость присутствует во фрагменте?", ans, pick_distractors(rng, ans, [a for _, a in snippets] + ["CSRF"], 3),
                  code=code, code_lang="python" if "document." not in code else "javascript")


MITIGATIONS = [
    (["Как правильно защититься от SQL-инъекций?"], "Параметризованные запросы / prepared statements"),
    (["Основная защита от хранимой XSS?"], "Контекстное экранирование вывода и CSP"),
    (["Защита от CSRF в приложении с cookie-сессиями?"], "SameSite-cookie и CSRF-токены"),
    (["Защита от SSRF при загрузке файла по URL пользователя?"], "Allowlist адресов и запрет внутренних сетей/metadata"),
    (["Защита от перебора паролей на форме входа?"], "Rate limiting, блокировки и MFA"),
    (["Как хранить пароли пользователей в БД?"], "Медленный хеш с солью (Argon2/bcrypt)"),
]


@template("sec.mitigation", "Меры защиты от атак", "web_security", SEC + ("backend",), 2, "single", time_limit=90, method="pool")
def sec_mitigation(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, MITIGATIONS, [a for _, a in MITIGATIONS] + ["Шифрование ответа Base64", "Скрытие ошибок в логах"])


@template("sec.jwt", "Безопасность JWT и сессий", "web_security", SEC, 3, "multi", time_limit=180, method="pool")
def sec_jwt(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Сервер должен отклонять токены с alg: none",
        "При RS256 подмена алгоритма на HS256 с публичным ключом как секретом — известная атака (key confusion)",
        "Короткоживущий access-токен с refresh-токеном снижает ущерб от утечки",
        "Payload JWT не зашифрован — его может прочитать любой, у кого есть токен",
        "Проверка подписи должна выполняться до доверия любым claims",
    ]
    false_pool = [
        "Подпись JWT скрывает содержимое payload от клиента",
        "Клиент может доверять claim exp без проверки подписи",
        "Слабый секрет HS256 невозможно подобрать перебором",
        "JWT невозможно отозвать никаким способом",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)


@template("sec.encoding_detect", "Распознавание кодировок", "crypto", SEC, 1, "single", time_limit=90)
def sec_encoding(rng: random.Random, ctx: GenCtx) -> Variant:
    word = rng.choice(["flag", "secret", "admin", "password", "ctf_round", "fsp_cup", "token"]) + str(rng.randint(10, 99))
    scheme = rng.choice(["Base64", "Hex", "URL-encoding", "ROT13"])
    if scheme == "Base64":
        enc = base64.b64encode(word.encode()).decode()
    elif scheme == "Hex":
        enc = word.encode().hex()
    elif scheme == "URL-encoding":
        enc = "".join(f"%{b:02X}" for b in word.encode())
    else:
        enc = word.translate(str.maketrans(string.ascii_lowercase, string.ascii_lowercase[13:] + string.ascii_lowercase[:13]))
    return single(f"В каком виде представлена строка `{enc}`?", scheme, [s for s in ["Base64", "Hex", "URL-encoding", "ROT13", "SHA-1"] if s != scheme][:3])


@template("sec.xor", "XOR-шифрование", "crypto", SEC, 2, "input", time_limit=150)
def sec_xor(rng: random.Random, ctx: GenCtx) -> Variant:
    p, k = rng.randint(0x20, 0x7E), rng.randint(1, 255)
    c = p ^ k
    return Variant(text=f"Байт открытого текста 0x{p:02x} зашифрован XOR с байтом ключа и дал шифртекст 0x{c:02x}. Найдите байт ключа "
                   "(в шестнадцатеричном виде, например 0x3f).", kind="input", input_type="text", answer=[f"0x{k:02x}", f"{k:02x}"])


CAESAR_WORDS = ["defense", "protocol", "firewall", "kernel", "sandbox", "payload", "exploit", "monitor", "cipher", "gateway", "network",
                "session", "process", "registry", "backdoor", "malware", "phishing", "honeypot", "token", "packet", "router", "botnet"]


@template("sec.caesar", "Шифр Цезаря", "crypto", SEC, 2, "input", time_limit=150)
def sec_caesar(rng: random.Random, ctx: GenCtx) -> Variant:
    word = rng.choice(CAESAR_WORDS)
    s = rng.randint(1, 25)
    enc = "".join(chr((ord(ch) - 97 + s) % 26 + 97) for ch in word)
    return Variant(text=f"Слово зашифровано шифром Цезаря со сдвигом +{s} по латинскому алфавиту: `{enc}`. Расшифруйте его.",
                   kind="input", input_type="text", answer=[word])


@template("sec.hash_identify", "Определение хеш-функции по виду", "crypto", SEC, 2, "single", time_limit=90)
def sec_hash_identify(rng: random.Random, ctx: GenCtx) -> Variant:
    name, n = rng.choice([("MD5", 32), ("SHA-1", 40), ("SHA-256", 64), ("SHA-512", 128)])
    digest = "".join(rng.choice("0123456789abcdef") for _ in range(n))
    return single(f"Хеш в шестнадцатеричном виде длиной {n} символов: `{digest[:32]}{'…' if n > 32 else ''}`. Какая функция наиболее вероятна?",
                  name, [x for x in ["MD5", "SHA-1", "SHA-256", "SHA-512"] if x != name])


@template("sec.crypto_facts", "Криптография: применение примитивов", "crypto", SEC, 3, "multi", time_limit=180, method="pool")
def sec_crypto_facts(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Режим ECB раскрывает структуру данных: одинаковые блоки дают одинаковый шифртекст",
        "AES-GCM обеспечивает и конфиденциальность, и целостность",
        "HMAC подтверждает целостность и подлинность сообщения при общем секрете",
        "«Кузнечик» и «Магма» — блочные шифры стандарта ГОСТ Р 34.12-2015",
        "«Стрибог» — хеш-функция стандарта ГОСТ Р 34.11-2012",
        "Повторное использование nonce в AES-GCM с тем же ключом катастрофично для безопасности",
    ]
    false_pool = [
        "Base64 — алгоритм шифрования",
        "MD5 подходит для хранения паролей, если добавить соль",
        "Асимметричное шифрование обычно быстрее симметричного",
        "Хеширование — обратимое преобразование при знании алгоритма",
        "Один и тот же IV можно безопасно использовать для всех сообщений в режиме CBC",
    ]
    return statements_multi(rng, ["Какие утверждения о криптографии верны?"], true_pool, false_pool)


@template("sec.password_entropy", "Энтропия пароля", "crypto", SEC, 3, "input", time_limit=150)
def sec_entropy(rng: random.Random, ctx: GenCtx) -> Variant:
    if rng.random() < 0.35:
        dict_size, k = rng.choice([2048, 4096, 7776, 1024]), rng.randint(3, 7)
        bits = k * math.log2(dict_size)
        return Variant(text=f"Парольная фраза из {k} слов, каждое выбирается случайно и равновероятно из словаря на {dict_size} слов. "
                       "Какова её энтропия в битах (до десятых)?", kind="input", input_type="number", answer=round(bits, 1), tolerance=0.11)
    alpha = rng.choice([(26, "строчные латинские буквы"), (36, "строчные латинские буквы и цифры"), (62, "латинские буквы обоих регистров и цифры"),
                        (10, "только цифры"), (16, "шестнадцатеричные символы"), (94, "все печатные символы ASCII"), (52, "латинские буквы обоих регистров")])
    L = rng.randint(6, 24)
    bits = L * math.log2(alpha[0])
    return Variant(text=f"Пароль длиной {L} символов генерируется случайно и равновероятно; алфавит — {alpha[1]} ({alpha[0]} символов). "
                   "Какова его энтропия в битах (до десятых)?", kind="input", input_type="number", answer=round(bits, 1), tolerance=0.11)


@template("forensics.auth_log", "Анализ журнала аутентификации", "forensics", SEC, 3, "input", time_limit=210)
def forensics_auth_log(rng: random.Random, ctx: GenCtx) -> Variant:
    ips = [f"203.0.113.{rng.randint(2, 250)}", f"198.51.100.{rng.randint(2, 250)}", f"192.0.2.{rng.randint(2, 250)}", f"10.0.0.{rng.randint(2, 50)}"]
    users = ["root", "admin", "deploy", "ivan"]
    lines, fails = [], {ip: 0 for ip in ips}
    for i in range(rng.randint(12, 15)):
        ip = rng.choice(ips)
        ok = rng.random() < 0.3
        if not ok:
            fails[ip] += 1
        t = f"Oct  5 10:{10 + i:02d}:{rng.randint(0, 59):02d}"
        lines.append(f"{t} sshd[{rng.randint(1000, 9999)}]: {'Accepted' if ok else 'Failed'} password for {rng.choice(users)} from {ip} port {rng.randint(40000, 60000)}")
    form = rng.choice(["count", "threshold"])
    if form == "count":
        ip = max(fails, key=lambda k: (fails[k], k))
        q = f"Сколько неудачных попыток входа было с адреса {ip}?"
        ans = fails[ip]
    else:
        thr = rng.choice([2, 3])
        q = f"Со скольких разных IP-адресов было не менее {thr} неудачных попыток входа?"
        ans = sum(1 for v in fails.values() if v >= thr)
    return Variant(text=f"Фрагмент /var/log/auth.log:\n\n{q}", kind="input", input_type="number", answer=ans, code="\n".join(lines), code_lang="text")


MITRE = [
    (["Злоумышленник создаёт задачу в планировщике, чтобы сохранить доступ после перезагрузки."], "Persistence (закрепление)"),
    (["Дамп памяти процесса LSASS для извлечения учётных данных."], "Credential Access (доступ к учётным данным)"),
    (["Сканирование внутренней сети и перечисление доменных пользователей после проникновения."], "Discovery (разведка)"),
    (["Выгрузка архива с документами на внешний облачный диск."], "Exfiltration (эксфильтрация)"),
    (["Фишинговое письмо с вредоносным вложением сотруднику."], "Initial Access (первоначальный доступ)"),
    (["Подключение по RDP к соседнему серверу с украденной учётной записью."], "Lateral Movement (горизонтальное перемещение)"),
]


@template("forensics.mitre", "Тактики MITRE ATT&CK", "forensics", SEC, 3, "single", time_limit=120, method="pool")
def forensics_mitre(rng: random.Random, ctx: GenCtx) -> Variant:
    return scenario_single(rng, MITRE, [a for _, a in MITRE] + ["Impact (воздействие)"], prefix="К какой тактике ATT&CK относится действие? ")


@template("forensics.ir_facts", "Реагирование на инциденты", "forensics", SEC, 2, "multi", time_limit=150, method="pool")
def forensics_ir(rng: random.Random, ctx: GenCtx) -> Variant:
    true_pool = [
        "Перед выключением скомпрометированного хоста стоит снять дамп оперативной памяти",
        "Индикаторы компрометации (IoC) включают хеши файлов, IP-адреса и домены",
        "Сдерживание (containment) выполняется до полного устранения угрозы",
        "Синхронизация времени (NTP) на всех системах важна для корреляции событий",
        "Цепочка хранения улик (chain of custody) нужна для юридической значимости доказательств",
    ]
    false_pool = [
        "Первое действие при инциденте — переустановить ОС на всех серверах",
        "Логи можно не хранить централизованно, если они есть на каждом хосте",
        "Антивирус гарантирует обнаружение любых целевых атак",
        "Post-incident анализ проводится только при утечке персональных данных",
    ]
    return statements_multi(rng, ["Какие утверждения верны?"], true_pool, false_pool)
