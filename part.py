import types
import sqlite3
from manager import Workspace
from product import Product

class Part:
	''' A self in the BOM exported from Eagle. '''
	
	@staticmethod
	def select_by_name(name, wspace, project='*', connection=None):
		''' Return the Part(s) of given name. '''
		parts = []
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
			
			sql = "SELECT * FROM parts WHERE name=? and project='%s'" % project
			symbol = (name,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
				part.fetch_attributes(wspace)
				parts.append(part)
			
		finally:
			cur.close()
			if connection is None:
				con.close()
			return parts
	
	@staticmethod
	def select_by_value(val, wspace, project='*', connection=None):
		''' Return the Part(s) of given value in a list. '''
		parts = []
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
			
			sql = "SELECT * FROM parts WHERE value=? and project='%s'" % project
			symbol = (val,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
				part.fetch_attributes(wspace)
				parts.append(part)
			
		finally:
			cur.close()
			if connection is None:
				con.close()
			return parts
		
	@staticmethod
	def select_by_product(prod, wspace, project='*', connection=None):
		''' Return the Part(s) of given product in a list. '''
		parts = []
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
			
			sql = "SELECT * FROM parts WHERE product=? and project='%s'" % project
			symbol = (prod,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5], row[6])
				part.fetch_attributes(wspace)
				parts.append(part)
			
		finally:
			cur.close()
			if connection is None:
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
			if self.attributes[k] != "":
				if k not in p.attributes.keys():
					eq = False
				else:
					if self.attributes[k].equals(p.attributes[k]) == False:
						eq = False
		if check_foreign_attribs is True:
			for k in p.attributes.keys():
				if p.attributes[k] != "":
					if k not in self.attributes.keys():
						eq = False
		return eq
		

	def findInFile(self, bom_file):
		''' Check if a BOM self of this name is in the given CSV BOM. '''
		with open(bom_file, 'rb') as f:
			db = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			rownum = 0
			for row in db:
				if row[0] == self.name:
					return rownum
				rownum = rownum + 1
			return -1
	
	def find_similar_parts(self, wspace, check_wspace=True, connection=None):
		''' Search the project and optionally workspace for parts of matching value/device/package/attributes.
		If check_wspace = True, returns a pair of lists: (project_results, workspace_results).
		If check_wspace = False, only returns the project_results list. 
		This allows for parts in different projects that incidentally have the same name to be added.
		Only returns parts that have all of the non-empty attributes in self.attributes
		(with equal values). This behavior is equivalent to self.equals(some_part, False). '''
		project_results = set()
		workspace_results = set()
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
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
					if self.attributes[k] != "":
						if k not in part.attributes.keys():
							attribs_eq = False
						else:
							if self.attributes[k].equals(part.attributes[k]) == False:
								attribs_eq = False
				if attribs_eq is True:
					project_results.add(part)
					
			if check_wspace:
				for proj in wspace.list_projects():
					if proj == self.project:
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
							if self.attributes[k] != "":
								if k not in part.attributes.keys():
									attribs_eq = False
								else:
									if self.attributes[k].equals(part.attributes[k]) == False:
										attribs_eq = False
						if attribs_eq is True:
							workspace_results.add(part)
							
		finally:
			cur.close()
			if connection is None:
				con.close()
			if check_wspace:
				return (list(project_results), list(workspace_results))
			else:
				return (list(project_results), [])
	
	def find_matching_products(self, wspace, proj_parts, wspace_parts, connection=None):
		''' Takes in the output of self.find_similar_parts. 
		Returns a list of Product objects.'''
		# TODO : Find more results by searching the product_attributes table
		products = set()
		for part in proj_parts:
			if part.product != 'NULL':
				db_prods = Product.select_by_pn(part.product, wspace)
				for prod in db_prods:
					products.add(prod)
		
		for part in wspace_parts:
			if part.product != 'NULL':
				db_prods = Product.select_by_pn(part.product, wspace)
				for prod in db_prods:
					products.add(prod)
	
		return list(products)
	
	def is_in_db(self, wspace, connection=None):
		''' Check if a BOM self of this name is in the project's database. '''
		result = Part.select_by_name(self.name, wspace, self.project)
		if len(result) == 0:
			return False
		else:
			return True
	
	def product_updater(self, wspace, connection=None):
		''' Checks if the Part is already in the DB. 
		Inserts/updates self into DB depending on:
		- The presence of a matching Part in the DB
		- The value of self.product
		- The product of the matching Part in the DB '''
		if(self.is_in_db(wspace)):
			print "Part of same name already in DB"
			old_part = Part.select_by_name(self.name, wspace, self.project)[0]
			#old_part.show()
			if(self.value == old_part.value and self.device == old_part.device and self.package == old_part.package):
				if self.product != 'NULL':
					if old_part.product != 'NULL':
						# TODO: prompt? Defaulting to old_part.product for now (aka do nothing)
						print 'Matching CSV and DB parts with non-NULL product mismatch, keeping DB version...'
					elif old_part.product == 'NULL':
						self.update(wspace)
				elif self.product == 'NULL':
					if old_part.product != 'NULL':
						pass	# Do nothing in this case
					elif old_part.product == 'NULL':
						(candidate_proj_parts, candidate_wspace_parts) = self.find_similar_parts(wspace)
						candidate_products = self.find_matching_products(wspace, candidate_proj_parts, candidate_wspace_parts)
						if len(candidate_products) == 0:
							#print 'No matching products found, nothing to do'
							pass
						elif len(candidate_products) == 1:
							self.product = candidate_products[0].manufacturer_pn
							print 'Found exactly one matching product, setting product and updating', #self.show()
							self.update(wspace)
						else:
							print 'Found multiple product matches, prompting for selection...'
							# TODO: Currently going with first result, need to prompt for selection
							self.product = candidate_products[0].manufacturer_pn
							self.update(wspace)
						
			else:	# Value/device/package mismatch
				if self.product != 'NULL':
					self.update(wspace)
				elif self.product == 'NULL':
					(candidate_proj_parts, candidate_wspace_parts) = self.find_similar_parts(wspace)
					candidate_products = self.find_matching_products(wspace, candidate_proj_parts, candidate_wspace_parts)
					if len(candidate_products) == 0:
						print 'No matching products found, updating as-is'
					elif len(candidate_products) == 1:
						self.product = candidate_products[0].manufacturer_pn
						print 'Found exactly one matching product, setting product and updating'#, self.show()
					else:
						print 'Found multiple product matches, prompting for selection...'
						# TODO: Currently going with first result, need to prompt for selection
						self.product = candidate_products[0].manufacturer_pn
					self.update(wspace)
		
		else:
			print 'Part not in DB'
			if self.product == 'NULL':
				(candidate_proj_parts, candidate_wspace_parts) = self.find_similar_parts(wspace)
				candidate_products = self.find_matching_products(wspace, candidate_proj_parts, candidate_wspace_parts)
				if len(candidate_products) == 0:
					print 'No matching products found, inserting as-is'#, self.show()
				elif len(candidate_products) == 1:
					self.product = candidate_products[0].manufacturer_pn
					print 'Found exactly one matching product, setting product and inserting'#, self.show()
				else:
					print 'Found multiple product matches, prompting for selection...'
					# TODO: Currently going with first result, need to prompt for selection
					self.product = candidate_products[0].manufacturer_pn
			else:
				newprod = Product('NULL', self.product)
				newprod.insert(wspace)
				newprod.scrape(wspace)
			self.insert(wspace)
		
	def update(self, wspace, connection=None):
		''' Update an existing Part record in the DB. '''
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
				
			sql = 'UPDATE parts SET name=?, project=?, value=?, device=?, package=?, description=?, product=? WHERE name=? AND project=?'
			symbol = (self.name, self.project, self.value, self.device, self.package,  
					self.description, self.product, self.name, self.project,)
			cur.execute(sql, symbol)
			self.write_attributes(wspace)
			
		finally:
			cur.close()
			if connection is None:
				con.close()
	
	def insert(self, wspace, connection=None):
		''' Write the Part to the DB. '''
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
			
			sql = 'INSERT OR REPLACE INTO parts VALUES (?,?,?,?,?,?,?)'
			symbol = (self.name, self.project, self.value, self.device, self.package,  
					self.description, self.product,)
			cur.execute(sql, symbol)
			self.write_attributes(wspace)
			
		finally:
			cur.close()
			if connection is None:
				con.close()
	
	def delete(self, wspace, connection=None):
		''' Delete the Part from the DB. 
		Part attributes are deleted via foreign key constraint cascading. '''
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
			
			sql = 'DELETE FROM parts WHERE name=? AND project=?'
			symbol = (self.name, self.project)
			cur.execute(sql, symbol)
			
		finally:
			cur.close()
			if connection is None:
				con.close()
	
	def fetch_attributes(self, wspace, connection=None):
		''' Fetch attributes dictionary for this Part. 
		Clears and sets the self.attributes dictionary directly. '''
		self.attributes.clear()
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
			
			params = (self.name, self.project,)
			cur.execute('''SELECT name, value FROM part_attributes WHERE part=? INTERSECT 
			SELECT name, value FROM part_attributes WHERE project=?''', params)
			for row in cur.fetchall():
				self.attributes[row[0]] = row[1]
			
		finally:
			cur.close()
			if connection is None:
				con.close()
	
	def has_attribute(self, attrib, wspace, connection=None):
		'''Check if this Part has an attribute of given name in the DB. 
		Ignores value of the attribute. '''
		results = []
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
			
			params = (self.name, self.project, attrib,)
			cur.execute('''SELECT name FROM part_attributes WHERE part=? INTERSECT 
			SELECT name FROM part_attributes WHERE project=? INTERSECT 
			SELECT name FROM part_attributes WHERE name=?''', params)
			for row in cur.fetchall():
				results.append(row[0])
			
		finally:
			cur.close()
			if connection is None:
				con.close()
			if len(results) == 0:
				return False
			else:
				return True

	def write_attributes(self, wspace, connection=None):
		''' Write all of this Part's attributes to the DB.
		Checks attributes currently in DB and updates/inserts as appropriate. '''
		db_attribs = []
		old_attribs = []
		new_attribs = []
		try:
			if connection is None:
				(con, cur) = wspace.con_cursor()
			else:
				con = connection
				cur = con.cursor()
			
			params = (self.name, self.project,)
			cur.execute('''SELECT name FROM part_attributes WHERE part=? INTERSECT 
			SELECT name FROM part_attributes WHERE project=?''', params)
			for row in cur.fetchall():
				db_attribs.append(row[0])
			for a in self.attributes.items():
				if a[1] != "":
					if a[0] in db_attribs:
						old_attribs.append((a[1], self.name, self.project, a[0]))
					else:
						new_attribs.append((self.name, self.project, a[0], a[1]))
			
			cur.executemany('INSERT OR REPLACE INTO part_attributes VALUES (NULL,?,?,?,?)', new_attribs)
			cur.executemany('UPDATE part_attributes SET value=? WHERE part=? AND project=? AND name=?', old_attribs)
		
		finally:
			cur.close()
			if connection is None:
				con.close()
