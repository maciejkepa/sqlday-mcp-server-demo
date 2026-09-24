# Przygotowanie bazy i wdrożenie do Azure

Wszystkie polecenia uruchamiaj z głównego katalogu repozytorium. Wymagają
[Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli),
Python 3.12, uv oraz zależności z `uv sync --frozen`.
Wstaw własne wartości zamiast `YOUR_SUBSCRIPTION`, `YOUR_PUBLIC_IPV4`,
`YOUR_SQL_SERVER` i `YOUR_UNIQUE_REGISTRY`. Nazwa serwera SQL w argumentach CLI
nie zawiera `.database.windows.net`.

## Baza danych

```sh
az login
az account set --subscription YOUR_SUBSCRIPTION
az group create --name sqlday-demo-rg --location westeurope
uv run --frozen python -m scripts.configure --admin
uv run --frozen --env-file .env.admin python -m scripts.azure database --resource-group sqlday-demo-rg --client-ip YOUR_PUBLIC_IPV4
```

`configure --admin` tworzy `.env` z danymi czytelnika i `.env.admin` z danymi
administratora. Pliki zawierają sekrety w postaci tekstowej, są ignorowane przez Git
i nie trafiają do obrazu. Skrypt odmawia nadpisania istniejących plików.
Dla istniejącej konfiguracji zachowaj hasła i utwórz brakujący `.env.admin` ręcznie:

```dotenv
AW_ADMIN_USER=sqldayadmin
AW_ADMIN_PASSWORD=your-existing-admin-password
```

Polecenie `database` tworzy Azure SQL Basic z próbką AdventureWorksLT i regułą
firewalla `sqlday-presenter` dla podanego adresu IP. Wpisz zwrócony FQDN do
`AW_SQL_SERVER` w `.env`, a następnie przygotuj dane:

```sh
uv run --frozen --env-file .env --env-file .env.admin python -m presenter.prepare --reset-demo
uv run --frozen --env-file .env python -m presenter.verify
```

`--reset-demo` zastępuje transakcje sprzedaży danymi demonstracyjnymi, dodaje
schematy biznesowe i tworzy konto `aw_demo_reader`. Operacja jest transakcyjna
i przyjmuje wyłącznie bazę `AdventureWorksLT_MCPDemo`. Konto czytelnika otrzymuje
SELECT oraz dostęp do metadanych 13 dozwolonych obiektów. Weryfikacja wykonuje
pięć zapytań z `presenter/reference/` i porównuje wyniki z oczekiwanymi wartościami.

Alternatywnie skopiuj istniejącą bazę AdventureWorksLT na tym samym serwerze,
a następnie wykonaj powyższe przygotowanie danych:

```sh
uv run --frozen python -m scripts.azure copy-database --resource-group sqlday-demo-rg --sql-server YOUR_SQL_SERVER --source-database AdventureWorksLT
```

Kopiowanie odmawia nadpisania istniejącej bazy demo. Przy tej ścieżce skonfiguruj
hasło istniejącego administratora w `.env.admin` oraz regułę firewalla:

```sh
az sql server firewall-rule create --resource-group sqlday-demo-rg --server YOUR_SQL_SERVER --name sqlday-presenter --start-ip-address YOUR_PUBLIC_IPV4 --end-ip-address YOUR_PUBLIC_IPV4
```

Tej samej komendy użyj po zmianie publicznego IP stanowiska lokalnego.

## Serwer MCP w Azure Container Apps

Konto wdrażające potrzebuje uprawnień do zasobów i przypisania roli `AcrPull`.
Docker lokalnie nie jest wymagany; obraz buduje Azure Container Registry.

```sh
uv run --frozen --env-file .env python -m scripts.azure deploy --resource-group sqlday-demo-rg --sql-resource-group sqlday-demo-rg --sql-server YOUR_SQL_SERVER --registry-name YOUR_UNIQUE_REGISTRY --app-name sqlday-mcp --client-ip YOUR_PUBLIC_IPV4
```

Polecenie tworzy rejestr, buduje obraz z jawnej listy plików aplikacji, wdraża
Container App i aktualizuje firewall SQL. Parametry sekretne trafiają do Bicep
przez plik tymczasowy usuwany po wykonaniu polecenia. Zwrócony URL kończy się `/mcp`.
Kolejne wdrożenia powinny używać tych samych nazw zasobów. Opcja
`--image-tag demo-v1` pozwala nadać obrazowi konkretny tag.

```sh
uv run --frozen --env-file .env python -m scripts.smoke --url https://YOUR_APP_FQDN/mcp
```

Po zmianie adresów wyjściowych aplikacji zaktualizuj firewall:

```sh
uv run --frozen python -m scripts.azure firewall --resource-group sqlday-demo-rg --sql-resource-group sqlday-demo-rg --sql-server YOUR_SQL_SERVER --app-name sqlday-mcp --client-ip YOUR_PUBLIC_IPV4
```

Aktualizacja zarządza wyłącznie regułami z prefiksem `mcp-<app-name>-`.
Nie włącza dostępu dla wszystkich usług Azure. Reguły firewalla serwera SQL
obejmują wszystkie jego bazy.

## Koszty i utrzymanie

Szablony tworzą SQL Basic, rejestr Basic, Log Analytics i jedną replikę Container App
(0,5 vCPU, 1 GiB). Zasoby naliczają opłaty również między uruchomieniami demo.
Po zakończeniu usuń zasoby, których już nie potrzebujesz. Statyczny token Bearer
jest wspólnym poświadczeniem demo; ten serwer nie implementuje OAuth.

Dokumentacja: [parametry Bicep](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/parameter-files),
[budowanie obrazu w ACR](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-tutorial-quick-task),
[firewall SQL](https://learn.microsoft.com/en-us/cli/azure/sql/server/firewall-rule).
