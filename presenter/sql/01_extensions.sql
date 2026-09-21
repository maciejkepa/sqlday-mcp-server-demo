-- Run only through presenter.prepare: one transaction, rollback on any failure.
IF DB_NAME() <> N'AdventureWorksLT_MCPDemo'
    THROW 51000, 'Refusing to change any database other than AdventureWorksLT_MCPDemo.', 1;
IF OBJECT_ID(N'SalesLT.SalesOrderHeader', 'U') IS NULL
    THROW 51001, 'Expected AdventureWorksLT (SalesLT), not full AdventureWorks.', 1;

IF SCHEMA_ID(N'Ops') IS NULL EXEC(N'CREATE SCHEMA Ops AUTHORIZATION dbo');
IF SCHEMA_ID(N'CRM') IS NULL EXEC(N'CREATE SCHEMA CRM AUTHORIZATION dbo');
IF SCHEMA_ID(N'Integration') IS NULL EXEC(N'CREATE SCHEMA Integration AUTHORIZATION dbo');
IF SCHEMA_ID(N'Catalog') IS NULL EXEC(N'CREATE SCHEMA Catalog AUTHORIZATION dbo');
IF SCHEMA_ID(N'Reporting') IS NULL EXEC(N'CREATE SCHEMA Reporting AUTHORIZATION dbo');
GO
IF OBJECT_ID(N'Ops.OrderFlags', 'U') IS NULL
CREATE TABLE Ops.OrderFlags (
    SalesOrderID int NOT NULL PRIMARY KEY REFERENCES SalesLT.SalesOrderHeader(SalesOrderID),
    RecognitionDate date NULL,
    IsCancelledOverride bit NOT NULL DEFAULT 0,
    IsInternal bit NOT NULL DEFAULT 0
);
IF OBJECT_ID(N'Ops.OrderEvent', 'U') IS NULL
BEGIN
    CREATE TABLE Ops.OrderEvent (
        EventID int IDENTITY PRIMARY KEY,
        SalesOrderID int NOT NULL REFERENCES SalesLT.SalesOrderHeader(SalesOrderID),
        EventType nvarchar(30) NOT NULL,
        OccurredAt datetime2 NOT NULL
    );
    CREATE INDEX IX_OrderEvent_Order ON Ops.OrderEvent(SalesOrderID);
END;
IF OBJECT_ID(N'CRM.CustomerIdentity', 'U') IS NULL
CREATE TABLE CRM.CustomerIdentity (
    CustomerID int NOT NULL PRIMARY KEY REFERENCES SalesLT.Customer(CustomerID),
    PartyKey nvarchar(80) NOT NULL
);
IF OBJECT_ID(N'Integration.CountryAlias', 'U') IS NULL
CREATE TABLE Integration.CountryAlias (
    RawCountry nvarchar(50) NOT NULL PRIMARY KEY,
    CanonicalCountry nvarchar(50) NOT NULL
);
IF OBJECT_ID(N'Catalog.ProductClassification', 'U') IS NULL
BEGIN
    CREATE TABLE Catalog.ProductClassification (
        ClassificationID int IDENTITY PRIMARY KEY,
        ProductID int NOT NULL REFERENCES SalesLT.Product(ProductID),
        ReportingCategory nvarchar(80) NOT NULL,
        EffectiveFrom date NOT NULL,
        EffectiveTo date NULL,
        CONSTRAINT CK_Classification_Dates CHECK (EffectiveTo IS NULL OR EffectiveTo >= EffectiveFrom),
        CONSTRAINT UQ_Classification_Start UNIQUE(ProductID, EffectiveFrom)
    );
END;
GO
CREATE OR ALTER TRIGGER Catalog.TR_ProductClassification_NoOverlap
ON Catalog.ProductClassification AFTER INSERT, UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (
        SELECT 1 FROM inserted AS i
        JOIN Catalog.ProductClassification AS c WITH (UPDLOCK, HOLDLOCK)
          ON c.ProductID=i.ProductID AND c.ClassificationID<>i.ClassificationID
         AND i.EffectiveFrom<=COALESCE(c.EffectiveTo, CONVERT(date,'99991231'))
         AND c.EffectiveFrom<=COALESCE(i.EffectiveTo, CONVERT(date,'99991231'))
    ) THROW 51002, 'Overlapping reporting classifications are not allowed.', 1;
END;
GO
-- Intentionally operational, not authoritative recognized revenue.
CREATE OR ALTER VIEW Reporting.SalesSummary AS
SELECT YEAR(OrderDate) AS OrderYear, DATEPART(quarter, OrderDate) AS OrderQuarter,
       SUM(SubTotal) AS Revenue, COUNT_BIG(*) AS OrderCount
FROM SalesLT.SalesOrderHeader
GROUP BY YEAR(OrderDate), DATEPART(quarter, OrderDate);

