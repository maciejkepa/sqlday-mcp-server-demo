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
SELECT COALESCE(c.ReportingCategory,N'[unmapped]') AS ReportingCategory,
       CAST(SUM(d.LineTotal) AS decimal(19,4)) AS Revenue
FROM EligibleOrders AS e
JOIN SalesLT.SalesOrderDetail AS d ON d.SalesOrderID=e.SalesOrderID
LEFT JOIN Catalog.ProductClassification AS c
  ON c.ProductID=d.ProductID AND e.RecognitionDate>=c.EffectiveFrom
 AND (c.EffectiveTo IS NULL OR e.RecognitionDate<=c.EffectiveTo)
GROUP BY COALESCE(c.ReportingCategory,N'[unmapped]')
ORDER BY Revenue DESC, ReportingCategory;
