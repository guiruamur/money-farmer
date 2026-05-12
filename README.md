# crypto-farmer

Servicio local de señales cripto con IA local. Fase 1 según `docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md`.

## Setup
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env  # rellenar valores
copy config\config.example.yaml config\config.yaml
```

## Ejecutar
```bash
python -m crypto_farmer
```

## Tests
```bash
pytest
```
