from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "database.db"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE_DIR / "uploads"))
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "png", "jpg", "jpeg"}
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "sim",
}
SINGLE_USER_NAME = "Administrador"
SINGLE_USER_LOGIN = "testebnb"
SINGLE_USER_PASSWORD = "bnb123"

CONTRACT_TYPES = [
    "Licitação",
    "Contratação direta",
    "Dispensa",
    "Inexigibilidade",
    "Adesão à ata",
    "Registro de preço",
    "Remanescente",
]

PROCESS_STATUSES = [
    "Em elaboração",
    "Pendências",
    "Aguardando validação",
    "Corrigir",
    "Concluído",
]

ITEM_STATUSES = ["Não iniciado", "Pendente", "Anexado", "Validado", "Não se aplica"]
VALIDATION_STATUSES = [
    "Pendente",
    "Enviado",
    "Em análise",
    "Aprovado",
    "Reprovado",
    "Corrigir",
    "Não se aplica",
]
MODEL_STATUSES = ["Ativo", "Substituído", "Inativo"]
USER_ROLES = ["Administrador", "Analista", "Solicitante"]


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Solicitante',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_number TEXT NOT NULL UNIQUE,
    unit_id INTEGER NOT NULL,
    object TEXT NOT NULL,
    contract_type TEXT NOT NULL,
    estimated_value REAL NOT NULL DEFAULT 0,
    engineering_service INTEGER NOT NULL DEFAULT 0,
    common_acquisition INTEGER NOT NULL DEFAULT 0,
    emergency INTEGER NOT NULL DEFAULT 0,
    outside_capgv INTEGER NOT NULL DEFAULT 0,
    dispensa_por_valor INTEGER NOT NULL DEFAULT 0,
    exceeds_authority INTEGER NOT NULL DEFAULT 0,
    requires_contract INTEGER NOT NULL DEFAULT 0,
    responsible TEXT NOT NULL,
    opening_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Em elaboração',
    legal_foundation TEXT,
    estimate_source TEXT,
    price_research_responsible TEXT,
    quotation_date TEXT,
    proposal_value REAL,
    supplier TEXT,
    proposal_registered_system INTEGER NOT NULL DEFAULT 0,
    proposal_history TEXT,
    budget_allocation TEXT,
    budget_source TEXT,
    budget_availability TEXT,
    budget_unit TEXT,
    expense_nature TEXT,
    controller_opinion TEXT,
    price_research_summary TEXT,
    reference_documents TEXT,
    external_consultations TEXT,
    committee_meeting_date TEXT,
    committee_record_number TEXT,
    chief_fiscal TEXT,
    substitute_fiscal TEXT,
    contract_manager TEXT,
    designation_document_generated INTEGER NOT NULL DEFAULT 0,
    proposal_generated INTEGER NOT NULL DEFAULT 0,
    proposal_notes TEXT,
    conclusion_date TEXT,
    conclusion_summary TEXT,
    final_responsible TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(unit_id) REFERENCES units(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS checklist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    demand_id INTEGER NOT NULL,
    document_name TEXT NOT NULL,
    applicability TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 0,
    model_available INTEGER NOT NULL DEFAULT 0,
    model_name TEXT,
    status TEXT NOT NULL DEFAULT 'Não iniciado',
    observation TEXT,
    responsible_send TEXT,
    responsible_validate TEXT,
    validation_status TEXT NOT NULL DEFAULT 'Pendente',
    validation_observation TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(demand_id) REFERENCES demands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_item_id INTEGER NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    uploaded_by INTEGER,
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT,
    deleted_by INTEGER,
    deletion_reason TEXT,
    FOREIGN KEY(checklist_item_id) REFERENCES checklist_items(id) ON DELETE CASCADE,
    FOREIGN KEY(uploaded_by) REFERENCES users(id),
    FOREIGN KEY(deleted_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS document_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    document_type TEXT NOT NULL,
    version TEXT NOT NULL,
    applicability TEXT NOT NULL,
    original_filename TEXT,
    stored_filename TEXT,
    status TEXT NOT NULL DEFAULT 'Ativo',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_item_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    observation TEXT,
    validator_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(checklist_item_id) REFERENCES checklist_items(id) ON DELETE CASCADE,
    FOREIGN KEY(validator_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS disbursements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    demand_id INTEGER NOT NULL,
    installment INTEGER NOT NULL,
    expected_month TEXT NOT NULL,
    expected_value REAL NOT NULL DEFAULT 0,
    percent REAL NOT NULL DEFAULT 0,
    observation TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(demand_id) REFERENCES demands(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS applicability_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_name TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    force_required INTEGER NOT NULL DEFAULT 0,
    force_not_applicable INTEGER NOT NULL DEFAULT 0,
    requires_justification INTEGER NOT NULL DEFAULT 0,
    requires_standard_model INTEGER NOT NULL DEFAULT 0,
    requires_superior_approval INTEGER NOT NULL DEFAULT 0,
    custom_applicability TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    user_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_demands_status ON demands(status);
CREATE INDEX IF NOT EXISTS idx_demands_unit ON demands(unit_id);
CREATE INDEX IF NOT EXISTS idx_checklist_demand ON checklist_items(demand_id);
CREATE INDEX IF NOT EXISTS idx_documents_item ON documents(checklist_item_id);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


DEMAND_EXTRA_COLUMNS = {
    "price_research_summary": "TEXT",
    "reference_documents": "TEXT",
    "external_consultations": "TEXT",
    "committee_meeting_date": "TEXT",
    "committee_record_number": "TEXT",
    "chief_fiscal": "TEXT",
    "substitute_fiscal": "TEXT",
    "contract_manager": "TEXT",
    "designation_document_generated": "INTEGER NOT NULL DEFAULT 0",
    "proposal_generated": "INTEGER NOT NULL DEFAULT 0",
    "proposal_notes": "TEXT",
    "conclusion_date": "TEXT",
    "conclusion_summary": "TEXT",
    "final_responsible": "TEXT",
}


CHECKLIST_DOCUMENTS = [
    "Formalização da Demanda",
    "Estudos Preliminares",
    "Mapa de Riscos",
    "Projeto Básico / Termo de Referência",
    "Proposta de Licitação / Contratação",
    "Fundamentação",
    "Estimativa de Preços",
    "Situação Orçamentária da Proposta",
    "Cronograma de Desembolso",
    "Ata do Comitê Gestor da Super do Demandante",
    "Termo de Designação de Acompanhamento e Fiscalização do Contrato",
    "Parecer Jurídico",
    "Anexos Técnicos",
    "Declaração de Vedação ao Nepotismo",
    "Checklist da Licitação ou Contratação",
]


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_schema_migrations(db: sqlite3.Connection) -> None:
    for column, definition in DEMAND_EXTRA_COLUMNS.items():
        ensure_column(db, "demands", column, definition)


def seed_applicability_rules(db: sqlite3.Connection) -> None:
    rules = []
    standard_model_docs = {
        "Formalização da Demanda",
        "Estudos Preliminares",
        "Mapa de Riscos",
        "Projeto Básico / Termo de Referência",
        "Termo de Designação de Acompanhamento e Fiscalização do Contrato",
        "Declaração de Vedação ao Nepotismo",
    }
    justification_docs = {"Estudos Preliminares", "Mapa de Riscos"}
    superior_docs = {"Ata do Comitê Gestor da Super do Demandante"}
    for document_name in CHECKLIST_DOCUMENTS:
        rules.append(
            (
                document_name,
                1 if document_name in justification_docs else 0,
                1 if document_name in standard_model_docs else 0,
                1 if document_name in superior_docs else 0,
            )
        )
    db.executemany(
        """
        INSERT OR IGNORE INTO applicability_rules (
            document_name, requires_justification, requires_standard_model,
            requires_superior_approval
        )
        VALUES (?, ?, ?, ?)
        """,
        rules,
    )


def enforce_single_user(db: sqlite3.Connection) -> int:
    user = db.execute(
        "SELECT id FROM users WHERE email = ?", (SINGLE_USER_LOGIN,)
    ).fetchone()
    password_hash = generate_password_hash(SINGLE_USER_PASSWORD)
    if user is None:
        cursor = db.execute(
            """
            INSERT INTO users (name, email, password_hash, role, active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (SINGLE_USER_NAME, SINGLE_USER_LOGIN, password_hash, "Administrador"),
        )
        user_id = cursor.lastrowid
    else:
        user_id = user["id"]
        db.execute(
            """
            UPDATE users
            SET name = ?,
                password_hash = ?,
                role = 'Administrador',
                active = 1
            WHERE id = ?
            """,
            (SINGLE_USER_NAME, password_hash, user_id),
        )

    db.execute(
        "UPDATE demands SET created_by = ? WHERE created_by IS NOT NULL AND created_by != ?",
        (user_id, user_id),
    )
    db.execute(
        "UPDATE documents SET uploaded_by = ? WHERE uploaded_by IS NOT NULL AND uploaded_by != ?",
        (user_id, user_id),
    )
    db.execute(
        "UPDATE documents SET deleted_by = ? WHERE deleted_by IS NOT NULL AND deleted_by != ?",
        (user_id, user_id),
    )
    db.execute(
        "UPDATE validations SET validator_id = ? WHERE validator_id IS NOT NULL AND validator_id != ?",
        (user_id, user_id),
    )
    db.execute(
        "UPDATE history SET user_id = ? WHERE user_id IS NOT NULL AND user_id != ?",
        (user_id, user_id),
    )
    db.execute("DELETE FROM users WHERE id != ?", (user_id,))
    return user_id


def init_db() -> None:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE) as db:
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        ensure_schema_migrations(db)
        seed_applicability_rules(db)

        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            db.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (
                    SINGLE_USER_NAME,
                    SINGLE_USER_LOGIN,
                    generate_password_hash(SINGLE_USER_PASSWORD),
                    "Administrador",
                ),
            )

        existing_login = db.execute(
            "SELECT id FROM users WHERE email = ?", (SINGLE_USER_LOGIN,)
        ).fetchone()
        if existing_login is None:
            db.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (
                    SINGLE_USER_NAME,
                    SINGLE_USER_LOGIN,
                    generate_password_hash(SINGLE_USER_PASSWORD),
                    "Administrador",
                ),
            )
        else:
            db.execute(
                """
                UPDATE users
                SET password_hash = ?, role = 'Administrador', active = 1
                WHERE email = ?
                """,
                (generate_password_hash(SINGLE_USER_PASSWORD), SINGLE_USER_LOGIN),
            )
        enforce_single_user(db)

        default_units = [
            "Administração",
            "Compras e Licitações",
            "Engenharia",
            "Financeiro",
            "Jurídico",
            "Unidade Demandante",
        ]
        for unit in default_units:
            db.execute("INSERT OR IGNORE INTO units (name) VALUES (?)", (unit,))

        settings = {
            "committee_threshold": (
                "500000",
                "Valor a partir do qual a ata do comitê gestor passa a ser exigida.",
            ),
            "default_validator": (
                "Analista de contratação",
                "Responsável padrão sugerido para validação documental.",
            ),
        }
        for key, (value, description) in settings.items():
            db.execute(
                """
                INSERT OR IGNORE INTO app_settings (key, value, description)
                VALUES (?, ?, ?)
                """,
                (key, value, description),
            )

        model_count = db.execute("SELECT COUNT(*) FROM document_models").fetchone()[0]
        if model_count == 0:
            seed_models = [
                ("Formalização da Demanda", "Formalização da Demanda", "1.0", "Licitação"),
                ("Estudos Técnicos Preliminares", "Estudos Preliminares", "1.0", "Serviço ou fornecimento"),
                ("Mapa de Riscos", "Mapa de Riscos", "1.0", "Contratações aplicáveis"),
                ("Termo de Referência", "Projeto Básico / Termo de Referência", "1.0", "Geral"),
                ("Termo de Fiscalização", "Termo de Designação", "1.0", "Todos os casos"),
                ("Declaração de Vedação ao Nepotismo", "Declaração de Nepotismo", "1.0", "Contratação direta e adesão"),
            ]
            db.executemany(
                """
                INSERT INTO document_models (title, document_type, version, applicability)
                VALUES (?, ?, ?, ?)
                """,
                seed_models,
            )


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def current_user_id() -> int | None:
    return session.get("user_id")


def default_user_id() -> int | None:
    db = get_db()
    row = db.execute(
        "SELECT id FROM users WHERE email = ? AND active = 1", (SINGLE_USER_LOGIN,)
    ).fetchone()
    if row is None:
        row = db.execute(
            "SELECT id FROM users WHERE active = 1 ORDER BY id LIMIT 1"
        ).fetchone()
    return row["id"] if row else None


def ensure_direct_access_user() -> int | None:
    user_id = current_user_id()
    if user_id is None and not AUTH_ENABLED:
        user_id = default_user_id()
        if user_id is not None:
            session["user_id"] = user_id
    return user_id


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if ensure_direct_access_user() is None:
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_in_user() -> None:
    user_id = ensure_direct_access_user()
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            "SELECT * FROM users WHERE id = ? AND active = 1", (user_id,)
        ).fetchone()


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "today": date.today().isoformat(),
        "contract_types": CONTRACT_TYPES,
        "process_statuses": PROCESS_STATUSES,
        "item_statuses": ITEM_STATUSES,
        "validation_statuses": VALIDATION_STATUSES,
        "model_statuses": MODEL_STATUSES,
        "user_roles": USER_ROLES,
        "auth_enabled": AUTH_ENABLED,
    }


def parse_money(value: str | None) -> float:
    if not value:
        return 0.0
    clean = value.replace("R$", "").replace(" ", "").strip()
    if "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    try:
        return round(float(clean), 2)
    except ValueError:
        return 0.0


def parse_bool(name: str) -> int:
    return 1 if request.form.get(name) in {"on", "1", "true", "Sim"} else 0


def money(value: float | int | None) -> str:
    value = float(value or 0)
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file_storage, folder: str) -> tuple[str, str]:
    if not file_storage or file_storage.filename == "":
        raise ValueError("Nenhum arquivo enviado.")
    if not allowed_file(file_storage.filename):
        raise ValueError("Formato de arquivo não permitido.")

    original = secure_filename(file_storage.filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    stored = f"{folder}/{timestamp}_{original}"
    destination = UPLOAD_DIR / stored
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_storage.save(destination)
    return original, stored


def delete_uploaded_file(stored_filename: str | None) -> None:
    if not stored_filename:
        return
    upload_root = UPLOAD_DIR.resolve()
    target = (UPLOAD_DIR / stored_filename).resolve()
    try:
        target.relative_to(upload_root)
    except ValueError:
        return
    if target.is_file():
        try:
            target.unlink()
        except OSError:
            pass


def add_history(entity_type: str, entity_id: int, action: str, details: str | None = None) -> None:
    get_db().execute(
        """
        INSERT INTO history (entity_type, entity_id, action, user_id, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entity_type, entity_id, action, current_user_id(), details),
    )


def get_setting(key: str, default: str = "") -> str:
    row = get_db().execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_setting_float(key: str, default: float) -> float:
    try:
        return float(get_setting(key, str(default)).replace(",", "."))
    except ValueError:
        return default


def is_direct_contract(contract_type: str) -> bool:
    return contract_type in {"Contratação direta", "Dispensa", "Inexigibilidade", "Adesão à ata"}


def model_for_reference(demand: dict[str, Any]) -> str:
    if demand.get("contract_type") == "Remanescente":
        return "Modelo para contratação remanescente"
    if demand.get("engineering_service"):
        return "Projeto básico para obra/serviço de engenharia"
    if demand.get("common_acquisition"):
        return "Termo de referência para fornecimento/aquisição comum"
    if is_direct_contract(demand.get("contract_type", "")):
        return "Termo de referência para contratação direta"
    return "Termo de referência para serviço comum"


def rule_item(
    order: int,
    name: str,
    applies: bool,
    required: bool,
    applicability: str,
    model_available: bool = False,
    model_name: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if not applies:
        status = "Não se aplica"
        validation_status = "Não se aplica"
        required = False
        full_applicability = "Não se aplica"
    else:
        status = "Pendente" if required else "Não iniciado"
        validation_status = "Pendente"
        full_applicability = applicability
    return {
        "sort_order": order,
        "document_name": name,
        "applicability": full_applicability,
        "required": 1 if required else 0,
        "model_available": 1 if model_available else 0,
        "model_name": model_name,
        "status": status,
        "validation_status": validation_status,
        "observation": note,
    }


def append_rule_note(item: dict[str, Any], note: str) -> None:
    current = item.get("observation")
    if current:
        if note not in current:
            item["observation"] = f"{current} {note}"
    else:
        item["observation"] = note


def fetch_applicability_rule_map() -> dict[str, sqlite3.Row]:
    rows = get_db().execute("SELECT * FROM applicability_rules").fetchall()
    return {row["document_name"]: row for row in rows}


def apply_configurable_rules(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = fetch_applicability_rule_map()
    for item in items:
        rule = rules.get(item["document_name"])
        if rule is None:
            continue

        custom_applicability = (rule["custom_applicability"] or "").strip()
        if custom_applicability:
            item["applicability"] = custom_applicability

        if rule["requires_standard_model"]:
            item["model_available"] = 1
            item["model_name"] = item["model_name"] or "Modelo padrão exigido por regra"

        if rule["requires_justification"]:
            append_rule_note(item, "Regra configurada: exige justificativa quando dispensado ou marcado como não se aplica.")

        if rule["requires_superior_approval"]:
            append_rule_note(item, "Regra configurada: exige aprovação superior.")

        if rule["force_required"]:
            item["required"] = 1
            if item["status"] == "Não se aplica":
                item["status"] = "Pendente"
                item["validation_status"] = "Pendente"
            if item["applicability"] == "Não se aplica":
                item["applicability"] = "Obrigatório por regra configurada."

        if not rule["enabled"] or rule["force_not_applicable"]:
            item["required"] = 0
            item["applicability"] = "Não se aplica por regra configurada."
            item["status"] = "Não se aplica"
            item["validation_status"] = "Não se aplica"
            append_rule_note(item, "Regra configurada: item desabilitado/não aplicável.")

    return items


def build_checklist_rules(demand: dict[str, Any]) -> list[dict[str, Any]]:
    contract_type = demand["contract_type"]
    estimated_value = float(demand.get("estimated_value") or 0)
    dispensa_por_valor = bool(demand.get("dispensa_por_valor"))
    emergency = bool(demand.get("emergency"))
    remainder = contract_type == "Remanescente"
    direct = is_direct_contract(contract_type)
    licitation = contract_type in {"Licitação", "Registro de preço"}
    requires_contract = bool(demand.get("requires_contract")) or licitation or remainder
    threshold = get_setting_float("committee_threshold", 500000)
    exceeds_authority = bool(demand.get("exceeds_authority")) or estimated_value >= threshold

    has_service_or_supply = (
        bool(demand.get("engineering_service"))
        or bool(demand.get("common_acquisition"))
        or contract_type != "Adesão à ata"
    )
    proposal_value = demand.get("proposal_value")
    proposal_value = estimated_value if proposal_value in {None, ""} else float(proposal_value or 0)
    positive_proposal = proposal_value > 0

    preliminary_applies = has_service_or_supply and not (
        dispensa_por_valor or remainder or emergency
    )
    risk_map_applies = not (dispensa_por_valor or remainder or emergency)
    reference_applies = licitation or (direct and requires_contract) or remainder
    legal_opinion_required = (
        contract_type in {"Contratação direta", "Inexigibilidade", "Adesão à ata"}
        or (contract_type == "Dispensa" and not dispensa_por_valor)
    )
    nepotism_required = direct

    items = [
        rule_item(
            1,
            "Formalização da Demanda",
            licitation and has_service_or_supply,
            True,
            "Obrigatório para licitação de serviço ou fornecimento.",
            True,
            "Modelo de formalização da demanda",
        ),
        rule_item(
            2,
            "Estudos Preliminares",
            preliminary_applies,
            preliminary_applies,
            "Aplicável a serviços ou fornecimentos, exceto dispensa por valor, remanescente ou emergência.",
            True,
            "Modelo de estudos técnicos preliminares",
            None if preliminary_applies else "Dispensado pela regra automática; registre justificativa se necessário.",
        ),
        rule_item(
            3,
            "Mapa de Riscos",
            risk_map_applies,
            risk_map_applies,
            "Aplicável a todos os casos, exceto dispensa por valor, remanescente ou emergência.",
            True,
            "Modelo de mapa de riscos",
            "Quando necessário, incluir mapa de riscos da fase de gestão do contrato."
            if risk_map_applies
            else None,
        ),
        rule_item(
            4,
            "Projeto Básico / Termo de Referência",
            reference_applies,
            reference_applies,
            "Aplicável a licitações e contratações diretas com instrumento contratual.",
            True,
            model_for_reference(demand),
        ),
        rule_item(
            5,
            "Proposta de Licitação / Contratação",
            True,
            True,
            "Cadastro ou upload da proposta associada ao processo.",
            False,
            None,
        ),
        rule_item(
            6,
            "Fundamentação",
            True,
            True,
            "Aplicável a todos os casos.",
            False,
            None,
        ),
        rule_item(
            7,
            "Estimativa de Preços",
            True,
            True,
            "Exige valor estimado, fonte, pesquisas, referências, cotação e responsável.",
            False,
            None,
        ),
        rule_item(
            8,
            "Situação Orçamentária da Proposta",
            positive_proposal,
            positive_proposal,
            "Aplicável a propostas com valor positivo.",
            False,
            None,
        ),
        rule_item(
            9,
            "Cronograma de Desembolso",
            positive_proposal,
            positive_proposal,
            "Aplicável a propostas com valor positivo.",
            False,
            None,
        ),
        rule_item(
            10,
            "Ata do Comitê Gestor da Super do Demandante",
            exceeds_authority,
            exceeds_authority,
            f"Obrigatório quando ultrapassa a alçada configurada ({money(threshold)}).",
            False,
            None,
        ),
        rule_item(
            11,
            "Termo de Designação de Acompanhamento e Fiscalização do Contrato",
            True,
            True,
            "Aplicável a todos os casos.",
            True,
            "Modelo padrão de designação de fiscalização",
        ),
        rule_item(
            12,
            "Parecer Jurídico",
            legal_opinion_required,
            legal_opinion_required,
            "Aplicável a contratação direta, exceto dispensa por valor, e adesão à ata.",
            False,
            None,
        ),
        rule_item(
            13,
            "Anexos Técnicos",
            True,
            bool(demand.get("engineering_service")),
            "Aplicável quando houver material técnico de apoio.",
            False,
            None,
        ),
        rule_item(
            14,
            "Declaração de Vedação ao Nepotismo",
            nepotism_required,
            nepotism_required,
            "Aplicável a contratação direta e adesão à ata de registro de preços.",
            True,
            "Modelo de declaração de vedação ao nepotismo",
        ),
        rule_item(
            15,
            "Checklist da Licitação ou Contratação",
            True,
            True,
            "Gerado automaticamente com pendências, anexos, responsáveis e status final.",
            False,
            None,
        ),
    ]
    return apply_configurable_rules(items)


def create_checklist_for_demand(demand_id: int) -> None:
    db = get_db()
    demand_row = db.execute("SELECT * FROM demands WHERE id = ?", (demand_id,)).fetchone()
    if demand_row is None:
        return
    demand = row_to_dict(demand_row)
    rules = build_checklist_rules(demand)
    for item in rules:
        db.execute(
            """
            INSERT INTO checklist_items (
                demand_id, document_name, applicability, required, model_available,
                model_name, status, observation, validation_status, sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                demand_id,
                item["document_name"],
                item["applicability"],
                item["required"],
                item["model_available"],
                item["model_name"],
                item["status"],
                item["observation"],
                item["validation_status"],
                item["sort_order"],
            ),
        )
    update_process_status(demand_id)


def merge_observation(existing_observation: str | None, rule_observation: str | None) -> str | None:
    existing_clean = (existing_observation or "").strip()
    rule_clean = (rule_observation or "").strip()
    if existing_clean and rule_clean and rule_clean not in existing_clean:
        return f"{existing_clean} {rule_clean}"
    return existing_clean or rule_clean or None


def status_after_recalculation(
    rule: dict[str, Any],
    existing: sqlite3.Row | None,
    active_documents: int,
) -> tuple[str, str]:
    if rule["status"] == "Não se aplica":
        return "Não se aplica", "Não se aplica"

    if active_documents > 0:
        if existing and existing["validation_status"] == "Aprovado":
            return "Validado", "Aprovado"
        if existing and existing["status"] == "Validado":
            return "Validado", existing["validation_status"]
        validation_status = existing["validation_status"] if existing else "Enviado"
        if validation_status == "Não se aplica":
            validation_status = "Enviado"
        return "Anexado", validation_status

    if existing and existing["validation_status"] in {"Reprovado", "Corrigir"}:
        return "Pendente", existing["validation_status"]

    if existing and existing["status"] == "Não se aplica" and not rule["required"]:
        return "Não se aplica", "Não se aplica"

    return rule["status"], rule["validation_status"]


def recalculate_checklist_for_demand(demand_id: int) -> None:
    db = get_db()
    demand_row = db.execute("SELECT * FROM demands WHERE id = ?", (demand_id,)).fetchone()
    if demand_row is None:
        return

    rules = build_checklist_rules(row_to_dict(demand_row))
    existing_rows = db.execute(
        "SELECT * FROM checklist_items WHERE demand_id = ?", (demand_id,)
    ).fetchall()
    existing_by_name = {row["document_name"]: row for row in existing_rows}
    expected_names = {rule["document_name"] for rule in rules}

    for rule in rules:
        existing = existing_by_name.get(rule["document_name"])
        active_documents = 0
        if existing:
            active_documents = db.execute(
                "SELECT COUNT(*) FROM documents WHERE checklist_item_id = ? AND active = 1",
                (existing["id"],),
            ).fetchone()[0]

        status, validation_status = status_after_recalculation(rule, existing, active_documents)
        if existing is None:
            db.execute(
                """
                INSERT INTO checklist_items (
                    demand_id, document_name, applicability, required, model_available,
                    model_name, status, observation, validation_status, sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    demand_id,
                    rule["document_name"],
                    rule["applicability"],
                    rule["required"],
                    rule["model_available"],
                    rule["model_name"],
                    status,
                    rule["observation"],
                    validation_status,
                    rule["sort_order"],
                ),
            )
            continue

        db.execute(
            """
            UPDATE checklist_items SET
                applicability = ?,
                required = ?,
                model_available = ?,
                model_name = ?,
                status = ?,
                observation = ?,
                validation_status = ?,
                sort_order = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                rule["applicability"],
                rule["required"],
                rule["model_available"],
                rule["model_name"],
                status,
                merge_observation(existing["observation"], rule["observation"]),
                validation_status,
                rule["sort_order"],
                existing["id"],
            ),
        )

    for existing in existing_rows:
        if existing["document_name"] not in expected_names:
            db.execute(
                """
                UPDATE checklist_items
                SET required = 0,
                    applicability = 'Não se aplica por regra atual.',
                    status = 'Não se aplica',
                    validation_status = 'Não se aplica',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (existing["id"],),
            )

    update_process_status(demand_id)


def update_process_status(demand_id: int) -> str:
    db = get_db()
    items = db.execute(
        "SELECT * FROM checklist_items WHERE demand_id = ?", (demand_id,)
    ).fetchall()
    if not items:
        status = "Em elaboração"
    elif any(item["validation_status"] in {"Reprovado", "Corrigir"} for item in items):
        status = "Corrigir"
    elif any(
        item["required"]
        and item["status"] not in {"Anexado", "Validado", "Não se aplica"}
        for item in items
    ):
        status = "Pendências"
    elif any(item["status"] == "Anexado" and item["validation_status"] != "Aprovado" for item in items):
        status = "Aguardando validação"
    elif all(
        (not item["required"]) or item["status"] in {"Validado", "Não se aplica"}
        for item in items
    ):
        status = "Concluído"
    else:
        status = "Em elaboração"

    db.execute(
        "UPDATE demands SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, demand_id),
    )
    return status


def get_dashboard_counts(filters: dict[str, str]) -> dict[str, int]:
    db = get_db()
    where = []
    params: list[Any] = []
    if filters.get("unit_id"):
        where.append("unit_id = ?")
        params.append(filters["unit_id"])
    if filters.get("status"):
        where.append("status = ?")
        params.append(filters["status"])
    if filters.get("contract_type"):
        where.append("contract_type = ?")
        params.append(filters["contract_type"])
    if filters.get("start_date"):
        where.append("opening_date >= ?")
        params.append(filters["start_date"])
    if filters.get("end_date"):
        where.append("opening_date <= ?")
        params.append(filters["end_date"])
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    total = db.execute(f"SELECT COUNT(*) FROM demands {clause}", params).fetchone()[0]
    counts = {"total": total}
    for status in PROCESS_STATUSES:
        row = db.execute(
            f"SELECT COUNT(*) FROM demands {clause + (' AND' if clause else 'WHERE')} status = ?",
            [*params, status],
        ).fetchone()
        counts[status] = row[0]
    pending_docs = db.execute(
        """
        SELECT COUNT(*)
        FROM checklist_items ci
        JOIN demands d ON d.id = ci.demand_id
        WHERE ci.required = 1
          AND ci.status IN ('Não iniciado', 'Pendente')
        """
    ).fetchone()[0]
    counts["pending_docs"] = pending_docs
    return counts


def fetch_units() -> list[sqlite3.Row]:
    return get_db().execute("SELECT * FROM units ORDER BY name").fetchall()


def fetch_demand_or_404(demand_id: int) -> sqlite3.Row:
    demand = get_db().execute(
        """
        SELECT d.*, u.name AS unit_name
        FROM demands d
        JOIN units u ON u.id = d.unit_id
        WHERE d.id = ?
        """,
        (demand_id,),
    ).fetchone()
    if demand is None:
        abort(404)
    return demand


def build_demand_payload() -> dict[str, Any]:
    return {
        "process_number": request.form.get("process_number", "").strip(),
        "unit_id": request.form.get("unit_id"),
        "object": request.form.get("object", "").strip(),
        "contract_type": request.form.get("contract_type", ""),
        "estimated_value": parse_money(request.form.get("estimated_value")),
        "engineering_service": parse_bool("engineering_service"),
        "common_acquisition": parse_bool("common_acquisition"),
        "emergency": parse_bool("emergency"),
        "outside_capgv": parse_bool("outside_capgv"),
        "dispensa_por_valor": parse_bool("dispensa_por_valor"),
        "exceeds_authority": parse_bool("exceeds_authority"),
        "requires_contract": parse_bool("requires_contract"),
        "responsible": request.form.get("responsible", "").strip(),
        "opening_date": request.form.get("opening_date") or date.today().isoformat(),
        "legal_foundation": request.form.get("legal_foundation", "").strip(),
        "estimate_source": request.form.get("estimate_source", "").strip(),
        "price_research_responsible": request.form.get("price_research_responsible", "").strip(),
        "quotation_date": request.form.get("quotation_date") or None,
        "proposal_value": parse_money(request.form.get("proposal_value")),
        "supplier": request.form.get("supplier", "").strip(),
        "proposal_registered_system": parse_bool("proposal_registered_system"),
        "proposal_history": request.form.get("proposal_history", "").strip(),
        "budget_allocation": request.form.get("budget_allocation", "").strip(),
        "budget_source": request.form.get("budget_source", "").strip(),
        "budget_availability": request.form.get("budget_availability", "").strip(),
        "budget_unit": request.form.get("budget_unit", "").strip(),
        "expense_nature": request.form.get("expense_nature", "").strip(),
        "controller_opinion": request.form.get("controller_opinion", "").strip(),
        "price_research_summary": request.form.get("price_research_summary", "").strip(),
        "reference_documents": request.form.get("reference_documents", "").strip(),
        "external_consultations": request.form.get("external_consultations", "").strip(),
        "committee_meeting_date": request.form.get("committee_meeting_date") or None,
        "committee_record_number": request.form.get("committee_record_number", "").strip(),
        "chief_fiscal": request.form.get("chief_fiscal", "").strip(),
        "substitute_fiscal": request.form.get("substitute_fiscal", "").strip(),
        "contract_manager": request.form.get("contract_manager", "").strip(),
        "designation_document_generated": parse_bool("designation_document_generated"),
        "proposal_generated": parse_bool("proposal_generated"),
        "proposal_notes": request.form.get("proposal_notes", "").strip(),
        "conclusion_date": request.form.get("conclusion_date") or None,
        "conclusion_summary": request.form.get("conclusion_summary", "").strip(),
        "final_responsible": request.form.get("final_responsible", "").strip(),
    }


def validate_demand_payload(payload: dict[str, Any]) -> list[str]:
    errors = []
    required_fields = {
        "process_number": "Número do processo",
        "unit_id": "Unidade demandante",
        "object": "Objeto da contratação",
        "contract_type": "Tipo de contratação",
        "responsible": "Responsável pela demanda",
        "opening_date": "Data de abertura",
    }
    for key, label in required_fields.items():
        if not payload.get(key):
            errors.append(f"{label} é obrigatório.")
    if payload.get("contract_type") and payload["contract_type"] not in CONTRACT_TYPES:
        errors.append("Tipo de contratação inválido.")
    return errors


@app.route("/")
def index():
    if AUTH_ENABLED and current_user_id() is None:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_ENABLED:
        ensure_direct_access_user()
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        login_id = request.form.get("login", request.form.get("email", "")).strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE email = ? AND active = 1", (login_id,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("E-mail ou senha inválidos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    if not AUTH_ENABLED:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    filters = {
        "unit_id": request.args.get("unit_id", ""),
        "status": request.args.get("status", ""),
        "contract_type": request.args.get("contract_type", ""),
        "start_date": request.args.get("start_date", ""),
        "end_date": request.args.get("end_date", ""),
    }
    counts = get_dashboard_counts(filters)
    db = get_db()
    alerts = db.execute(
        """
        SELECT d.id AS demand_id, d.process_number, d.object, ci.document_name, ci.status
        FROM checklist_items ci
        JOIN demands d ON d.id = ci.demand_id
        WHERE ci.required = 1
          AND ci.status IN ('Não iniciado', 'Pendente')
        ORDER BY d.opening_date DESC, ci.sort_order
        LIMIT 12
        """
    ).fetchall()
    recent_demands = db.execute(
        """
        SELECT d.*, u.name AS unit_name
        FROM demands d
        JOIN units u ON u.id = d.unit_id
        ORDER BY d.updated_at DESC
        LIMIT 8
        """
    ).fetchall()
    return render_template(
        "dashboard.html",
        counts=counts,
        alerts=alerts,
        recent_demands=recent_demands,
        units=fetch_units(),
        filters=filters,
    )


@app.route("/demandas")
@login_required
def demand_list():
    db = get_db()
    where = []
    params: list[Any] = []
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    unit_id = request.args.get("unit_id", "")
    contract_type = request.args.get("contract_type", "")
    if q:
        where.append("(d.process_number LIKE ? OR d.object LIKE ? OR d.responsible LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])
    if status:
        where.append("d.status = ?")
        params.append(status)
    if unit_id:
        where.append("d.unit_id = ?")
        params.append(unit_id)
    if contract_type:
        where.append("d.contract_type = ?")
        params.append(contract_type)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    demands = db.execute(
        f"""
        SELECT d.*, u.name AS unit_name
        FROM demands d
        JOIN units u ON u.id = d.unit_id
        {clause}
        ORDER BY d.opening_date DESC, d.id DESC
        """,
        params,
    ).fetchall()
    return render_template(
        "demandas/list.html",
        demands=demands,
        units=fetch_units(),
        filters={
            "q": q,
            "status": status,
            "unit_id": unit_id,
            "contract_type": contract_type,
        },
    )


@app.route("/demandas/nova", methods=["GET", "POST"])
@login_required
def demand_new():
    if request.method == "POST":
        payload = build_demand_payload()
        errors = validate_demand_payload(payload)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("demandas/form.html", demand=payload, units=fetch_units())
        db = get_db()
        try:
            cursor = db.execute(
                """
                INSERT INTO demands (
                    process_number, unit_id, object, contract_type, estimated_value,
                    engineering_service, common_acquisition, emergency, outside_capgv,
                    dispensa_por_valor, exceeds_authority, requires_contract, responsible,
                    opening_date, legal_foundation, estimate_source, price_research_responsible,
                    quotation_date, proposal_value, supplier, proposal_registered_system,
                    proposal_history, budget_allocation, budget_source, budget_availability,
                    budget_unit, expense_nature, controller_opinion, price_research_summary,
                    reference_documents, external_consultations, committee_meeting_date,
                    committee_record_number, chief_fiscal, substitute_fiscal, contract_manager,
                    designation_document_generated, proposal_generated, proposal_notes,
                    conclusion_date, conclusion_summary, final_responsible, created_by
                )
                VALUES (
                    :process_number, :unit_id, :object, :contract_type, :estimated_value,
                    :engineering_service, :common_acquisition, :emergency, :outside_capgv,
                    :dispensa_por_valor, :exceeds_authority, :requires_contract, :responsible,
                    :opening_date, :legal_foundation, :estimate_source, :price_research_responsible,
                    :quotation_date, :proposal_value, :supplier, :proposal_registered_system,
                    :proposal_history, :budget_allocation, :budget_source, :budget_availability,
                    :budget_unit, :expense_nature, :controller_opinion, :price_research_summary,
                    :reference_documents, :external_consultations, :committee_meeting_date,
                    :committee_record_number, :chief_fiscal, :substitute_fiscal, :contract_manager,
                    :designation_document_generated, :proposal_generated, :proposal_notes,
                    :conclusion_date, :conclusion_summary, :final_responsible, :created_by
                )
                """,
                {**payload, "created_by": current_user_id()},
            )
            demand_id = cursor.lastrowid
            create_checklist_for_demand(demand_id)
            add_history("demanda", demand_id, "Demanda criada", "Checklist automático gerado.")
            db.commit()
            flash("Demanda cadastrada e checklist gerado automaticamente.", "success")
            return redirect(url_for("demand_detail", demand_id=demand_id))
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Já existe uma demanda com esse número de processo.", "danger")

    default_demand = {"opening_date": date.today().isoformat(), "contract_type": "Licitação"}
    return render_template("demandas/form.html", demand=default_demand, units=fetch_units())


@app.route("/demandas/<int:demand_id>/editar", methods=["GET", "POST"])
@login_required
def demand_edit(demand_id: int):
    demand = fetch_demand_or_404(demand_id)
    if request.method == "POST":
        payload = build_demand_payload()
        errors = validate_demand_payload(payload)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("demandas/form.html", demand={**row_to_dict(demand), **payload}, units=fetch_units(), edit=True)
        db = get_db()
        try:
            db.execute(
                """
                UPDATE demands SET
                    process_number = :process_number,
                    unit_id = :unit_id,
                    object = :object,
                    contract_type = :contract_type,
                    estimated_value = :estimated_value,
                    engineering_service = :engineering_service,
                    common_acquisition = :common_acquisition,
                    emergency = :emergency,
                    outside_capgv = :outside_capgv,
                    dispensa_por_valor = :dispensa_por_valor,
                    exceeds_authority = :exceeds_authority,
                    requires_contract = :requires_contract,
                    responsible = :responsible,
                    opening_date = :opening_date,
                    legal_foundation = :legal_foundation,
                    estimate_source = :estimate_source,
                    price_research_responsible = :price_research_responsible,
                    quotation_date = :quotation_date,
                    proposal_value = :proposal_value,
                    supplier = :supplier,
                    proposal_registered_system = :proposal_registered_system,
                    proposal_history = :proposal_history,
                    budget_allocation = :budget_allocation,
                    budget_source = :budget_source,
                    budget_availability = :budget_availability,
                    budget_unit = :budget_unit,
                    expense_nature = :expense_nature,
                    controller_opinion = :controller_opinion,
                    price_research_summary = :price_research_summary,
                    reference_documents = :reference_documents,
                    external_consultations = :external_consultations,
                    committee_meeting_date = :committee_meeting_date,
                    committee_record_number = :committee_record_number,
                    chief_fiscal = :chief_fiscal,
                    substitute_fiscal = :substitute_fiscal,
                    contract_manager = :contract_manager,
                    designation_document_generated = :designation_document_generated,
                    proposal_generated = :proposal_generated,
                    proposal_notes = :proposal_notes,
                    conclusion_date = :conclusion_date,
                    conclusion_summary = :conclusion_summary,
                    final_responsible = :final_responsible,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                {**payload, "id": demand_id},
            )
            recalculate_checklist_for_demand(demand_id)
            add_history("demanda", demand_id, "Demanda atualizada", "Checklist recalculado com preservação dos anexos existentes.")
            db.commit()
            flash("Demanda atualizada.", "success")
            return redirect(url_for("demand_detail", demand_id=demand_id))
        except sqlite3.IntegrityError:
            db.rollback()
            flash("Já existe uma demanda com esse número de processo.", "danger")
    return render_template("demandas/form.html", demand=demand, units=fetch_units(), edit=True)


@app.route("/demandas/<int:demand_id>")
@login_required
def demand_detail(demand_id: int):
    update_process_status(demand_id)
    get_db().commit()
    demand = fetch_demand_or_404(demand_id)
    db = get_db()
    items = db.execute(
        """
        SELECT *
        FROM checklist_items
        WHERE demand_id = ?
        ORDER BY sort_order, id
        """,
        (demand_id,),
    ).fetchall()
    documents = db.execute(
        """
        SELECT docs.*, u.name AS uploaded_by_name
        FROM documents docs
        LEFT JOIN users u ON u.id = docs.uploaded_by
        WHERE docs.checklist_item_id IN (
            SELECT id FROM checklist_items WHERE demand_id = ?
        )
        ORDER BY docs.checklist_item_id, docs.version DESC
        """,
        (demand_id,),
    ).fetchall()
    docs_by_item: dict[int, list[sqlite3.Row]] = {}
    for document in documents:
        docs_by_item.setdefault(document["checklist_item_id"], []).append(document)
    disbursements = db.execute(
        "SELECT * FROM disbursements WHERE demand_id = ? ORDER BY installment",
        (demand_id,),
    ).fetchall()
    history = db.execute(
        """
        SELECT h.*, u.name AS user_name
        FROM history h
        LEFT JOIN users u ON u.id = h.user_id
        WHERE h.entity_type = 'demanda' AND h.entity_id = ?
        ORDER BY h.created_at DESC
        LIMIT 10
        """,
        (demand_id,),
    ).fetchall()
    return render_template(
        "demandas/detail.html",
        demand=demand,
        items=items,
        docs_by_item=docs_by_item,
        disbursements=disbursements,
        history=history,
    )


@app.route("/demandas/<int:demand_id>/cronograma", methods=["POST"])
@login_required
def disbursement_add(demand_id: int):
    fetch_demand_or_404(demand_id)
    installment = request.form.get("installment", "").strip()
    expected_month = request.form.get("expected_month", "").strip()
    expected_value = parse_money(request.form.get("expected_value"))
    percent = parse_money(request.form.get("percent"))
    observation = request.form.get("observation", "").strip()
    if not installment or not expected_month:
        flash("Parcela e mês previsto são obrigatórios.", "danger")
        return redirect(url_for("demand_detail", demand_id=demand_id) + "#cronograma")
    db = get_db()
    db.execute(
        """
        INSERT INTO disbursements (demand_id, installment, expected_month, expected_value, percent, observation)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (demand_id, int(installment), expected_month, expected_value, percent, observation),
    )
    add_history("demanda", demand_id, "Cronograma atualizado", f"Parcela {installment}.")
    db.commit()
    flash("Parcela adicionada ao cronograma.", "success")
    return redirect(url_for("demand_detail", demand_id=demand_id) + "#cronograma")


def word_response(filename: str, title: str, body: str) -> Response:
    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; font-size: 12pt; line-height: 1.45; }}
            h1 {{ font-size: 18pt; }}
            table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
            td, th {{ border: 1px solid #777; padding: 6px; vertical-align: top; }}
            .signature {{ margin-top: 48px; text-align: center; }}
        </style>
    </head>
    <body>{body}</body>
    </html>
    """
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(html, headers=headers, mimetype="application/msword")


@app.route("/demandas/<int:demand_id>/proposta/gerar")
@login_required
def proposal_generate(demand_id: int):
    demand = fetch_demand_or_404(demand_id)
    body = f"""
    <h1>Proposta de Licitação / Contratação</h1>
    <table>
        <tr><th>Processo</th><td>{demand['process_number']}</td></tr>
        <tr><th>Unidade demandante</th><td>{demand['unit_name']}</td></tr>
        <tr><th>Objeto</th><td>{demand['object']}</td></tr>
        <tr><th>Fornecedor/interessado</th><td>{demand['supplier'] or '-'}</td></tr>
        <tr><th>Valor da proposta</th><td>{money(demand['proposal_value'])}</td></tr>
        <tr><th>Cadastro em sistema</th><td>{'Sim' if demand['proposal_registered_system'] else 'Não'}</td></tr>
        <tr><th>Histórico</th><td>{demand['proposal_history'] or '-'}</td></tr>
        <tr><th>Observações</th><td>{demand['proposal_notes'] or '-'}</td></tr>
    </table>
    <p class="signature">Responsável pela demanda<br><strong>{demand['responsible']}</strong></p>
    """
    filename = secure_filename(f"proposta_{demand['process_number']}.doc")
    return word_response(filename, "Proposta", body)


@app.route("/demandas/<int:demand_id>/estimativa/gerar")
@login_required
def estimate_generate(demand_id: int):
    demand = fetch_demand_or_404(demand_id)
    body = f"""
    <h1>Estimativa de Preços</h1>
    <table>
        <tr><th>Processo</th><td>{demand['process_number']}</td></tr>
        <tr><th>Unidade demandante</th><td>{demand['unit_name']}</td></tr>
        <tr><th>Objeto</th><td>{demand['object']}</td></tr>
        <tr><th>Valor estimado</th><td>{money(demand['estimated_value'])}</td></tr>
        <tr><th>Fonte da estimativa</th><td>{demand['estimate_source'] or '-'}</td></tr>
        <tr><th>Responsável pela pesquisa</th><td>{demand['price_research_responsible'] or '-'}</td></tr>
        <tr><th>Data da cotação</th><td>{date_br(demand['quotation_date'])}</td></tr>
        <tr><th>Pesquisas realizadas</th><td>{demand['price_research_summary'] or '-'}</td></tr>
        <tr><th>Documentos de referência</th><td>{demand['reference_documents'] or '-'}</td></tr>
        <tr><th>Consultas externas</th><td>{demand['external_consultations'] or '-'}</td></tr>
    </table>
    <p class="signature">Responsável pela estimativa<br><strong>{demand['price_research_responsible'] or demand['responsible']}</strong></p>
    """
    filename = secure_filename(f"estimativa_precos_{demand['process_number']}.doc")
    return word_response(filename, "Estimativa de Preços", body)


@app.route("/demandas/<int:demand_id>/ata-comite/gerar")
@login_required
def committee_minutes_generate(demand_id: int):
    demand = fetch_demand_or_404(demand_id)
    body = f"""
    <h1>Ata do Comitê Gestor da Super do Demandante</h1>
    <table>
        <tr><th>Processo</th><td>{demand['process_number']}</td></tr>
        <tr><th>Unidade demandante</th><td>{demand['unit_name']}</td></tr>
        <tr><th>Objeto</th><td>{demand['object']}</td></tr>
        <tr><th>Valor estimado</th><td>{money(demand['estimated_value'])}</td></tr>
        <tr><th>Data da reunião</th><td>{date_br(demand['committee_meeting_date'])}</td></tr>
        <tr><th>Numero da ata</th><td>{demand['committee_record_number'] or '-'}</td></tr>
        <tr><th>Fundamentação</th><td>{demand['legal_foundation'] or '-'}</td></tr>
        <tr><th>Parecer da controladoria</th><td>{demand['controller_opinion'] or '-'}</td></tr>
    </table>
    <p>Registro formal para deliberação, acompanhamento e validação da demanda acima identificada.</p>
    <p class="signature">Representante do comitê<br><strong>________________________________________</strong></p>
    """
    filename = secure_filename(f"ata_comite_{demand['process_number']}.doc")
    return word_response(filename, "Ata do Comitê", body)


@app.route("/demandas/<int:demand_id>/termo-designacao/gerar")
@login_required
def designation_generate(demand_id: int):
    demand = fetch_demand_or_404(demand_id)
    body = f"""
    <h1>Termo de Designação de Acompanhamento e Fiscalização do Contrato</h1>
    <p>Processo: <strong>{demand['process_number']}</strong></p>
    <p>Objeto: {demand['object']}</p>
    <table>
        <tr><th>Fiscal titular</th><td>{demand['chief_fiscal'] or '-'}</td></tr>
        <tr><th>Fiscal substituto</th><td>{demand['substitute_fiscal'] or '-'}</td></tr>
        <tr><th>Gestor do contrato</th><td>{demand['contract_manager'] or '-'}</td></tr>
        <tr><th>Unidade demandante</th><td>{demand['unit_name']}</td></tr>
        <tr><th>Data de abertura</th><td>{date_br(demand['opening_date'])}</td></tr>
    </table>
    <p>Os responsáveis acima ficam designados para acompanhar, fiscalizar e registrar as ocorrências relacionadas ao contrato/processo.</p>
    <p class="signature">Autoridade competente<br><strong>________________________________________</strong></p>
    """
    filename = secure_filename(f"termo_designacao_{demand['process_number']}.doc")
    return word_response(filename, "Termo de Designação", body)


@app.route("/checklist/<int:item_id>/atualizar", methods=["POST"])
@login_required
def checklist_update(item_id: int):
    db = get_db()
    item = db.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        abort(404)
    status = request.form.get("status", item["status"])
    observation = request.form.get("observation", "").strip()
    if status not in ITEM_STATUSES:
        flash("Status do item inválido.", "danger")
        return redirect(url_for("demand_detail", demand_id=item["demand_id"]))
    if status == "Não se aplica" and item["required"] and not observation:
        flash("Informe uma observação para marcar um item obrigatório como não se aplica.", "danger")
        return redirect(url_for("demand_detail", demand_id=item["demand_id"]) + f"#item-{item_id}")
    validation_status = "Não se aplica" if status == "Não se aplica" else item["validation_status"]
    db.execute(
        """
        UPDATE checklist_items SET
            status = ?,
            observation = ?,
            responsible_send = ?,
            responsible_validate = ?,
            validation_status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            status,
            observation,
            request.form.get("responsible_send", "").strip(),
            request.form.get("responsible_validate", "").strip(),
            validation_status,
            item_id,
        ),
    )
    update_process_status(item["demand_id"])
    add_history("demanda", item["demand_id"], "Checklist atualizado", item["document_name"])
    db.commit()
    flash("Item do checklist atualizado.", "success")
    return redirect(url_for("demand_detail", demand_id=item["demand_id"]) + f"#item-{item_id}")


@app.route("/checklist/<int:item_id>/upload", methods=["POST"])
@login_required
def checklist_upload(item_id: int):
    db = get_db()
    item = db.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        abort(404)
    try:
        original, stored = save_uploaded_file(request.files.get("document"), f"checklist/{item_id}")
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("demand_detail", demand_id=item["demand_id"]) + f"#item-{item_id}")

    current_version = db.execute(
        "SELECT COALESCE(MAX(version), 0) FROM documents WHERE checklist_item_id = ?",
        (item_id,),
    ).fetchone()[0]
    allow_multiple_active = item["document_name"] == "Anexos Técnicos"
    if not allow_multiple_active:
        db.execute("UPDATE documents SET active = 0 WHERE checklist_item_id = ?", (item_id,))
    db.execute(
        """
        INSERT INTO documents (checklist_item_id, original_filename, stored_filename, version, uploaded_by)
        VALUES (?, ?, ?, ?, ?)
        """,
        (item_id, original, stored, current_version + 1, current_user_id()),
    )
    db.execute(
        """
        UPDATE checklist_items
        SET status = 'Anexado', validation_status = 'Enviado', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (item_id,),
    )
    update_process_status(item["demand_id"])
    add_history("demanda", item["demand_id"], "Documento anexado", item["document_name"])
    db.commit()
    if allow_multiple_active:
        flash("Anexo técnico anexado e mantido ativo junto aos demais arquivos.", "success")
    else:
        flash("Documento anexado com controle de versão.", "success")
    return redirect(url_for("demand_detail", demand_id=item["demand_id"]) + f"#item-{item_id}")


@app.route("/checklist/<int:item_id>/validar", methods=["POST"])
@login_required
def checklist_validate(item_id: int):
    db = get_db()
    item = db.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        abort(404)
    status = request.form.get("validation_status", "")
    observation = request.form.get("validation_observation", "").strip()
    if status not in VALIDATION_STATUSES:
        flash("Status de validação inválido.", "danger")
        return redirect(url_for("demand_detail", demand_id=item["demand_id"]) + f"#item-{item_id}")
    if status in {"Reprovado", "Corrigir"} and not observation:
        flash("Observação obrigatória para reprovar ou solicitar correção.", "danger")
        return redirect(url_for("demand_detail", demand_id=item["demand_id"]) + f"#item-{item_id}")

    item_status = item["status"]
    if status == "Aprovado":
        item_status = "Validado"
    elif status in {"Reprovado", "Corrigir"}:
        item_status = "Pendente"
    elif status == "Não se aplica":
        item_status = "Não se aplica"

    db.execute(
        """
        UPDATE checklist_items
        SET validation_status = ?, validation_observation = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, observation, item_status, item_id),
    )
    db.execute(
        """
        INSERT INTO validations (checklist_item_id, status, observation, validator_id)
        VALUES (?, ?, ?, ?)
        """,
        (item_id, status, observation, current_user_id()),
    )
    update_process_status(item["demand_id"])
    add_history("demanda", item["demand_id"], "Validação registrada", f"{item['document_name']}: {status}")
    db.commit()
    flash("Validação registrada.", "success")
    return redirect(url_for("demand_detail", demand_id=item["demand_id"]) + f"#item-{item_id}")


@app.route("/documentos/<int:document_id>/excluir", methods=["POST"])
@login_required
def document_delete(document_id: int):
    db = get_db()
    document = db.execute(
        """
        SELECT docs.*, ci.demand_id, ci.document_name
        FROM documents docs
        JOIN checklist_items ci ON ci.id = docs.checklist_item_id
        WHERE docs.id = ?
        """,
        (document_id,),
    ).fetchone()
    if document is None:
        abort(404)
    reason = request.form.get("deletion_reason", "").strip()
    if not reason:
        flash("Informe a justificativa para excluir o anexo.", "danger")
        return redirect(url_for("demand_detail", demand_id=document["demand_id"]) + f"#item-{document['checklist_item_id']}")
    db.execute(
        """
        UPDATE documents
        SET active = 0, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?, deletion_reason = ?
        WHERE id = ?
        """,
        (current_user_id(), reason, document_id),
    )
    active_count = db.execute(
        "SELECT COUNT(*) FROM documents WHERE checklist_item_id = ? AND active = 1",
        (document["checklist_item_id"],),
    ).fetchone()[0]
    if active_count == 0:
        db.execute(
            """
            UPDATE checklist_items
            SET status = CASE WHEN required = 1 THEN 'Pendente' ELSE 'Não iniciado' END,
                validation_status = 'Pendente',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (document["checklist_item_id"],),
        )
    update_process_status(document["demand_id"])
    add_history("demanda", document["demand_id"], "Anexo excluído", f"{document['document_name']}: {reason}")
    db.commit()
    flash("Anexo excluído com justificativa.", "success")
    return redirect(url_for("demand_detail", demand_id=document["demand_id"]) + f"#item-{document['checklist_item_id']}")


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename: str):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)


def fetch_model_or_404(model_id: int) -> sqlite3.Row:
    model = get_db().execute(
        "SELECT * FROM document_models WHERE id = ?", (model_id,)
    ).fetchone()
    if model is None:
        abort(404)
    return model


@app.route("/modelos")
@login_required
def model_list():
    models = get_db().execute(
        "SELECT * FROM document_models ORDER BY document_type, title, version DESC"
    ).fetchall()
    return render_template("modelos/list.html", models=models)


@app.route("/modelos/novo", methods=["GET", "POST"])
@login_required
def model_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        document_type = request.form.get("document_type", "").strip()
        version = request.form.get("version", "").strip()
        applicability = request.form.get("applicability", "").strip()
        status = request.form.get("status", "Ativo")
        if not title or not document_type or not version or not applicability:
            flash("Preencha título, tipo, versão e aplicabilidade.", "danger")
            return render_template("modelos/form.html", model=request.form)
        if status not in MODEL_STATUSES:
            status = "Ativo"
        original = stored = None
        upload = request.files.get("model_file")
        if upload and upload.filename:
            try:
                original, stored = save_uploaded_file(upload, "modelos")
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("modelos/form.html", model=request.form)
        db = get_db()
        db.execute(
            """
            INSERT INTO document_models (
                title, document_type, version, applicability, original_filename, stored_filename, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, document_type, version, applicability, original, stored, status),
        )
        db.commit()
        flash("Modelo cadastrado.", "success")
        return redirect(url_for("model_list"))
    return render_template("modelos/form.html", model={"status": "Ativo", "version": "1.0"})


@app.route("/modelos/<int:model_id>/editar", methods=["GET", "POST"])
@login_required
def model_edit(model_id: int):
    model = fetch_model_or_404(model_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        document_type = request.form.get("document_type", "").strip()
        version = request.form.get("version", "").strip()
        applicability = request.form.get("applicability", "").strip()
        status = request.form.get("status", "Ativo")
        if not title or not document_type or not version or not applicability:
            flash("Preencha título, tipo, versão e aplicabilidade.", "danger")
            model_data = {**row_to_dict(model), **request.form}
            return render_template("modelos/form.html", model=model_data, edit=True)
        if status not in MODEL_STATUSES:
            status = "Ativo"

        original = model["original_filename"]
        stored = model["stored_filename"]
        upload = request.files.get("model_file")
        remove_file = parse_bool("remove_file")
        if upload and upload.filename:
            try:
                new_original, new_stored = save_uploaded_file(upload, "modelos")
            except ValueError as exc:
                flash(str(exc), "danger")
                model_data = {**row_to_dict(model), **request.form}
                return render_template("modelos/form.html", model=model_data, edit=True)
            delete_uploaded_file(stored)
            original = new_original
            stored = new_stored
        elif remove_file:
            delete_uploaded_file(stored)
            original = None
            stored = None

        db = get_db()
        db.execute(
            """
            UPDATE document_models
            SET title = ?,
                document_type = ?,
                version = ?,
                applicability = ?,
                original_filename = ?,
                stored_filename = ?,
                status = ?
            WHERE id = ?
            """,
            (title, document_type, version, applicability, original, stored, status, model_id),
        )
        db.commit()
        flash("Modelo atualizado.", "success")
        return redirect(url_for("model_list"))

    return render_template("modelos/form.html", model=model, edit=True)


@app.route("/modelos/<int:model_id>/excluir", methods=["POST"])
@login_required
def model_delete(model_id: int):
    model = fetch_model_or_404(model_id)
    delete_uploaded_file(model["stored_filename"])
    db = get_db()
    db.execute("DELETE FROM document_models WHERE id = ?", (model_id,))
    db.commit()
    flash("Modelo excluído.", "success")
    return redirect(url_for("model_list"))


@app.route("/relatorios")
@login_required
def reports():
    demands = get_db().execute(
        """
        SELECT d.*, u.name AS unit_name,
            SUM(CASE WHEN ci.required = 1 THEN 1 ELSE 0 END) AS required_total,
            SUM(CASE WHEN ci.required = 1 AND ci.status = 'Validado' THEN 1 ELSE 0 END) AS validated_total,
            SUM(CASE WHEN ci.required = 1 AND ci.status IN ('Pendente', 'Não iniciado') THEN 1 ELSE 0 END) AS pending_total
        FROM demands d
        JOIN units u ON u.id = d.unit_id
        LEFT JOIN checklist_items ci ON ci.demand_id = d.id
        GROUP BY d.id
        ORDER BY d.opening_date DESC
        """
    ).fetchall()
    return render_template("relatorios/list.html", demands=demands)


@app.route("/relatorios/demanda/<int:demand_id>")
@login_required
def report_demand(demand_id: int):
    demand = fetch_demand_or_404(demand_id)
    items = get_db().execute(
        """
        SELECT ci.*,
            COUNT(docs.id) AS attachment_count,
            MAX(docs.uploaded_at) AS last_upload
        FROM checklist_items ci
        LEFT JOIN documents docs ON docs.checklist_item_id = ci.id AND docs.active = 1
        WHERE ci.demand_id = ?
        GROUP BY ci.id
        ORDER BY ci.sort_order
        """,
        (demand_id,),
    ).fetchall()
    return render_template("relatorios/demanda.html", demand=demand, items=items)


@app.route("/configuracoes", methods=["GET", "POST"])
@login_required
def settings():
    db = get_db()
    if request.method == "POST":
        if request.form.get("form_type") == "applicability_rules":
            rules = db.execute("SELECT id FROM applicability_rules").fetchall()
            for rule in rules:
                rule_id = rule["id"]
                db.execute(
                    """
                    UPDATE applicability_rules
                    SET enabled = ?,
                        force_required = ?,
                        force_not_applicable = ?,
                        requires_justification = ?,
                        requires_standard_model = ?,
                        requires_superior_approval = ?,
                        custom_applicability = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        1 if request.form.get(f"enabled_{rule_id}") else 0,
                        1 if request.form.get(f"force_required_{rule_id}") else 0,
                        1 if request.form.get(f"force_not_applicable_{rule_id}") else 0,
                        1 if request.form.get(f"requires_justification_{rule_id}") else 0,
                        1 if request.form.get(f"requires_standard_model_{rule_id}") else 0,
                        1 if request.form.get(f"requires_superior_approval_{rule_id}") else 0,
                        request.form.get(f"custom_applicability_{rule_id}", "").strip(),
                        rule_id,
                    ),
                )
            demand_ids = [row["id"] for row in db.execute("SELECT id FROM demands").fetchall()]
            for demand_id in demand_ids:
                recalculate_checklist_for_demand(demand_id)
            db.commit()
            flash("Matriz de aplicabilidade salva e checklists recalculados.", "success")
            return redirect(url_for("settings"))

        committee_threshold = parse_money(request.form.get("committee_threshold"))
        default_validator = request.form.get("default_validator", "").strip() or "Analista de contratação"
        db.execute(
            "UPDATE app_settings SET value = ? WHERE key = 'committee_threshold'",
            (str(committee_threshold),),
        )
        db.execute(
            "UPDATE app_settings SET value = ? WHERE key = 'default_validator'",
            (default_validator,),
        )
        demand_ids = [row["id"] for row in db.execute("SELECT id FROM demands").fetchall()]
        for demand_id in demand_ids:
            recalculate_checklist_for_demand(demand_id)
        db.commit()
        flash("Configurações atualizadas e checklists recalculados.", "success")
        return redirect(url_for("settings"))
    settings_rows = db.execute("SELECT * FROM app_settings ORDER BY key").fetchall()
    applicability_rules = db.execute("SELECT * FROM applicability_rules ORDER BY id").fetchall()
    return render_template(
        "configuracoes.html",
        settings_rows=settings_rows,
        applicability_rules=applicability_rules,
    )


@app.template_filter("money")
def money_filter(value: float | int | None) -> str:
    return money(value)


@app.template_filter("date_br")
def date_br(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d")
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return value


@app.template_filter("datetime_br")
def datetime_br(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


@app.template_filter("status_class")
def status_class(value: str | None) -> str:
    classes = {
        "Concluído": "success",
        "Validado": "success",
        "Aprovado": "success",
        "Aguardando validação": "primary",
        "Anexado": "primary",
        "Enviado": "primary",
        "Em análise": "info",
        "Em elaboração": "secondary",
        "Não iniciado": "secondary",
        "Pendências": "warning",
        "Pendente": "warning",
        "Corrigir": "danger",
        "Reprovado": "danger",
        "Não se aplica": "dark",
    }
    return classes.get(value or "", "secondary")


# Inicializa o banco também quando a aplicação sobe via Gunicorn em produção.
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5010"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
