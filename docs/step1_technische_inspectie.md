# Affaigent – technische inspectie (stap 1)

Datum: 2026-04-24

## Korte samenvatting
- De basisstack is functioneel opgezet, maar heeft enkele duidelijke inconsistenties tussen API-validatie, identity-configuratie en compose/runtime-afhankelijkheden.
- De belangrijkste risico's zitten in: identity-validatie die niet overeenkomt met de beoogde contexten, ontbrekende dependency-healthchecks (embeddings/reranker), beperkte startup-robustness en onvoldoende expliciete security boundaries op API-niveau.
- Voor stap 1 is een kleine, veilige diff-set voldoende: alignen van identity literals, healthchecks/dependencies aanscherpen, en minimale logging/startup-hardening zonder architectuurwijziging.

## Risicobestanden / paden
1. `apps/api/app/schemas.py`
   - `IdentityKey` bevat alleen `dennis_work`, `linsey_work`, `shared_private` en mist `dennis_private` en `linsey_private`.
   - Effect: valide runtime-contexten uit config/router kunnen op requestniveau onterecht falen.

2. `apps/api/app/config.py`
   - `identities` bevat 5 identity keys, wat niet matcht met schema-literals.
   - Model-defaults en env-afhankelijkheden zijn aanwezig, maar zonder centrale startup-validatie op verplichte secrets per actief profiel.

3. `apps/api/app/main.py`
   - Lifespan initialiseert Qdrant-collectie en context-tabel direct; bij externe dependencies kan startup hard falen zonder gecontroleerde retry/backoff.
   - In `/chat/respond` worden retrieval-fouten stil geslikt (`except Exception:`), waardoor observability laag is.
   - Geen gestructureerde logging (niveau, requestcontext, afhankelijkheidsstatus).

4. `infra/docker/docker-compose.yml`
   - `api` hangt af van `postgres`, `redis`, `qdrant`, maar niet van `embeddings`; retrieval/chat kan daardoor falen terwijl container als healthy wordt gezien.
   - `build.context` verwijst naar een absolute hostpad (`/opt/affaigent/apps/api`) i.p.v. repo-relatief pad; dit vergroot drift en verlaagt reproduceerbaarheid.
   - Alleen `api`, `postgres`, `redis`, `qdrant` hebben healthcheck; embeddings/reranker missen healthchecks.

5. `README.md`
   - Beschrijft operationele status die deels afwijkt van code/config defaults (modelkeuzes, identity-set).
   - Risico op operationele misinterpretatie tijdens incidenten.

## Minimaal en veilig herstelplan (logische volgorde)
1. **Identity-consistentie herstellen (laag risico, hoge impact)**
   - Breng `IdentityKey` in `schemas.py` in lijn met `settings.identities`.
   - Doel: API-validatie consistent maken met core-contextbeleid.

2. **Compose dependency/healthcheck hardening**
   - Voeg healthchecks toe voor `embeddings` (en optioneel `reranker`).
   - Maak `api.depends_on` expliciet afhankelijk van `embeddings` health.
   - Houd wijzigingen beperkt tot readiness; geen architectuurwijziging.

3. **Startup robustness API (minimaal)**
   - Voeg beperkte startup-logging toe rondom init-stappen (`ensure_collection`, `ensure_chat_context_state_table`).
   - Voeg gecontroleerde retry (korte bounded backoff) toe voor Qdrant-init.

4. **Observability verbeteren zonder functionele wijziging**
   - Vervang stille `except Exception` in retrievalpad door logging + veilige fallback.
   - Uniforme logvelden: endpoint, identity_key, dependency, fouttype.

5. **Config hygiene**
   - Voeg een `.env.example`/documentatiecheck toe (alleen keys, geen secrets) om drift te beperken.
   - Geen secrets in repo; alleen structuur en required vars vastleggen.

## Voorstel eerstvolgende concrete wijziging
**Start met stap 1: identity-consistentie in de API-schema’s.**

Reden:
- Kleinste veilige wijziging.
- Vermindert directe functionele fouten in memory/search/chat-routes.
- Sluit aan op architectuurregel dat Affaigent core de regie voert over identiteit/context.

Concreet:
- In `apps/api/app/schemas.py` `IdentityKey` uitbreiden met:
  - `dennis_private`
  - `linsey_private`

## Voorstel minimale diff-set voor stap 1
1. `apps/api/app/schemas.py`
   - Alleen aanpassen van `IdentityKey` literalset naar 5 identities.

2. (optioneel maar veilig) `apps/api/app/main.py`
   - Geen functionele codewijziging nodig voor stap 1.
   - Eventueel alleen commentaar/docstring om identity-bron van waarheid te duiden.

3. `README.md` (optioneel in zelfde of aparte mini-commit)
   - Korte notitie dat schema-identities gelijk moeten lopen met `settings.identities`.

> Geen brede refactor, geen nieuwe componenten, geen verschuiving van verantwoordelijkheden naar n8n.
