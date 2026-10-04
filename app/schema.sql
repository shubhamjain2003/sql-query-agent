CREATE TABLE Departments (DepartmentID INTEGER PRIMARY KEY, Name TEXT NOT NULL, Location TEXT);
CREATE TABLE Employees (EmployeeID INTEGER PRIMARY KEY, FirstName TEXT, LastName TEXT, Email TEXT,
  DepartmentID INTEGER REFERENCES Departments(DepartmentID), Salary REAL, HireDate TEXT);
CREATE TABLE Customers (CustomerID INTEGER PRIMARY KEY, Name TEXT, Email TEXT, City TEXT, State TEXT, CreatedAt TEXT);
CREATE TABLE Products (ProductID INTEGER PRIMARY KEY, Name TEXT, Category TEXT, Price REAL);
CREATE TABLE Orders (OrderID INTEGER PRIMARY KEY, CustomerID INTEGER REFERENCES Customers(CustomerID), OrderDate TEXT, Status TEXT);
CREATE TABLE OrderItems (OrderItemID INTEGER PRIMARY KEY, OrderID INTEGER REFERENCES Orders(OrderID),
  ProductID INTEGER REFERENCES Products(ProductID), Quantity INTEGER, UnitPrice REAL);

INSERT INTO Departments VALUES (1,'Engineering','Bengaluru'),(2,'Sales','Mumbai'),(3,'HR','Delhi');
INSERT INTO Employees VALUES
 (1,'Asha','Rao','asha@x.com',1,120000,'2023-03-15'),(2,'Ravi','Shah','ravi@x.com',1,95000,'2024-02-01'),
 (3,'Meera','Iyer','meera@x.com',2,70000,'2024-06-20'),(4,'Karan','Nair','karan@x.com',3,65000,'2022-11-05'),
 (5,'Zoya','Khan','zoya@x.com',2,82000,'2025-01-10');
INSERT INTO Customers VALUES
 (1,'Alice Brown','alice@c.com','Los Angeles','California','2023-05-01'),(2,'Bob Lee','bob@c.com','Austin','Texas','2023-07-12'),
 (3,'Cara Diaz','cara@c.com','San Diego','California','2024-01-03'),(4,'Dan Wu','dan@c.com','Seattle','Washington','2024-09-09');
INSERT INTO Products VALUES (1,'Laptop','Electronics',1200),(2,'Headphones','Electronics',150),(3,'Desk','Furniture',320),(4,'Chair','Furniture',210);
INSERT INTO Orders VALUES (1,1,'2024-02-10','Shipped'),(2,2,'2024-03-05','Pending'),(3,3,'2024-04-18','Shipped'),(4,1,'2024-05-22','Cancelled');
INSERT INTO OrderItems VALUES (1,1,1,1,1200),(2,1,2,2,150),(3,2,3,1,320),(4,3,4,2,210),(5,4,2,1,150);
