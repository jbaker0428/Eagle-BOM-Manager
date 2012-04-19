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
				part.fetch_attributes(wspace)
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
				part.fetch_attributes(wspace)
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
				part.fetch_attributes(wspace)
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
	
	def __init__(self, name, project, value, device, package, description='NULL', product='NULL', attributes={}):
		self.name = name
		self.project = project
		self.value = value
		self.device = device
		self.package = package
		self.description = description
		self.product = product
		self.attributes = attributes

	def show(self):
		''' A simple print method. '''
		print 'Name: ', self.name, type(self.name)
		print 'Project', self.project, type(self.project)
		print 'Value: ', self.value, type(self.value)
		print 'Device: ', self.device, type(self.device)
		print 'Package: ', self.package, type(self.package)
		print 'Description: ', self.description, type(self.description)
		print 'Product: ', self.product, type(self.product)
		for attrib in self.attributes.items():
			print attrib[0], ': ', attrib[1]
		
	def equals(self, p, check_foreign_attribs=True):
		''' Compares the Part to another Part.
		The check_foreign_attribs argument (default True) controls whether or not
		p.attributes.keys() is checked for members not in self.attributes.keys().
		The reverse is always checked. '''
		if type(p) != type(self):
			return False
		eq = True
		if self.name != p.name:
			eq = False
		elif self.project != p.project:
			eq = False
		elif self.value != p.value:
			eq = False
		elif self.device != p.device:
			eq = False
		elif self.package != p.package:
			eq = False
		elif self.description != p.description:
			eq = False
		elif self.product != p.product:
			eq = False
		for k in self.attributes.keys():
			if k not in p.attributes.keys():
				eq = False
			else:
				if self.attributes[k].equals(p.attributes[k]) == False:
					eq = False
		if check_foreign_attribs is True:
			for k in p.attributes.keys():
				if k not in self.attributes.keys():
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
		This allows for parts in different projects that incidentally have the same name to be added.
		Only returns parts that have all of the attributes of in self.attributes
		(with equal values). This behavior is equivalent to self.equals(some_part, False). '''
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
				part.fetch_attributes(wspace)
				attribs_eq = True
				for k in self.attributes.keys():
					if k not in part.attributes.keys():
						attribs_eq = False
					else:
						if self.attributes[k].equals(part.attributes[k]) == False:
							attribs_eq = False
				if attribs_eq is True:
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
						part.fetch_attributes(wspace)
						attribs_eq = True
						for k in self.attributes.keys():
							if k not in part.attributes.keys():
								attribs_eq = False
							else:
								if self.attributes[k].equals(part.attributes[k]) == False:
									attribs_eq = False
						if attribs_eq is True:
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
			self.write_attributes(wspace)
			
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
			self.write_attributes(wspace)
			
		finally:
			cur.close()
			con.close()
	
	def delete(self, wspace):
		''' Delete the Part from the DB. 
		Part attributes are deleted via foreign key constraint cascading. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'DELETE FROM parts WHERE name=? AND project=?'
			symbol = (self.name, self.project)
			cur.execute(sql, symbol)
			
		finally:
			cur.close()
			con.close()
	
	def fetch_attributes(self, wspace):
		''' Fetch attributes dictionary for this Part. 
		Clears and sets the self.attributes dictionary directly. '''
		self.attributes.clear()
		try:
			(con, cur) = wspace.con_cursor()
			
			params = (self.name, self.project,)
			cur.execute('''SELECT name, value FROM part_attributes WHERE part=? INTERSECT 
			SELECT name, value FROM part_attributes WHERE project=?''', params)
			for row in cur.fetchall():
				self.attributes[row[0]] = row[1]
			
		finally:
			cur.close()
			con.close()
	
	def has_attribute(self, attrib, wspace):
		'''Check if this Part has an attribute of given name in the DB. 
		Ignores value of the attribute. '''
		results = []
		try:
			(con, cur) = wspace.con_cursor()
			
			params = (self.name, self.project, attrib,)
			cur.execute('''SELECT name FROM part_attributes WHERE part=? INTERSECT 
			SELECT name FROM part_attributes WHERE project=? INTERSECT 
			SELECT name FROM part_attributes WHERE name=?''', params)
			for row in cur.fetchall():
				results.append(row[0])
			
		finally:
			cur.close()
			con.close()
			if len(results) == 0:
				return False
			else:
				return True

	def write_attributes(self, wspace):
		''' Write all of this Part's attributes to the DB.
		Checks attributes currently in DB and updates/inserts as appropriate. '''
		db_attribs = []
		old_attribs = []
		new_attribs = []
		try:
			(con, cur) = wspace.con_cursor()
			
			params = (self.name, self.project,)
			cur.execute('''SELECT name FROM part_attributes WHERE part=? INTERSECT 
			SELECT name FROM part_attributes WHERE project=?''', params)
			for row in cur.fetchall():
				db_attribs.append(row[0])
			for a in self.attributes.items():
				if a[0] in db_attribs:
					old_attribs.append((a[1], self.name, self.project, a[0]))
				else:
					new_attribs.append((self.name, self.project, a[0], a[1]))
			
			cur.executemany('INSERT OR REPLACE INTO part_attributes VALUES (NULL,?,?,?,?)', new_attribs)
			cur.executemany('UPDATE part_attributes SET value=? WHERE part=? AND project=? AND name=?', old_attribs)
		
		finally:
			cur.close()
			con.close()
