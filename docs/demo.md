# Scenariusz prowadzącego — 25–30 minut

Ten dokument należy do środowiska prowadzącego. Agenci pracują tylko na wyeksportowanych stanowiskach.

## Przed sesją

1. Przygotuj Azure SQL, reset danych i czytelnika; uruchom `presenter.verify` i testy integracyjne.
2. Wdróż sprawdzony obraz, zapisz jego tag i URL. Zainstaluj zależności oraz inspektor na laptopie.
3. Sprawdź firewall i oba URL-e: lokalny oraz Azure. Nie aktualizuj zależności w dniu sesji.
4. Wyeksportuj trzy stanowiska, wybierz ten sam model i reasoning effort, wyłącz inne narzędzia.
5. Konto SQL do odczytu i token przygotuj przed udostępnieniem ekranu; usuń zmienne administratora.
6. Wykonaj trzy pełne próby. Nagraj jedną z nich i zachowaj ją lokalnie.

## Przebieg

| Minuty | Działanie | Co publiczność ma zobaczyć |
|---|---|---|
| 0–3 | Pytanie o przychód i prosty schemat | Dane i definicja miary to osobne problemy |
| 3–10 | Pokaż `app/server.py`, dopisz dekorator/narzędzie, uruchom Uvicorn i Inspector | Funkcja Python staje się odkrywalnym narzędziem z opisem i typami |
| 10–14 | Uruchom skrypt wdrożenia; w czasie budowania pokaż konfigurację Codex | Ten sam protokół i kod lokalnie oraz przez HTTPS |
| 14–24 | Dwa świeże okna Codex: pytania 1, 2 i 5 | Daty, tożsamość firmy i mnożenie wierszy przez eventy |
| 24–30 | Porównaj SQL i wyjaśnienia; powtórz pytanie z regułami w pliku | Wiedza pomaga także bez MCP; MCP standaryzuje dostęp i kontrolę |

Nie koduj na żywo: instalacji ODBC, reguł firewalla, całego seed SQL i infrastruktury.
Są przygotowane wcześniej i krótko objaśniane. Jeśli budowanie obrazu przekracza okno czasowe,
kontynuuj z działającą wcześniejszą rewizją i pokaż wynik publikacji na końcu.

## Co sprawdzić w odpowiedziach

- P1: pozycje zamówień, rozpoznanie przychodu, status 6, override i zamówienia wewnętrzne.
- P2: połączenie dwóch CustomerID w NW-MOBILITY; bez przypadkowego grupowania po nazwie.
- P3: ShipToAddressID i mapowanie US/USA na United States.
- P4: historyczna Safety Gear, mimo że późniejsza klasyfikacja hełmu to Accessories.
- P5: niezależne agregacje linii i eventów; nie sumować przychodu po zwielokrotnieniu zamówień.

Wyniki referencyjne są w `presenter/verify.py` oraz `Pytania.md`. Nie wklejaj tych plików
do rozmowy, nie otwieraj repo prowadzącego w oknie agenta, nie udostępniaj wykonanych wcześniej SQL.

## Protokół trzech prób

Dla każdego pytania uruchom osobną świeżą rozmowę, maksymalnie 180 sekund. Najpierw oceniaj
poprawność liczbową i reguły, dopiero potem czas. Odpowiedź „nie wiem” nie jest halucynacją;
liczby bez pokrycia i niepoparte wyjaśnienia zapisuj osobno. Nie wybieraj tylko najlepszych prób.

Skopiuj poniższy nagłówek do prywatnego CSV i zapisz 5 pytań × 3 warianty × 3 próby:

```csv
trial,question,variant,model,reasoning_effort,elapsed_seconds,sql_calls,failed_calls,numeric_correct,rules_correct,unsupported_claims,notes
```

Porównuj medianę czasu osobno dla poprawnych odpowiedzi, odsetek poprawności oraz liczbę
nieudanych wywołań. Logi MCP podają czas narzędzia, nie czas całej odpowiedzi agenta.
SQL CLI zwraca `elapsed_ms`; pozostałe metryki odczytaj z przebiegu rozmowy.

## Awaria

- Publikacja: użyj wcześniej sprawdzonej rewizji Azure.
- Hosting MCP: zmień URL na lokalny `http://127.0.0.1:8000/mcp`, pozostaw tę samą bazę.
- SQL lub internet: pokaż lokalne nagranie i prywatne wyniki prób; nie przedstawiaj ich jako przebiegu na żywo.

## Gotowość

- [ ] `ruff`, testy lokalne i kompilacja Bicep przeszły.
- [ ] Kontener zbudowany; SQL przygotowany; pięć wyników referencyjnych zgodnych.
- [ ] Smoke test po HTTPS z poprawnym i błędnym tokenem.
- [ ] Wszystkie scenariusze sprawdzone przez Codex w obu głównych wariantach.
- [ ] Próba kontrolna z regułami w pliku.
- [ ] Trzy próby zapisane; kopia nagrania dostępna bez sieci.
