IF DB_NAME() <> N'AdventureWorksLT_MCPDemo'
    THROW 51000, 'Refusing to reset a non-demo database.', 1;

-- Only sales transactions in the explicitly named copy are replaced.
DELETE FROM Ops.OrderEvent;
DELETE FROM Ops.OrderFlags;
DELETE FROM SalesLT.SalesOrderDetail;
DELETE FROM SalesLT.SalesOrderHeader;
DELETE FROM CRM.CustomerIdentity;
DELETE FROM Integration.CountryAlias;
DELETE FROM Catalog.ProductClassification;

INSERT SalesLT.Customer (NameStyle, FirstName, LastName, CompanyName, EmailAddress,
                         PasswordHash, PasswordSalt)
SELECT 0, v.FirstName, N'Demo', v.CompanyName, v.Email, N'NOT-A-LOGIN', N'DEMO'
FROM (VALUES
    (N'Ada', N'Northwest Mobility', N'mcp-a@example.invalid'),
    (N'Alex', N'NW Mobility Ltd', N'mcp-b@example.invalid'),
    (N'Sam', N'British Cycles', N'mcp-c@example.invalid')
) AS v(FirstName, CompanyName, Email)
WHERE NOT EXISTS (SELECT 1 FROM SalesLT.Customer AS c WHERE c.EmailAddress=v.Email);

INSERT SalesLT.Address (AddressLine1, City, StateProvince, CountryRegion, PostalCode)
SELECT v.Line1, N'Demo City', N'Demo Region', v.Country, N'00000'
FROM (VALUES (N'SQLDay shipping A', N'US'), (N'SQLDay shipping B', N'USA'),
             (N'SQLDay shipping C', N'UK')) AS v(Line1, Country)
WHERE NOT EXISTS (SELECT 1 FROM SalesLT.Address AS a WHERE a.AddressLine1=v.Line1);

INSERT SalesLT.ProductCategory (Name)
SELECT v.Name FROM (VALUES (N'MCP Operational Bikes'), (N'MCP Operational Accessories')) AS v(Name)
WHERE NOT EXISTS (SELECT 1 FROM SalesLT.ProductCategory AS c WHERE c.Name=v.Name);

INSERT SalesLT.Product (Name, ProductNumber, StandardCost, ListPrice, ProductCategoryID, SellStartDate)
SELECT v.Name, v.Number, 0, v.Price, c.ProductCategoryID, CONVERT(datetime,'20200101')
FROM (VALUES
    (N'SQLDay bicycle', N'MCP-BIKE', 1000, N'MCP Operational Bikes'),
    (N'SQLDay helmet', N'MCP-HELMET', 300, N'MCP Operational Accessories'),
    (N'SQLDay service', N'MCP-SERVICE', 150, N'MCP Operational Accessories'),
    (N'SQLDay accessory', N'MCP-ACCESSORY', 100, N'MCP Operational Accessories')
) AS v(Name, Number, Price, Category)
JOIN SalesLT.ProductCategory AS c ON c.Name=v.Category
WHERE NOT EXISTS (SELECT 1 FROM SalesLT.Product AS p WHERE p.ProductNumber=v.Number);

INSERT CRM.CustomerIdentity (CustomerID, PartyKey)
SELECT CustomerID, CASE WHEN EmailAddress IN (N'mcp-a@example.invalid', N'mcp-b@example.invalid')
                       THEN N'NW-MOBILITY' ELSE N'BRITISH-CYCLES' END
FROM SalesLT.Customer
WHERE EmailAddress IN (N'mcp-a@example.invalid', N'mcp-b@example.invalid', N'mcp-c@example.invalid');

INSERT Integration.CountryAlias VALUES
    (N'US', N'United States'), (N'USA', N'United States'), (N'United States', N'United States'),
    (N'UK', N'United Kingdom'), (N'United Kingdom', N'United Kingdom');

INSERT Catalog.ProductClassification (ProductID, ReportingCategory, EffectiveFrom, EffectiveTo)
SELECT p.ProductID, v.Category, CONVERT(date,v.DateFrom), CONVERT(date,v.DateTo)
FROM (VALUES
    (N'MCP-BIKE', N'Bikes', '20200101', NULL),
    (N'MCP-HELMET', N'Safety Gear', '20200101', '20250131'),
    (N'MCP-HELMET', N'Accessories', '20250201', NULL),
    (N'MCP-SERVICE', N'Services', '20200101', NULL),
    (N'MCP-ACCESSORY', N'Accessories', '20200101', NULL)
) AS v(Number, Category, DateFrom, DateTo)
JOIN SalesLT.Product AS p ON p.ProductNumber=v.Number;

DECLARE @Orders TABLE (
    Code nvarchar(10), Email nvarchar(50), AddressLine nvarchar(60),
    OrderDate date, RecognitionDate date, Status tinyint,
    CancelOverride bit, IsInternal bit, HeaderTotal money
);
INSERT @Orders VALUES
    (N'A', N'mcp-a@example.invalid', N'SQLDay shipping A', '20241215','20250101',5,0,0,1600),
    (N'B', N'mcp-b@example.invalid', N'SQLDay shipping B', '20250215','20250215',5,0,0,950),
    (N'C', N'mcp-c@example.invalid', N'SQLDay shipping C', '20250331',NULL,5,0,0,1200),
    (N'CANCEL', N'mcp-a@example.invalid', N'SQLDay shipping A', '20250210','20250210',6,0,0,999),
    (N'OVERRIDE', N'mcp-a@example.invalid', N'SQLDay shipping A', '20250210','20250210',5,1,0,888),
    (N'INTERNAL', N'mcp-a@example.invalid', N'SQLDay shipping A', '20250210','20250210',5,0,1,777),
    (N'APRIL', N'mcp-a@example.invalid', N'SQLDay shipping A', '20250331','20250401',5,0,0,666),
    (N'DECEMBER', N'mcp-a@example.invalid', N'SQLDay shipping A', '20250101','20241231',5,0,0,555);

INSERT SalesLT.SalesOrderHeader (RevisionNumber, OrderDate, DueDate, Status, OnlineOrderFlag,
    PurchaseOrderNumber, CustomerID, ShipToAddressID, BillToAddressID, ShipMethod,
    SubTotal, TaxAmt, Freight)
SELECT 0, o.OrderDate, DATEADD(day,7,o.OrderDate), o.Status, 0,
       N'MCP-'+o.Code, c.CustomerID, a.AddressID, a.AddressID, N'SQLDay Demo',
       o.HeaderTotal, 0, 0
FROM @Orders AS o
JOIN SalesLT.Customer AS c ON c.EmailAddress=o.Email
JOIN SalesLT.Address AS a ON a.AddressLine1=o.AddressLine;

INSERT Ops.OrderFlags (SalesOrderID, RecognitionDate, IsCancelledOverride, IsInternal)
SELECT h.SalesOrderID, o.RecognitionDate, o.CancelOverride, o.IsInternal
FROM @Orders AS o JOIN SalesLT.SalesOrderHeader AS h ON h.PurchaseOrderNumber=N'MCP-'+o.Code;

INSERT SalesLT.SalesOrderDetail (SalesOrderID, OrderQty, ProductID, UnitPrice, UnitPriceDiscount)
SELECT h.SalesOrderID, 1, p.ProductID, v.Price, 0
FROM (VALUES
    (N'A', N'MCP-BIKE', 1000), (N'A', N'MCP-HELMET', 300),
    (N'B', N'MCP-BIKE', 750), (N'B', N'MCP-ACCESSORY', 100),
    (N'C', N'MCP-BIKE', 900), (N'C', N'MCP-SERVICE', 150),
    (N'CANCEL', N'MCP-BIKE', 999), (N'OVERRIDE', N'MCP-BIKE', 888),
    (N'INTERNAL', N'MCP-BIKE', 777), (N'APRIL', N'MCP-BIKE', 666),
    (N'DECEMBER', N'MCP-BIKE', 555)
) AS v(Code, Number, Price)
JOIN SalesLT.SalesOrderHeader AS h ON h.PurchaseOrderNumber=N'MCP-'+v.Code
JOIN SalesLT.Product AS p ON p.ProductNumber=v.Number;

-- Restore intentionally inconsistent header amounts even if a source database has line triggers.
UPDATE h SET SubTotal=o.HeaderTotal
FROM SalesLT.SalesOrderHeader AS h JOIN @Orders AS o ON h.PurchaseOrderNumber=N'MCP-'+o.Code;

WITH Digits AS (
    SELECT n FROM (VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) AS v(n)
), Numbers AS (
    SELECT a.n + 10*b.n + 100*c.n AS n FROM Digits AS a CROSS JOIN Digits AS b CROSS JOIN Digits AS c
)
INSERT Ops.OrderEvent (SalesOrderID, EventType, OccurredAt)
SELECT h.SalesOrderID, N'StatusObserved', DATEADD(second,n.n,CONVERT(datetime2,'20250331'))
FROM SalesLT.SalesOrderHeader AS h CROSS JOIN Numbers AS n
WHERE h.PurchaseOrderNumber IN (N'MCP-A', N'MCP-B', N'MCP-C');

IF (SELECT COUNT(*) FROM SalesLT.SalesOrderHeader) <> 8
    THROW 51003, 'Unexpected customer/address duplication or seed cardinality.', 1;
IF (SELECT COUNT(*) FROM SalesLT.SalesOrderDetail) <> 11
    THROW 51004, 'Unexpected seed line count.', 1;
IF (SELECT COUNT(*) FROM Ops.OrderEvent) <> 3000
    THROW 51005, 'Unexpected seed event count.', 1;

