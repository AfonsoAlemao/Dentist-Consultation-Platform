--
-- Basic company schema creation
--
DROP TABLE IF EXISTS contract;
DROP TABLE IF EXISTS permanent;
DROP TABLE IF EXISTS freelancer;
DROP TABLE IF EXISTS works_at;
DROP TABLE IF EXISTS department;
DROP TABLE IF EXISTS employee;

CREATE TABLE employee(
    eid NUMERIC(9),
    name VARCHAR(80),
    birthdate DATE,
    PRIMARY KEY(eid)
);

CREATE TABLE department(
	did	INTEGER,
	name VARCHAR(20),
	location VARCHAR(40),
	mid INTEGER,
	PRIMARY KEY(did),
	UNIQUE(name),
	FOREIGN KEY (mid) REFERENCES employee(eid)
);

CREATE TABLE works_at(
    eid NUMERIC(9),
    did INTEGER,
    since DATE,
    PRIMARY key(eid),
    FOREIGN KEY(eid) REFERENCES employee(eid),
    FOREIGN KEY(did) REFERENCES department(did)
);

--
-- Basic company data population
--

INSERT INTO employee VALUES(1, 'Alice', '10-10-1995');
INSERT INTO employee VALUES(2, 'Bob', '03-02-1996');
INSERT INTO employee VALUES(3, 'Caroline', '04-04-1971');
INSERT INTO employee VALUES(4, 'Daniel', '04-04-1998');
INSERT INTO employee VALUES(5, 'Eduard', '10-03-1960');
INSERT INTO employee VALUES(6, 'Florence', NULL);
INSERT INTO employee VALUES(7, 'Gabriel', '02-11-1983');

INSERT INTO department VALUES(1, 'Finance', 'Buraca', 1);
INSERT INTO department VALUES(2, 'Marketing', 'Damaia', 2);
INSERT INTO department VALUES(3, 'Sales', 'Chelas', 3);

INSERT INTO works_at VALUES(1, 1, '03-03-2016');
INSERT INTO works_at VALUES(2, 2, '02-04-2017');
INSERT INTO works_at VALUES(3, 3, '10-05-2017');
INSERT INTO works_at VALUES(4, 3, '10-04-2017');
INSERT INTO works_at VALUES(5, 3, '01-01-2018');

--
-- Company contract schema creation
--

CREATE TABLE freelancer(
	eid NUMERIC(9),
	job VARCHAR(30) NOT NULL,
	hour_rate NUMERIC(6,2) NOT NULL,
	PRIMARY KEY(eid),
	FOREIGN KEY(eid) REFERENCES employee(eid)
);

CREATE TABLE permanent(
	eid NUMERIC(9),
	PRIMARY KEY(eid),
	FOREIGN KEY(eid) REFERENCES employee(eid)
);

CREATE TABLE contract(
	eid NUMERIC(9),
	role VARCHAR(30) NOT NULL,
	salary NUMERIC(6,2) NOT NULL,
	PRIMARY KEY(eid, role),
	FOREIGN KEY(eid) REFERENCES permanent(eid)
);
