import types

import apsw

from manager import Workspace
from product import Product

class Part(object):
	
	"""A component in the BOM exported from Eagle."""
	
	@staticmethod
	def new_from_row(row, connection, known_project=None):
		"""Given a parts table row from the DB, returns a Part object."""
		
		from bom import BOM
		#print 'new_from_row: row param: ', row
		if row[6] is None or row[6] == 'NULL' or row[6] == '':
			product = None
			#print 'new_from_row: setting no product'
		else:
			product = Product.select_by_pn(row[6], connection)[0]
			#print 'new_from_row: product results: ', product
		if row[1] is None or row[1] == 'NULL':
			project = None # TODO: Raise an exception here? This is a PK  violation
			print 'row[1] is None/NULL!'
		else:
			if known_project is None:
				projects = BOM.read_from_db(row[1], connection)
				if len(projects) > 0:
					project = projects[0]
			else:
				project = known_project
		part = Part(row[0], project, row[2], row[3], row[4], row[5], product)
		part.fetch_specs(connection)
		return part
	
	@staticmethod
	def select_all(connection):
		"""Returns the entire parts table as Parts instances."""
		
		#print 'Entered Part.select_all'
		parts = []
		try:
			cur = connection.cursor()
			for row in cur.execute('SELECT * FROM parts'):
				part = Part.new_from_row(row, connection)
				#print 'Appending part: ', part.show()
				parts.append(part)
		
		finally:
			cur.close()
			return parts
	
	@staticmethod
	def select_by_name(name, connection, project=None):
		"""Return the Part(s) of given name."""
		
		parts = []
		try:
			cur = connection.cursor()
			
			if project is None:
				sql = "SELECT * FROM parts WHERE name=?"
				params = (name,)
			else:
				sql = "SELECT * FROM parts WHERE name=? AND project=?"
				params = (name, project.name,)
			for row in cur.execute(sql, params):
				parts.append(Part.new_from_row(row, connection))
			
		finally:
			cur.close()
			return parts
	
	@staticmethod
	def select_by_value(val, connection, project=None):
		"""Return the Part(s) of given value in a list."""
		
		parts = []
		try:
			cur = connection.cursor()
			
			if project is None:
				sql = "SELECT * FROM parts WHERE value=?"
				params = (val,)
			else:
				sql = "SELECT * FROM parts WHERE value=? AND project=?"
				params = (val, project.name,)
			for row in cur.execute(sql, params):
				parts.append(Part.new_from_row(row, connection))
			
		finally:
			cur.close()
			return parts
		
	@staticmethod
	def select_by_product(prod, connection, project=None):
		"""Return the Part(s) of given product in a list."""
		
		parts = []
		try:
			cur = connection.cursor()
			
			if project is None:
				sql = "SELECT * FROM parts WHERE product=?"
				params = (prod,)
			else:
				sql = "SELECT * FROM parts WHERE product=? AND project=?"
				params = (prod, project.name,)
			for row in cur.execute(sql, params):
				parts.append(Part.new_from_row(row, connection))
			
		finally:
			cur.close()
			return parts
	
	def __init__(self, name, project, value, device, package, description=None, product=None, specs=None):
		self.name = name
		self.project = project	# A BOM object
		self.value = value
		self.device = device
		self.package = package
		self.description = description
		self.product = product	# A Product object
		if specs is None:
			self.specs = dict()
		else:
			self.specs = specs

	def __str__(self):
		if self.product is None:
			return '%s.%s (%s, %s, %s): No product, Attribs: %s' % (self.project.name, self.name, self.value, self.device, self.package, self.specs)
		else:
			return '%s.%s (%s, %s, %s): PN: %s, Attribs: %s' % (self.project.name, self.name, self.value, self.device, self.package, self.product.manufacturer_pn, self.specs)

	def show(self):
		"""A simple print method."""
		
		print '============================'
		print 'Name: ', self.name, type(self.name)
		print 'Project name: ', self.project.name, type(self.project)
		print 'Value: ', self.value, type(self.value)
		print 'Device: ', self.device, type(self.device)
		print 'Package: ', self.package, type(self.package)
		print 'Description: ', self.description, type(self.description)
		if self.product is not None:
			print 'Product PN: ', self.product.manufacturer_pn, type(self.product.manufacturer_pn)
		print 'Specs: '
		for spec in self.specs.items():
			print spec[0], ': ', spec[1]
		print '============================'
		
	def equals(self, p, check_foreign_specs=True, same_name=True, same_project=True, same_product=True):
		"""Compares the Part to another Part.
		
		The check_foreign_specs argument (default True) controls whether or not
		p.specs.keys() is checked for members not in self.specs.keys().
		The reverse is always checked.
		"""
		if type(p) != type(self):
			return False
		eq = True
		if same_name is True and self.name != p.name:
			eq = False
		elif same_project is True and self.project.name != p.project.name:
			eq = False
		elif self.value != p.value:
			eq = False
		elif self.device != p.device:
			eq = False
		elif self.package != p.package:
			eq = False
		elif self.description != p.description:
			eq = False
		elif same_product is True:
			if self.product is None or p.product is None:
				if self.product is not p.product:
					eq = False
			elif self.product.manufacturer_pn != p.product.manufacturer_pn:
				eq = False
		if self.specs is not None:
			for k in self.specs.keys():
				if self.specs[k] != "":
					if k not in p.specs.keys():
						eq = False
					elif self.specs[k] != p.specs[k]:
						eq = False
					
		if check_foreign_specs is True:
			if p.specs is None and self.specs is not None:
				eq = False
			else:
				for k in p.specs.keys():
					if p.specs[k] != "":
						if k not in self.specs.keys():
							eq = False
						elif p.specs[k] != self.specs[k]:
							eq = False
		return eq
		
	def __eq__(self, p):
		"""Calls self.equals with all strict comparison options enabled."""
		
		return self.equals(p)

	def findInFile(self, bom_file):
		"""Check if a BOM self of this name is in the given CSV BOM."""
		
		with open(bom_file, 'rb') as f:
			db = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			rownum = 0
			for row in db:
				if row[0] == self.name:
					return rownum
				rownum = rownum + 1
			return -1
	
	def part_query_constructor(self, wspace_scope):
		"""Helper method to construct the SQL queries for find_similar_parts.
		
		If wspace_scope == False, queries within the project scope.
		If wspace_scope == True, queries other projects in the workspace. 
		Returns a pair: The query string and the parameters tuple.
		"""
		
		# TODO: These helper functions have extraneous arguments
		# self.name is always ?1, self.project.name is always ?2
		def project_spec_expr(attrib_name, attrib_value, name_param_number, value_param_number):
			"""Generates an SQL expression to match a single attribute for the project query."""
			
			name_expr = '?%s IN (SELECT name FROM part_specs WHERE part!=?1 AND project=?2)' % name_param_number
			value_expr = '?%s IN (SELECT value FROM part_specs WHERE part!=?1 AND project=?2 AND name=?%s)' % (value_param_number, name_param_number)
			return '(' + name_expr + ' AND ' + value_expr + ')'
		
		def workspace_spec_expr(attrib_name, attrib_value, name_param_number, value_param_number):
			"""Generates an SQL expression to match a single attribute for the workspace query."""
			
			name_expr = '?%s IN (SELECT name FROM part_specs WHERE project!=?2)' % name_param_number
			value_expr = '?%s IN (SELECT value FROM part_specs WHERE project=!?2 AND name=?%s)' % (value_param_number, name_param_number)
			return '(' + name_expr + ' AND ' + value_expr + ')'
		
		params_dict = {1 : self.name, 2 : self.project.name, 3 : self.value, 4 : self.device, 5 : self.package}
		if len(self.specs.keys()) > 0:
			spec_exprs = []
			for spec in self.specs.items():
				greatest_param = max(params_dict.keys())
				name_key = greatest_param + 1
				val_key = greatest_param + 2
				params_dict[name_key] = spec[0]
				params_dict[val_key] = spec[1]
				if wspace_scope == True:
					spec_exprs.append(workspace_spec_expr(spec[0], spec[1], name_key, val_key))
				else:
					spec_exprs.append(project_spec_expr(spec[0], spec[1], name_key, val_key))
			
			full_specs_expr = ' AND ' + ' AND '.join(spec_exprs)
		else:
			full_specs_expr = ''
			
		if wspace_scope == True:
			if len(full_specs_expr) > 0:
				specs_clause = 'SELECT DISTINCT part FROM part_specs WHERE project!=?2' + full_specs_expr
				query = 'SELECT * FROM parts WHERE value=?3 AND device=?4 AND package=?5 AND project!=?2 AND name IN (%s)' % specs_clause
			else:
				query = 'SELECT * FROM parts WHERE value=?3 AND device=?4 AND package=?5 AND project!=?2'
		else:
			if len(full_specs_expr) > 0:
				specs_clause = 'SELECT DISTINCT part FROM part_specs WHERE part!=?1 AND project=?2' + full_specs_expr
				query = 'SELECT * FROM parts WHERE value=?3 AND device=?4 AND package=?5 AND project=?2 AND name IN (%s)' % specs_clause
			else:
				query = 'SELECT * FROM parts WHERE value=?3 AND device=?4 AND package=?5 AND project=?2'
		
		# Make the params tuple to pass to the cursor 
		params = []
		for key in sorted(params_dict.keys()):
			params.append(params_dict[key])
		
		return query, tuple(params)
	
	def find_similar_parts(self, connection, check_wspace=True):
		"""Search the project and optionally workspace for parts of matching value/device/package/specs.
		
		If check_wspace = True, returns a pair of lists: (project_results, workspace_results).
		If check_wspace = False, only returns the project_results list. 
		This allows for parts in different projects that incidentally have the same name to be added.
		Only returns parts that have all of the non-empty specs in self.specs
		(with equal values). This behavior is equivalent to self.equals(some_part, False).
		"""
		project_results = []
		workspace_results = []
		try:
			cur = connection.cursor()
			
			project_query, project_params = self.part_query_constructor(False)
			for row in cur.execute(project_query, project_params):
				part = Part.new_from_row(row, connection)
				project_results.append(part)
					
			if check_wspace:
				workspace_query, workspace_params = self.part_query_constructor(True)
				for row in cur.execute(workspace_query, workspace_params):
					part = Part.new_from_row(row, connection)
					workspace_results.append(part)
							
		finally:
			cur.close()
			return (project_results, workspace_results)
	
	def find_matching_products(self, proj_parts, wspace_parts, connection):
		"""Given the output of self.find_similar_parts,	returns a list of Product objects."""
		
		# TODO : Find more results by searching the product_attributes table
		products = set()
		part_nums = set()
		for part in proj_parts:
			if part.product is not None:
				db_prods = Product.select_by_pn(part.product.manufacturer_pn, connection)
				for prod in db_prods:
					if prod.manufacturer_pn not in part_nums:
						part_nums.add(prod.manufacturer_pn)
						products.add(prod)
		
		for part in wspace_parts:
			if part.product is not None:
				db_prods = Product.select_by_pn(part.product.manufacturer_pn, connection)
				for prod in db_prods:
					if prod.manufacturer_pn not in part_nums:
						part_nums.add(prod.manufacturer_pn)
						products.add(prod)
	
		return list(products)
	
	def is_in_db(self, connection):
		"""Check if a BOM self of this name is in the project's database."""
		
		result = Part.select_by_name(self.name, connection, self.project)
		if len(result) == 0:
			return False
		else:
			return True
	
	def product_updater(self, connection, check_wspace=True):
		"""Checks if the Part is already in the DB.
		
		Inserts/updates self into DB depending on:
			- The presence of a matching Part in the DB.
			- The value of self.product.manufacturer_pn.
			- The product of the matching Part in the DB.
		"""
		unset_pn = ('', 'NULL', 'none', None, [])
		if(self.is_in_db(connection)):
			#print "Part of same name already in DB"
			old_part = Part.select_by_name(self.name, connection, self.project)[0]
			if self.equals(old_part, True, True, True, False):
				if self.product is not None and self.product.manufacturer_pn not in unset_pn:
					if old_part.product is not None and old_part.product.manufacturer_pn not in unset_pn:
						# TODO: prompt? Defaulting to old_part.product for now (aka do nothing)
						#print 'Matching CSV and DB parts with non-NULL product mismatch, keeping DB version...'
						pass
					elif old_part.product is None or old_part.product.manufacturer_pn in unset_pn:
						self.update(connection)
				elif self.product is None or self.product.manufacturer_pn in unset_pn:
					if old_part.product is not None and old_part.product.manufacturer_pn not in unset_pn:
						pass	# Do nothing in this case
					elif old_part.product is None or old_part.product.manufacturer_pn in unset_pn:
						(candidate_proj_parts, candidate_wspace_parts) = self.find_similar_parts(connection, check_wspace)
						#print 'first find_similar_parts call'
						candidate_products = self.find_matching_products(candidate_proj_parts, candidate_wspace_parts, connection)
						if len(candidate_products) == 0:
							#print 'No matching products found, nothing to do'
							pass
						elif len(candidate_products) == 1:
							self.product = candidate_products[0]
							#print 'Found exactly one matching product, setting product and updating', #self.show()
							self.update(connection)
						else:
							#print 'Found multiple product matches, prompting for selection...'
							# TODO: Currently going with first result, need to prompt for selection
							self.product = candidate_products[0]
							self.update(connection)
						
			else:	# Value/device/package/attribs mismatch
				if self.product is not None and self.product.manufacturer_pn not in unset_pn:
					self.update(connection)
				elif self.product is None or self.product.manufacturer_pn in unset_pn:
					(candidate_proj_parts, candidate_wspace_parts) = self.find_similar_parts(connection, check_wspace)
					#print 'second find_similar_parts call'
					candidate_products = self.find_matching_products(candidate_proj_parts, candidate_wspace_parts, connection)
					if len(candidate_products) == 0:
						#print 'No matching products found, updating as-is'
						pass
					elif len(candidate_products) == 1:
						self.product = candidate_products[0]
						#print 'Found exactly one matching product, setting product and updating'#, self.show()
					else:
						#print 'Found multiple product matches, prompting for selection...'
						# TODO: Currently going with first result, need to prompt for selection
						self.product = candidate_products[0]
					self.update(connection)
		
		else:
			#print 'Part not in DB'
			if self.product is None or self.product.manufacturer_pn in unset_pn:
				(candidate_proj_parts, candidate_wspace_parts) = self.find_similar_parts(connection, check_wspace)
				#print 'third find_similar_parts call'
				candidate_products = self.find_matching_products(candidate_proj_parts, candidate_wspace_parts, connection)
				if len(candidate_products) == 0:
					#print 'No matching products found, inserting as-is'#, self.show()
					pass
				elif len(candidate_products) == 1:
					self.product = candidate_products[0]
					#print 'Found exactly one matching product, setting product and inserting'#, self.show()
				else:
					#print 'Found multiple product matches, prompting for selection...'
					# TODO: Currently going with first result, need to prompt for selection
					self.product = candidate_products[0]
			else:
				if self.product.is_in_db(connection) == False:
					newprod = Product('NULL', self.product.manufacturer_pn)
					newprod.insert(connection)
					newprod.scrape(connection)
			self.insert(connection)
		
	def update(self, connection):
		"""Update an existing Part record in the DB."""
		
		try:
			cur = connection.cursor()
			
			if self.product is None:
				pn = None
			else:
				pn = self.product.manufacturer_pn
			
			sql = 'UPDATE parts SET name=?, project=?, value=?, device=?, package=?, description=?, product=? WHERE name=? AND project=?'
			params = (self.name, self.project.name, self.value, self.device, self.package,  
					self.description, pn, self.name, self.project.name,)
			cur.execute(sql, params)
			self.write_specs(connection)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		"""Write the Part to the DB."""
		
		try:
			cur = connection.cursor()
			
			if self.product is None:
				pn = None
			else:
				pn = self.product.manufacturer_pn
			
			sql = 'INSERT OR REPLACE INTO parts VALUES (?,?,?,?,?,?,?)'
			params = (self.name, self.project.name, self.value, self.device, self.package,  
					self.description, pn,)
			cur.execute(sql, params)
			self.write_specs(connection)
			
		finally:
			cur.close()
	
	def delete(self, connection):
		"""Delete the Part from the DB.
		 
		Part specs are deleted via foreign key constraint cascading.
		"""
		
		try:
			cur = connection.cursor()
			
			sql = 'DELETE FROM parts WHERE name=? AND project=?'
			params = (self.name, self.project.name)
			cur.execute(sql, params)
			
		finally:
			cur.close()
	
	def fetch_specs(self, connection):
		"""Fetch specs dictionary for this Part.
		
		Clears and sets the self.specs dictionary directly.
		"""
		
		self.specs.clear()
		try:
			cur = connection.cursor()
			
			params = (self.name, self.project.name,)
			for row in cur.execute('SELECT name, value FROM part_specs WHERE part=? AND project=?', params):
				self.specs[row[0]] = row[1]
			
		finally:
			cur.close()
	
	def has_spec(self, spec, connection):
		"""Check if this Part has an spec of given name in the DB.
		
		Ignores value of the spec.
		"""
		
		results = []
		try:
			cur = connection.cursor()
			sql = 'SELECT name FROM part_specs WHERE part=? AND project=? AND name=?'
			params = (self.name, self.project.name, spec,)
			for row in cur.execute(sql, params):
				results.append(row[0])
			
		finally:
			cur.close()
			if len(results) == 0:
				return False
			else:
				return True
	
	def add_spec(self, name, value, connection):
		"""Add a single spec to this Part.
		
		Adds the new spec to the self.specs dictionary in memory.
		Writes the new spec to the DB immediately.
		"""
		
		try:
			cur = connection.cursor()
			
			self.specs[name] = value
			params = (self.name, self.project.name, name, value,)
			cur.execute('INSERT OR REPLACE INTO part_specs VALUES (NULL,?,?,?,?)', params)

		finally:
			cur.close()
				
	def remove_spec(self, name, connection):
		"""Removes a single spec from this Part.
		
		Deletes the spec from the self.specs dictionary in memory.
		Deletes the spec from the DB immediately.
		"""
		
		try:
			cur = connection.cursor()
			
			if name in self.specs:
				del self.specs[name]
			params = (self.name, self.project.name, name,)
			cur.execute('DELETE FROM part_specs WHERE part=? AND project=? AND name=?', params)

		finally:
			cur.close()

	def write_specs(self, connection):
		"""Write all of this Part's specs to the DB.
		
		Checks specs currently in DB and updates/inserts/deletes as appropriate.
		"""
		
		db_specs = []
		update_specs = []
		insert_specs = []
		delete_specs = []
		try:
			cur = connection.cursor()
			
			params = (self.name, self.project.name,)
			for row in cur.execute('SELECT name FROM part_specs WHERE part=? AND project=?', params):
				db_specs.append(row[0])
			
			update_keys = db_specs & self.specs.keys()
			insert_keys = self.specs.keys() - db_specs
			delete_keys = db_specs - self.specs.keys()
			
			for k, v in self.specs.items():
				if v != "":
					if k in update_keys:
						update_specs.append((self.name, self.project.name, k, v,))
					elif k in insert_keys:
						insert_specs.append((self.name, self.project.name, k, v,))
					elif k in delete_keys:
						delete_specs.append((self.name, self.project.name, k,))
			cur.executemany('UPDATE part_specs SET value=? WHERE part=? AND project=? AND name=?', update_specs)
			cur.executemany('INSERT INTO part_specs VALUES (NULL,?,?,?,?)', insert_specs)
			cur.executemany('DELETE FROM part_specs WHERE part=? AND project=? AND name=?', delete_specs)
		
		finally:
			cur.close()
