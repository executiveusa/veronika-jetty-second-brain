from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPOSED = "072090156d28a9df6502d94083e47990"


def test_exposed_database_credential_is_not_in_current_tracked_source():
    checked = [
        ROOT / "backend" / "main.py",
        ROOT / "docker-compose.yml",
        ROOT / ".env.example",
    ]
    assert all(EXPOSED not in path.read_text(encoding="utf-8") for path in checked)


def test_database_dsn_has_no_code_default():
    backend = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert 'os.getenv("VERONIKA_PG_DSN", "")' in backend
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${VERONIKA_PG_DSN:?" in compose
