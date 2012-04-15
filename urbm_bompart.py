import types
import sqlite3
from urbm import Workspace

class bomPart:
	''' A part in the BOM exported from Eagle. '''
	
	@staticmethod
	def select_by_name(name, project, wspace):
		''' Return the bomPart(s) of given name. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE name=?' % project
			symbol = (name,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = bomPart(row[0], row[1], row[2], row[3], row[4], row[5])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
	
	@staticmethod
	def select_by_value(val, project, wspace):
		''' Return the bomPart(s) of given value in a list. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE value=?' % project
			symbol = (val,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = bomPart(row[0], row[1], row[2], row[3], row[4], row[5])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
		
	@staticmethod
	def select_by_product(prod, project, wspace):
		''' Return the bomPart(s) of given product in a list. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE product=?' % project
			symbol = (prod,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = bomPart(row[0], row[1], row[2], row[3], row[4], row[5])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
	
	def __init__(self, name, value, device, package, description='NULL', product='NULL'):
		self.name = name
		self.value = value
		self.device = device
		self.package = package
		self.description = description
		self.product = product

	def show(self):
		''' A simple print method. '''
		print 'Name: ', self.name, type(self.name)
		print 'Value: ', self.value, type(self.value)
		print 'Device: ', self.device, type(self.device)
		print 'Package: ', self.package, type(self.package)
		print 'Description: ', self.description, type(self.description)
		print 'Product: ', self.product, type(self.product)
		
	def equals(self, p):
		''' Compares the bomPart to another bomPart.'''
		if type(p) != type(self):
			return False
		eq = True
		if self.name != p.name:
			eq = False
		if self.value != p.value:
			eq = False
		if self.device != p.device:
			eq = False
		if self.package != p.package:
			eq = False
		if self.description != p.description:
			eq = False
		if self.product != p.product:
			eq = False
		return eq
		

	def findInFile(self, bomFile):
		''' Check if a BOM part of this name is in the given CSV BOM. '''
		with open(bomFile, 'rb') as f:
			db = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			rownum = 0
			for row in db:
				if row[0] == self.name:
					return rownum
				rownum = rownum + 1
			return -1
	
	def isInDB(self, project, wspace):
		''' Check if a BOM part of this name is in the project's database. '''
		result = bomPart.select_by_name(self.name, project, wspace)
		if len(result) == 0:
			return False
		else:
			return True
	
	def update(self, project, wspace):
		''' Update an existing bomPart record in the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
				
			sql = 'UPDATE %s SET name=?, value=?, device=?, package=?, description=?, product=? WHERE name=?' % project
			symbol = (self.name, self.value, self.device, self.package,  
					self.description, self.product, self.name,)
			cur.execute(sql, symbol)
			
		finally:
			cur.close()
			con.close()
	
	def insert(self, project, wspace):
		''' Write the bomPart to the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'INSERT OR REPLACE INTO %s VALUES (?,?,?,?,?,?)' % project
			symbol = (self.name, self.value, self.device, self.package,  
					self.description, self.product,)
			cur.execute(sql, symbol)
			
		finally:
			#con.commit()
			cur.close()
			con.close()
	
	def delete(self, project, wspace):
		''' Delete the bomPart from the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'DELETE FROM %s WHERE name=?' % project
			symbol = (self.name,)
			cur.execute(sql, symbol)
			
		finally:
			cur.close()
			con.close()
			