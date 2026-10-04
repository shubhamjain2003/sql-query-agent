from app import db
from app.validator import validate

db.init_db()
S, F = db.get_schema(), db.get_fks()
ok = lambda q: validate(q, S, F)


def test_valid_query():
    assert ok("SELECT * FROM Employees WHERE HireDate >= '2024-01-01';") == []


def test_valid_join_and_alias():
    assert ok("SELECT c.Name, COUNT(o.OrderID) AS n FROM Customers c JOIN Orders o ON c.CustomerID = o.CustomerID GROUP BY c.Name ORDER BY n DESC") == []


def test_unknown_table_and_column():
    assert any("Unknown table" in e for e in ok("SELECT * FROM Staff"))
    assert any("does not exist" in e for e in ok("SELECT e.Bonus FROM Employees e"))


def test_destructive_blocked():
    for q in ["DELETE FROM Employees", "DROP TABLE Orders", "UPDATE Employees SET Salary=1",
              "INSERT INTO Products VALUES (9,'x','y',1)", "ALTER TABLE Orders ADD x INT", "TRUNCATE TABLE Orders"]:
        assert ok(q), q


def test_multi_statement_blocked():
    assert ok("SELECT 1; DROP TABLE Orders;")


def test_bad_join_relationship():
    assert any("not a defined relationship" in e for e in ok("SELECT * FROM Employees e JOIN Orders o ON e.EmployeeID = o.OrderID"))
