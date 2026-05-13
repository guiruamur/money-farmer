# crypto-farmer

Servicio local de señales de cripto con IA local (Ollama) + RAG + feedback in-context. Fase 1 según [docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md](docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md).

## Requisitos

- Python 3.11+
- Ollama corriendo localmente con los modelos `qwen2.5:7b-instruct-q4_K_M` y `nomic-embed-text` descargados (`ollama pull <modelo>`).
- Cuenta en Telegram con un bot creado (BotFather) y el `chat_id` de destino.
- Token de CryptoPanic (free tier disponible).

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env             # rellenar con tus secretos
copy config\config.example.yaml config\config.yaml
```

Editar `config/config.yaml` para ajustar pares, umbrales, etc. Las claves quedan en `.env`.

## Verificar que arranca (un solo ciclo)

```powershell
python -m crypto_farmer --config config/config.yaml --run-once
```

Debe terminar sin errores y crear `data/crypto_farmer.db` con un row en `cycles`.

## Ejecución 24/7

```powershell
python -m crypto_farmer --config config/config.yaml
```

El proceso queda corriendo. Cada 15 min ejecuta un ciclo. Los outcomes a 1h/4h/24h se miden automáticamente. Las señales con confianza >= 60 se envían al chat configurado.

## Comandos del bot

Una vez el proceso esté corriendo, escribe en tu chat de Telegram:

- `/status` — estado del sistema y último ciclo
- `/last` — últimas 5 señales
- `/stats` — win rate y distribución reciente
- `/pair BTC/USDT` — resumen de un par concreto
- `/pause` y `/resume` — controlar el scheduler
- `/health` — comprobar conectividad de subsistemas
- `/config` — config actual (secretos redactados)

## Tests

```powershell
pytest                                              # unit + integration con fakes (rápido)
$env:RUN_LLM_TESTS = "1"; pytest -m llm             # tests opt-in contra Ollama real
```

## Estructura

Ver [docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md](docs/design/specs/2026-05-12-crypto-farmer-fase1-design.md) sección 2.2.

## Backups

Diariamente: copiar `data/crypto_farmer.db` y `data/memory/` a `data/backups/YYYY-MM-DD/`. Ver `scripts/backup.ps1`.

Programar como tarea diaria (PowerShell, no requiere admin si va en tu usuario):

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File C:\Users\germ1\Proyectos\money-farmer\scripts\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName "crypto-farmer-backup" -Action $action -Trigger $trigger
```

## Aviso

Fase 1 NO ejecuta órdenes reales. Solo genera y entrega señales. No tomes decisiones de inversión basándote únicamente en este sistema; está en validación.
