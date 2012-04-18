import types
import sqlite3
from manager import Workspace

class Part:
	''' A part in the BOM exported from Eagle. '''
	
	@staticmethod
	def select_by_name(name, wspace, project='*'):
		''' Return the Part(s) of given name. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = "SELECT * FROM parts WHERE name=? and project='%s'" % project
			symbol = (name,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
	
	@staticmethod
	def select_by_value(val, wspace, project='*'):
		''' Return the Part(s) of given value in a list. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = "SELECT * FROM parts WHERE value=? and project='%s'" % project
			symbol = (val,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
		
	@staticmethod
	def select_by_product(prod, wspace, project='*'):
		''' Return the Part(s) of given product in a list. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = "SELECT * FROM parts WHERE product=? and project='%s'" % project
			symbol = (prod,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
	
	def __init__(self, name, project, value, device, package, description='NULL', product='NULL'):
		self.name = name
		self.project = project
		self.value = value
		self.device = device
		self.package = package
		self.description = description
		self.product = product

	def show(self):
		''' A simple print method. '''
		print 'Name: ', self.name, type(self.name)
		print 'Project', self.project, type(self.project)
		print 'Value: ', self.value, type(self.value)
		print 'Device: ', self.device, type(self.device)
		print 'Package: ', self.package, type(self.package)
		print 'Description: ', self.description, type(self.description)
		print 'Product: ', self.product, type(self.product)
		
	def equals(self, p):
		''' Compares the Part to another Part.'''
		if type(p) != type(self):
			return False
		eq = True
		if self.name != p.name:
			eq = False
		if self.project != p.project:
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
		

	def findInFile(self, bom_file):
		''' Check if a BOM part of this name is in the given CSV BOM. '''
		with open(bom_file, 'rb') as f:
			db = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			rownum = 0
			for row in db:
				if row[0] == self.name:
					return rownum
				rownum = rownum + 1
			return -1
	
	def find_similar_parts(self, project, wspace, check_wspace=True):
		''' Search the project and optionally workspace for parts of matching value/device/package.
		If check_wspace = True, returns a pair of lists: (project_results, workspace_results).
		If check_wspace = False, only returns the project_results list. 
		The contents of the workspace_results list are pairs: (project, Part). 
		This allows for parts in different projects that incidentally have the same name to be added. '''
		# Can pass these returned lists to a new version of find_matching_products with a similar return pair
		# New version of find_matching_prods, boolean optional (default True) arg for "check workspace"
		project_results = set()
		workspace_results = set()
		try:
			(con, cur) = wspace.con_cursor()
			sql = """SELECT DISTINCT * FROM parts WHERE value=? AND project=? INTERSECT
				SELECT * FROM parts WHERE device=? AND project=? INTERSECT
				SELECT * FROM parts WHERE package=? AND project=?"""
			t = (self.value, self.project, self.device, self.project, self.package, self.project,)
			cur.execute(sql, t)
			rows = cur.fetchall()
			for row in rows:
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
				project_results.add(part)
					
			if check_wspace:
				for proj in wspace.list_projects():
					if proj == project:
						continue	# Do not re-check the passed project
					sql = """SELECT DISTINCT * FROM parts WHERE value=? AND project!=? INTERSECT
						SELECT * FROM parts WHERE device=? AND project!=? INTERSECT
						SELECT * FROM parts WHERE package=? AND project!=?"""
					t = (self.value, self.project, self.device, self.project, self.package, self.project,)
					cur.execute(sql, t)
					rows = cur.fetchall()
					for row in rows:
						part = Part(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
						workspace_results.add((proj, part))
							
		finally:
			cur.close()
			con.close()
			if check_wspace:
				return (list(project_results), list(workspace_results))
			else:
				return list(project_results)
		
	def find_matching_products(self, wspace):
		''' Search all projects in a Workspace for Parts with the same value/device/pakage.
		Checks the search results for non-NULL product columns.
		Return a set of candidate Product objects for this Part.'''
		#print 'Entering %s.find_matching_products...' % self.name
		products = set()
		try:
			from product import Product
			(con, cur) = wspace.con_cursor()
			sql = """SELECT DISTINCT product FROM parts WHERE value=? INTERSECT
			SELECT product FROM parts WHERE device=? INTERSECT
			SELECT product FROM parts WHERE package=?"""
			t = (self.value, self.device, self.package,)
			cur.execute(sql, t)
			rows = cur.fetchall()
			for row in rows:
				if row[0] != 'NULL':
					db_prods = Product.select_by_pn(row[0], wspace)
					#print 'Found db_prods: ', db_prods
					for p in db_prods:
						products.add(p)
		finally:
			cur.close()
			con.close()
			return products
	
	def is_in_db(self, wspace):
		''' Check if a BOM part of this name is in the project's database. '''
		result = Part.select_by_name(self.name, wspace, self.project)
		if len(result) == 0:
			return False
		else:
			return True
	
	def update(self, wspace):
		''' Update an existing Part record in the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
				
			sql = 'UPDATE parts SET name=?, project=?, value=?, device=?, package=?, description=?, product=? WHERE name=? AND project=?'
			symbol = (self.name, self.project, self.value, self.device, self.package,  
					self.description, self.product, self.name, self.project,)
			cur.execute(sql, symbol)
			
		finally:
			cur.close()
			con.close()
	
	def insert(self, wspace):
		''' Write the Part to the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'INSERT OR REPLACE INTO parts VALUES (?,?,?,?,?,?,?)'
			symbol = (self.name, self.project, self.value, self.device, self.package,  
					self.description, self.product,)
			cur.execute(sql, symbol)
			
		finally:
			cur.close()
			con.close()
	
	def delete(self, wspace):
		''' Delete the Part from the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'DELETE FROM parts WHERE name=? AND project=?'
			symbol = (self.name, self.project)
			cur.execute(sql, symbol)
			
		finally:
			cur.close()
			con.close()
			