WITH LineRevenue AS (
    SELECT SalesOrderID, SUM(LineTotal) AS Revenue, COUNT_BIG(*) AS LineCount
    FROM SalesLT.SalesOrderDetail GROUP BY SalesOrderID
), EligibleOrders AS (
    SELECT h.SalesOrderID, h.CustomerID, h.ShipToAddressID, l.Revenue, l.LineCount,
           CONVERT(date, COALESCE(f.RecognitionDate, h.OrderDate)) AS RecognitionDate
    FROM SalesLT.SalesOrderHeader AS h
    JOIN LineRevenue AS l ON l.SalesOrderID=h.SalesOrderID
    LEFT JOIN Ops.OrderFlags AS f ON f.SalesOrderID=h.SalesOrderID
    WHERE h.Status<>6 AND COALESCE(f.IsCancelledOverride,0)=0 AND COALESCE(f.IsInternal,0)=0
      AND COALESCE(f.RecognitionDate,h.OrderDate)>='20250101'
      AND COALESCE(f.RecognitionDate,h.OrderDate)<'20250401'
)
SELECT COALESCE(c.CanonicalCountry,a.CountryRegion,N'[unmapped]') AS Country,
       CAST(SUM(e.Revenue) AS decimal(19,4)) AS Revenue
FROM EligibleOrders AS e
LEFT JOIN SalesLT.Address AS a ON a.AddressID=e.ShipToAddressID
LEFT JOIN Integration.CountryAlias AS c ON c.RawCountry=a.CountryRegion
GROUP BY COALESCE(c.CanonicalCountry,a.CountryRegion,N'[unmapped]')
ORDER BY Revenue DESC, Country;
