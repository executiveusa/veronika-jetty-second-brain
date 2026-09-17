from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_default_cors_is_not_wildcard():
    source=(ROOT/'backend/main.py').read_text(encoding='utf-8')
    assert 'PUBLIC_ORIGIN    = os.getenv("PUBLIC_ORIGIN", "http://localhost:4700")' in source
def test_env_example_names_explicit_origin():
    source=(ROOT/'.env.example').read_text(encoding='utf-8')
    assert 'ALLOWED_ORIGINS=http://localhost:4700' in source
