from __future__ import annotations

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
WEB_DIR = APP_DIR / "web"

RUNTIME_MODULES = ["api.py", "main.py", "services.py", "model.py", "analysis.py", "hazards.py", "auth.py"]


def _py_files():
    return [p for p in APP_DIR.rglob("*.py")]


def _web_files():
    return [p for p in WEB_DIR.rglob("*") if p.suffix in {".js", ".html", ".css"}]


def test_no_accident_csv_or_blackspot_in_runtime():
    # R2: no historical accident CSV / blackspot references in shipped code.
    pattern = re.compile(r"accident.*csv|blackspot", re.IGNORECASE)
    offenders = []
    for path in [*_py_files(), *_web_files()]:
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path))
    assert offenders == []


def test_no_affirmative_risk_marketing_phrases():
    # R4: forbidden affirmative claims must never appear.
    forbidden = ["safe route", "prevents accidents", "validated risk"]
    offenders = []
    for path in [*_py_files(), *_web_files()]:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            if phrase in text:
                offenders.append((str(path), phrase))
    assert offenders == []


def test_accident_probability_only_in_negated_disclaimers():
    # R4: "accident probability" may appear only as an explicit negation.
    offenders = []
    for path in [*_py_files(), *_web_files()]:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "accident probability" in line.lower():
                if "not" not in line.lower():
                    offenders.append((str(path), lineno, line.strip()))
    assert offenders == []


def test_runtime_never_imports_ml_training():
    # R10: training/generator code must not be imported by the runtime server.
    offenders = []
    for name in RUNTIME_MODULES:
        path = APP_DIR / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for mod in mods:
                if mod.split(".")[0] == "ml":
                    offenders.append((name, mod))
    assert offenders == []


def test_no_hardcoded_secrets_in_source():
    # R8: no literal secrets assigned in shipped source.
    secret_re = re.compile(
        r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        re.IGNORECASE,
    )
    # Known-safe literals that are labels or validation messages, not credentials.
    benign = re.compile(r"password_hash|validate_password|password must|pbkdf2|session_token", re.IGNORECASE)
    offenders = []
    for path in _py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if secret_re.search(line) and not benign.search(line):
                offenders.append((str(path), lineno, line.strip()))
    assert offenders == []


def test_error_codes_expose_unavailable_not_zero():
    # R3/R5: the API surface declares explicit unavailable/insufficient codes.
    from app.errors import ErrorCode

    assert ErrorCode.insufficient_evidence.value == "insufficient_evidence"
    assert ErrorCode.model_unavailable.value == "model_unavailable"
    assert ErrorCode.provider_unavailable.value == "provider_unavailable"


def test_baseline_assumptions_state_indicator_not_probability():
    # R7: every rider-facing geometry statement is framed as an indicator/advisory.
    from app.baseline import ASSUMPTIONS

    joined = " ".join(ASSUMPTIONS).lower()
    assert "not an accident probability" in joined
    assert "advisory" in joined or "advisory band" in joined
