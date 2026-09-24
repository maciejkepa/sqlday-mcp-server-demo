# Przykładowe pytania

1. Jaki był rozpoznany przychód netto ze sprzedaży zewnętrznej w Q1 2025? Podaj jedną wartość oraz krótko wyjaśnij, które zamówienia zostały uwzględnione lub wykluczone i dlaczego.

2. Który klient biznesowy wygenerował największy rozpoznany przychód netto w Q1 2025 i jaka była jego wartość? Traktuj różne rekordy klienta reprezentujące tę samą firmę jako jednego klienta biznesowego.

3. Pokaż rozpoznany przychód netto w Q1 2025 według kraju wysyłki. Kraje oznaczające ten sam kraj powinny zostać znormalizowane do jednej nazwy.

4. Pokaż rozpoznany przychód netto w Q1 2025 według raportowej kategorii produktu. Jeżeli klasyfikacja produktu zmieniała się w czasie, zastosuj klasyfikację obowiązującą w momencie rozpoznania przychodu.

5. Dla zamówień kwalifikujących się do rozpoznanego przychodu netto w Q1 2025 podaj: liczbę zamówień, liczbę pozycji zamówień, liczbę powiązanych eventów oraz łączny przychód netto. Wynik finansowy nie może zostać zawyżony przez relacje jeden-do-wielu.

## Oczekiwane odpowiedzi

### 1. Rozpoznany przychód netto

**3 200,00** — suma `SalesLT.SalesOrderDetail.LineTotal` dla trzech zamówień:

| Zamówienie (`PurchaseOrderNumber`) | Przychód netto | Data rozpoznania |
|---|---:|---|
| `MCP-A` | 1 300,00 | 2025-01-01 |
| `MCP-B` | 850,00 | 2025-02-15 |
| `MCP-C` | 1 050,00 | 2025-03-31 |

`MCP-A` należy do Q1 mimo daty zamówienia w grudniu 2024: decyduje
`Ops.OrderFlags.RecognitionDate`. Dla `MCP-C` ta wartość jest pusta,
więc datą rozpoznania jest `SalesLT.SalesOrderHeader.OrderDate`.

Wykluczone zamówienia:

| Zamówienie | Powód |
|---|---|
| `MCP-CANCEL` | Anulowane: `Status = 6` |
| `MCP-OVERRIDE` | Anulowane przez `IsCancelledOverride = 1`, mimo statusu 5 |
| `MCP-INTERNAL` | Sprzedaż wewnętrzna: `IsInternal = 1` |
| `MCP-APRIL` | Data rozpoznania 2025-04-01, poza Q1 |
| `MCP-DECEMBER` | Data rozpoznania 2024-12-31, poza Q1 |

Sumowanie `SalesOrderHeader.SubTotal` zamiast pozycji zamówień da błędny wynik.

### 2. Klient o największym przychodzie

**`NW-MOBILITY`: 2 150,00** (1 300,00 + 850,00).

Rekordy klientów `Northwest Mobility` i `NW Mobility Ltd` mają wspólny
`CRM.CustomerIdentity.PartyKey = 'NW-MOBILITY'`. Należy je zsumować jako jedną
firmę. Drugi klient, `BRITISH-CYCLES`, ma przychód 1 050,00.

### 3. Przychód według kraju wysyłki

| Kraj | Przychód netto |
|---|---:|
| United States | 2 150,00 |
| United Kingdom | 1 050,00 |

Kraj pochodzi z adresu wskazanego przez `ShipToAddressID`. Mapowanie
`Integration.CountryAlias` łączy `US` i `USA` w `United States`,
a `UK` zamienia na `United Kingdom`.

### 4. Przychód według raportowej kategorii produktu

| Kategoria raportowa | Przychód netto |
|---|---:|
| Bikes | 2 650,00 |
| Safety Gear | 300,00 |
| Services | 150,00 |
| Accessories | 100,00 |

Klasyfikację z `Catalog.ProductClassification` należy dobrać według daty
rozpoznania przychodu, z uwzględnieniem `EffectiveFrom` i `EffectiveTo`.
Kask w `MCP-A` należy do `Safety Gear`: przychód rozpoznano 2025-01-01.
Jego późniejsza klasyfikacja jako `Accessories`, obowiązująca od 2025-02-01,
nie zmienia wyniku historycznego.

### 5. Zamówienia, pozycje, eventy i przychód

| Miara | Wartość |
|---|---:|
| Liczba zamówień | 3 |
| Liczba pozycji zamówień | 6 |
| Liczba powiązanych eventów | 3 000 |
| Przychód netto | 3 200,00 |

Każde z zamówień `MCP-A`, `MCP-B` i `MCP-C` ma dwie pozycje oraz 1 000 eventów.
Pozycje i eventy należy agregować osobno do poziomu `SalesOrderID`, a następnie
połączyć wyniki. Bezpośrednie połączenie pozycji z eventami zwielokrotni wiersze
i zawyży sumę przychodu.
