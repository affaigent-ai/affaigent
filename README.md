Affaigent

Affaigent is een persoonlijke AI-assistent voor meerdere gescheiden identiteiten en contexten.
De focus ligt op hoge antwoordkwaliteit, minimale hallucinaties, onderhoudbaarheid, veiligheid en uitbreidbaarheid.

Doel

Affaigent moet uitgroeien van werkende backend naar een bruikbare persoonlijke assistent die:

•	context per identiteit gescheiden houdt
•	gesprekken via Telegram en later via een webinterface kan voeren
•	relevante geheugenfragmenten kan ophalen vóór antwoordgeneratie
•	later memory write-back, GitHub-automatisering, browseracties en extra connectoren ondersteunt
•	op termijn zelfstandig delen van de eigen inrichting en codebase kan onderhouden binnen veilige grenzen

Huidige status

Werkend:

•	Infra op VPS staat
•	Docker stack draait
•	Postgres, Redis, Qdrant en embeddings-service draaien
•	FastAPI backend draait
•	Chatcontext per chat wordt opgeslagen in Postgres
•	Telegram worker draait via systemd
•	Normale Telegram-tekstberichten werken zonder slash-commando's
•	Slash-commando's blijven beschikbaar als fallback
•	/chat/respond werkt met Gemini
•	Retrieval vóór antwoordgeneratie werkt live
•	Semantic search via Qdrant werkt
•	Identity-aware chatcontext werkt

Nog niet af:

•	Memory write-back na antwoorden
•	Claude-route
•	GitHub App-integratie in de applicatie
•	LibreChat-webinterface
•	Browser/agentlaag
•	Volledige autonome onderhoudsflows

Identiteiten en chatcontext

Actieve identities:

•	dennis_work
•	dennis_private
•	linsey_work
•	linsey_private
•	shared_private

Actieve chatkoppeling:

•	Dennis privéchat → default dennis_work, toegestaan: dennis_work, dennis_private, shared_private
•	Linsey privéchat → default linsey_work, toegestaan: linsey_work, linsey_private, shared_private
•	Gedeelde groepschat → alleen shared_private

Technische stack

Server en runtime
•	Ubuntu 24.04 LTS
•	Docker Compose
•	systemd

Backend
•	Python 3.12
•	FastAPI
•	Uvicorn

Data en retrieval
•	Postgres 16
•	Redis 7
•	Qdrant 1.16.3
•	Hugging Face Text Embeddings Inference (CPU)

Modelrouting
•	Primair werkend: Google Gemini (gemini-2.5-flash)
•	OpenAI-route is nu niet bruikbaar door quota issues
•	Claude wordt later toegevoegd

Belangrijke paden

/opt/affaigent/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── llm.py
│   │   │   ├── schemas.py
│   │   │   ├── model_router.py
│   │   │   ├── chat_contexts.py
│   │   │   ├── chat_state.py
│   │   │   ├── embeddings.py
│   │   │   ├── qdrant.py
│   │   │   ├── db.py
│   │   │   └── config.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── qdrant-image/
├── config/
│   ├── postgres/
│   └── security/
├── infra/
│   └── docker/
│       ├── docker-compose.yml
│       └── .env
├── scripts/
│   ├── telegram_command_worker.py
│   ├── smoke_memory_pipeline.sh
│   └── security scripts...
├── data/          # niet in Git
├── logs/          # niet in Git
└── backups/       # niet in Git

Services

Let op: de Docker Compose service heet api, maar de container heet affaigent-api.

Belangrijkste services:

•	api → container affaigent-api
•	postgres → container affaigent-postgres
•	redis → container affaigent-redis
•	qdrant → container affaigent-qdrant
•	embeddings → container affaigent-embeddings

Belangrijkste flows

Telegram chatflow
1. Telegram ontvangt bericht
2. scripts/telegram_command_worker.py haalt updates op
3. Worker bepaalt chat_key
4. Worker haalt huidige chatcontext op via /chat-context/current
5. Worker stuurt normaal tekstbericht door naar /chat/respond
6. API doet retrieval
7. LLM genereert antwoord
8. Worker stuurt antwoord terug naar Telegram

Retrieval flow
1. Memory entry wordt opgeslagen in Postgres
2. Entry wordt gechunked
3. Chunks worden embedded via de embeddings-service
4. Vectors worden opgeslagen in Qdrant
5. Bij /chat/respond wordt semantic search uitgevoerd op basis van identity_key
6. Top hits worden samengevoegd tot retrieval-context
7. Die context wordt meegegeven aan het model
8. Model geeft antwoord terug met retrieval_count

Belangrijkste API-routes

Gezondheid en context
•	GET /health
•	GET /contexts
•	GET /chat-context
•	GET /chat-context/current
•	POST /chat-context/select

Memory
•	POST /memory/entries
•	GET /memory/entries
•	GET /memory/entries/{memory_id}
•	POST /memory/entries/{memory_id}/chunk
•	POST /memory/entries/{memory_id}/embed
•	POST /memory/search/semantic

Chat
•	GET /model-route
•	POST /chat/respond

Telegram-commando's

Fallback-commando's die nu werken:

•	/start
•	/health
•	/context
•	/work
•	/private
•	/shared

Normale tekstberichten werken ook.

Operationele commando's

Docker stack
cd /opt/affaigent/infra/docker
docker compose ps
docker compose logs api --tail 100
docker compose build api
docker compose up -d --force-recreate api

API direct testen
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/contexts

Telegram worker
systemctl status affaigent-telegram-worker.service --no-pager
journalctl -u affaigent-telegram-worker.service -n 100 --no-pager
sudo systemctl restart affaigent-telegram-worker.service

Python syntax check
python3 -m py_compile /opt/affaigent/apps/api/app/main.py
python3 -m py_compile /opt/affaigent/apps/api/app/llm.py
python3 -m py_compile /opt/affaigent/apps/api/app/schemas.py
python3 -m py_compile /opt/affaigent/scripts/telegram_command_worker.py

Git workflow

Gebruik Git altijd als baseline voor werkende toestand.

Regels
•	commit geen .env bestanden
•	commit geen keys of .pem bestanden
•	commit geen runtime data
•	commit geen backupbestanden
•	commit geen logs

Normale flow
git status
git add .
git commit -m "Beschrijvende commit message"
git push

Secrets en veiligheid

Niet committen:

•	infra/docker/.env
•	GitHub App private keys
•	SSH private keys
•	runtime state
•	database data
•	logs

Bekend open risico:

•	een eerder gebruikte Gemini API-key is blootgesteld geweest en moet later worden geroteerd

Huidige webinterface-richting

Telegram is nu de werkende chatinterface.
De geplande professionele webinterface is LibreChat, maar die is nog niet gekoppeld.

Ontwikkelrichting vanaf hier

Logische vervolgstappen:

1. GitHub-baseline afronden
2. Memory write-back ontwerpen
3. GitHub App integreren
4. LibreChat koppelen
5. Browser-/agentlaag toevoegen
6. Claude als extra hoogwaardige route toevoegen
7. Veilige autonome onderhoudsflows bouwen

Developer-notities

•	Retrieval werkt live
•	Compose service naam is api, niet affaigent-api
•	Containernaam en servicenaam verschillen
•	Als codewijzigingen niet live lijken, rebuild dan de api service en niet alleen een container restart
•	Deze README moet actueel gehouden worden bij elke betekenisvolle architectuur- of workflowwijziging
