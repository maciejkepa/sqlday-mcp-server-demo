# SQLDay: AdventureWorksLT + MCP + Codex

Serwer MCP w Pythonie udostępniający bazę AdventureWorksLT do analiz przez Codex.
Agent poznaje schemat i reguły biznesowe, a następnie wykonuje zapytania T-SQL przez
trzy narzędzia: `get_schema`, `get_business_rules` i `query_sql`.
Reguły są dostępne również jako zasób `adventureworks://business-rules`.

**[Przykładowe pytania](docs/example-questions.md)** ·
**[Reguły biznesowe](docs/business-rules.md)** ·
**[Przygotowanie bazy i Azure](docs/azure-setup.md)**

## Wymagania

- Python 3.12 i [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Microsoft ODBC Driver 18 for SQL Server: [Windows](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
  lub [Ubuntu](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server).
  Sterownik musi mieć architekturę zgodną z Pythonem.
- Przygotowana baza `AdventureWorksLT_MCPDemo` i konto SQL do odczytu.
  Dane do połączenia otrzymasz od prowadzącego; własną bazę przygotujesz według
  [instrukcji Azure](docs/azure-setup.md).
- Node.js z npm do instalacji Codex CLI.

Polecenia poniżej uruchamiaj z katalogu repozytorium. Mają tę samą składnię na
Windowsie (cmd lub PowerShell) i Ubuntu (Bash), bez aktywowania środowiska wirtualnego.
W WSL instaluj Python, uv, ODBC i Codex po stronie Ubuntu.

## Uruchomienie serwera

Zainstaluj zależności i utwórz lokalną konfigurację:

```sh
uv sync --frozen
uv run --frozen python -m scripts.configure
```

Skrypt tworzy `.env` z losowym hasłem czytelnika i tokenem MCP. Nie nadpisuje istniejącego
pliku. Dla istniejącej bazy zastąp `AW_SQL_PASSWORD` otrzymanym hasłem. Uzupełnij:

| Zmienna | Wartość |
|---|---|
| `AW_SQL_SERVER` | Adres serwera, np. `your-server.database.windows.net` |
| `AW_SQL_DATABASE` | `AdventureWorksLT_MCPDemo` |
| `AW_SQL_USER` | Konto do odczytu, domyślnie `aw_demo_reader` |
| `AW_SQL_PASSWORD` | Hasło tego konta |
| `AW_MCP_TOKEN` | Losowy token, co najmniej 32 znaki |
| `AW_ALLOWED_HOSTS` | Dozwolone hosty, domyślnie `localhost,127.0.0.1` |

`.env` zawiera lokalne sekrety i jest ignorowany przez Git. Na firewallu SQL musi być
dopuszczony publiczny adres IP komputera uruchamiającego serwer.

```sh
uv run --frozen --env-file .env uvicorn app.server:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --log-config app/logging.json
```

Endpoint MCP: `http://127.0.0.1:8000/mcp`. Pozostaw ten terminal otwarty.
W drugim terminalu sprawdź uwierzytelnienie, narzędzia i połączenie z bazą:

```sh
uv run --frozen --env-file .env python -m scripts.smoke --url http://127.0.0.1:8000/mcp
```

`http://127.0.0.1:8000/health` sprawdza tylko działanie procesu.
Plik `.env` jest ładowany przez `--env-file`, nie przez samą aplikację.

### Docker

Docker instaluje Python i ODBC wewnątrz obrazu. Potrzebujesz Docker Engine na Ubuntu
lub Docker Desktop z kontenerami Linux na Windowsie oraz uzupełnionego `.env`.

```sh
docker build -t adventureworks-mcp .
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 adventureworks-mcp
```

## Instalacja i podłączenie Codex CLI

Zainstaluj Codex przez npm, a następnie zaloguj się:

```sh
npm install -g @openai/codex
codex login
```

Dodaj uruchomiony serwer:

```sh
codex mcp add adventureworks --url http://127.0.0.1:8000/mcp --bearer-token-env-var AW_MCP_TOKEN
codex mcp list
```

Konfiguracja jest zapisywana w `~/.codex/config.toml` (na Windowsie w katalogu
użytkownika). Uruchom Codex z tokenem załadowanym z `.env`:

```sh
uv run --frozen --env-file .env codex
```

W Codex wpisz `/mcp` i sprawdź dostępność narzędzi serwera `adventureworks`.
Następnie użyj pytania z [docs/example-questions.md](docs/example-questions.md), np.:

> Użyj narzędzi MCP AdventureWorks. Jaki był rozpoznany przychód netto ze sprzedaży
> zewnętrznej w Q1 2025? Podaj wartość i wyjaśnij zastosowane reguły biznesowe.

Dla serwera udostępnionego przez prowadzącego użyj jego adresu HTTPS `/mcp` i tokenu.
Nie musisz wtedy uruchamiać własnego serwera ani mieć dostępu SQL.
Token musi być dostępny w środowisku procesu Codex; `codex mcp list` potwierdza
konfigurację, a `/mcp` pozwala sprawdzić połączenie. Ten serwer używa tokenu Bearer,
więc nie wymaga `codex mcp login`.

Instrukcje: [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
i [konfiguracja MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
Sam serwer MCP nie potrzebuje klucza OpenAI; Codex wymaga własnego logowania.

## Porównanie z dostępem bez MCP

Eksporter tworzy dwa katalogi: `with-mcp` z konfiguracją MCP i `without-mcp`
z interfejsem SQL CLI. Oba zawierają te same pytania. Eksportuj poza repozytorium,
aby agent nie widział danych przygotowujących demo i zapytań referencyjnych:

```sh
uv run --frozen python -m scripts.export_workspaces --destination ../sqlday-workspaces --url http://127.0.0.1:8000/mcp
```

Zależności SQL CLI zainstaluj raz, również z głównego katalogu repozytorium:

```sh
uv sync --directory ../sqlday-workspaces/without-mcp --frozen --no-dev
```

Następnie otwórz dwa terminale **w głównym katalogu repozytorium**, gdzie znajduje
się uzupełniony `.env`, i uruchom po jednym wariancie:

```sh
uv run --frozen --env-file .env python -m scripts.run_codex ../sqlday-workspaces/with-mcp
```

```sh
uv run --frozen --env-file .env python -m scripts.run_codex ../sqlday-workspaces/without-mcp
```

Launcher przekazuje Codexowi katalog pracy przez `-C`. Zmienne `AW_*` wybiera
z konfiguracji wczytanej z `.env`: `with-mcp` otrzymuje tylko `AW_MCP_TOKEN`,
a `without-mcp` wyłącznie dane połączenia SQL czytelnika. Zmienne administratora
są usuwane ze środowiska obu procesów. Pliku `.env` nie trzeba kopiować ani
montować w wyeksportowanych katalogach. `uv` jest programem zainstalowanym
w systemie; nie musi znajdować się w każdym katalogu projektu.

Zaakceptuj zaufanie do `with-mcp`, aby Codex odczytał projektowy
`.codex/config.toml`, i sprawdź połączenie przez `/mcp`. Launcher wyłącza
`adventureworks` w wariancie `without-mcp`, również gdy serwer jest skonfigurowany
globalnie. SQL CLI dziedziczy dane czytelnika z procesu Codex i nie wymaga
lokalnego `.env`. Przy porównaniu użyj tego samego modelu i nowej rozmowy
dla każdego pytania.

## Struktura projektu

| Katalog | Zawartość |
|---|---|
| `app/` | Narzędzia MCP, autoryzacja, SQL CLI, metadane i walidacja zapytań |
| `docs/` | Pytania, reguły biznesowe i instrukcja Azure |
| `scripts/` | Konfiguracja, Azure CLI, smoke test i eksport katalogów demo |
| `presenter/` | Przygotowanie danych, zapytania referencyjne i weryfikacja wyników |
| `infra/` | Szablony Bicep bazy, rejestru i Container App |
| `tests/` | Testy lokalne bez dostępu do Azure SQL |

## Walidacja i diagnostyka

```sh
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest -q
```

- `401`: sprawdź zgodność `AW_MCP_TOKEN` w serwerze i Codex.
- `421`: dopisz hostname endpointu do `AW_ALLOWED_HOSTS` i uruchom serwer ponownie.
- `SQL_UNAVAILABLE`: sprawdź ODBC, dane logowania i firewall SQL.
- `SQL_INVALID`: sprawdź składnię T-SQL, nazwy kolumn i uprawnienia czytelnika.

`query_sql` przyjmuje jedno zapytanie SELECT/CTE do dozwolonych obiektów.
Limit wynosi 15 sekund, 200 wierszy i 64 KiB wyniku JSON. `truncated=true` oznacza
niepełny wynik. Konto SQL do odczytu stanowi dodatkowe ograniczenie uprawnień.
Kwoty są zwracane jako ciągi dziesiętne, a daty w ISO 8601.
