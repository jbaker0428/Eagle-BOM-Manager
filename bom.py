import csv
import shutil
import os
import urlparse
from operator import itemgetter
import apsw
from manager import Workspace
from part import Part
from product import Product


class NullProductInProjectException(Exception):
	''' Raised in situations where correct results require all Parts in the project
	to have a non-NULL Product for correct results, but a NULL product is found. '''
	def __init__(self, source, text):
		self.source = source
		self.text = text
	def __str__(self):
		return repr(self.text)
	
class BOM:
	'''For determining the name of a project's Part table.'''
	
	@staticmethod
	def read_from_db(name, connection):
		''' Return any BOM object from a DB based on its table name. '''
		boms = []
		try:
			cur = connection.cursor()
			
			params = (name,)
			for row in cur.execute('SELECT * FROM projects WHERE name=?', params):
				bom = BOM(row[0], row[1], row[2])
				boms.append(bom)
			
		finally:
			cur.close()
			return boms
	
	@staticmethod
	def new_project(name, desc, infile, connection):
		''' Create a new BOM object and its part table.
		Add the BOM to the Workspace's projects table.
		Returns the created BOM object. '''
		new = BOM(name, desc, infile)
		try:
			cur = connection.cursor()
			
			params = (name, desc, infile,)
			cur.execute('INSERT INTO projects VALUES (?,?,?)', params)
			
		finally:
			cur.close()
			return new
	
	def __init__(self, name, desc, input_file="bom.csv"):
		self.name = name	# Table name
		self.description = desc # Longer description string
		self.input = input_file
		self.parts = [] # List of 3-element lists of part name, value, and product.name
		# This is used for sorting in the BOM table in the GUI
		self.val_counts = {}
		self.prod_counts = {}
	
	def delete(self, connection):
		''' Delete the BOM table for a project from the given Workspace. '''
		try:
			cur = connection.cursor()
			
			params = (self.name,)
			cur.execute('DELETE FROM projects WHERE name=?', params)
			
		finally:
			cur.close()
	
	def rename(self, new_name, connection):
		''' Rename the project. '''
		try:
			cur = connection.cursor()
			
			params = (new_name, self.name,)
			cur.execute('UPDATE projects SET name=? WHERE name=?', params)
			
		finally:
			cur.close()
	
	def sort_by_name(self):
		self.parts.sort(key=itemgetter(0))
		
	def sort_by_val(self):
		self.parts.sort(key=itemgetter(1))
		
	def sort_by_prod(self):
		self.parts.sort(key=itemgetter(2))
	
	def set_val_counts(self, connection):
		print "BOM.set_val_counts"
		self.val_counts.clear()
		vals = set()
		try:
			cur = connection.cursor()
			
			params = (self.name,)
			sql = 'SELECT DISTINCT value FROM parts WHERE project=?'
			for row in cur.execute(sql, params):
				vals.add(row[0])
			for v in vals:
				sql = 'SELECT name FROM parts WHERE value=? AND project=?'
				params = (v, self.name,)
				cur.execute(sql, params)
				self.val_counts[v] = len(cur.fetchall())
			
		finally:
			cur.close()

	def set_prod_counts(self, connection):
		print "BOM.set_prod_counts"
		self.prod_counts.clear()
		
		prods = set()
		try:
			cur = connection.cursor()
			
			params = (self.name,)
			sql = 'SELECT DISTINCT product FROM parts WHERE project=?'
			for row in cur.execute(sql, params):
				prods.add(row[0])
			for p in prods:
				sql = 'SELECT name FROM parts WHERE product=? INTERSECT SELECT name FROM parts WHERE project=?'
				params = (p, self.name,)
				cur.execute(sql, params)
				self.prod_counts[p] = len(cur.fetchall())
			
		finally:
			cur.close()
	
	def get_cost(self, connection, run_size=1):
		''' Get the total project BOM cost and unit price for a given production run size.
		Returns a pair (unit_price, total_cost).'''
		self.set_prod_counts(connection)
		project_prod_counts = self.prod_counts.copy()
		unit_price = 0
		total_cost = 0
		if 'NULL' in project_prod_counts.keys():
			raise NullProductInProjectException(self.get_cost.__name__, 'Warning: Cost calculation does not account for parts with no product assigned!')
		for x in project_prod_counts.keys():
			project_prod_counts[x] = self.prod_counts[x] * run_size
			
		for x in project_prod_counts.items():
			# Find x[0] (the dict key) in the product DB
			# x is [manufacturer_pn, qty]
			if x[0] == 'NULL':
				pass
			else:
				prod = Product.select_by_pn(x[0], connection)[0]
				listing = prod.best_listing(project_prod_counts[x[0]])
				price_break = listing.get_price_break(x[1])
				unit_price += (price_break[1] * self.prod_counts[x[0]]) + listing.reel_fee
				total_cost += (price_break[1] * project_prod_counts[x[0]]) + listing.reel_fee
				
		return (unit_price, total_cost)
	
	def update_parts_list(self, part):
		''' Take in a Part, find it in self.parts, update product.name entry'''
		# Find p in self.parts by name
		for p in self.parts:
			if p[0] == part.name:
				if part.product is None:
					p[2] = ''
				else:
					p[2] = part.product.manufacturer_pn
		# TODO : If inline addition of parts is added later (as in, not from a
		# CSV file), a check needs to be added here to make sure part is in self.parts
	
	def read_parts_list_from_db(self, connection):
		print "BOM.read_parts_list_from_db"
		new_parts = []	# List of 3-element lists of part name, value, and product
		try:
			cur = connection.cursor()
			
			sql = 'SELECT name, value, product FROM parts WHERE project=?'
			params = (self.name,)
			for row in cur.execute(sql, params):
				new_parts.append([row[0], row[1], row[2]])
			
		finally:
			cur.close()
			#print 'read_parts_list_from_db: new_parts = ', new_parts
			return new_parts
		
	def read_from_file(self, connection):
		''' Parses a BOM spreadsheet in CSV format and writes it to the DB.
		Passing an open connection to this method is HIGHLY recommended.  '''
		# TODO: product_updater calls are hardcoded to always check wspace
		print "BOM.read_from_file"
		# Clear self.parts
		del self.parts[:]
		with open(self.input, 'rb') as f:
			sniffer = csv.Sniffer()
			sniffed_dialect = sniffer.sniff(f.read(1024))
			f.seek(0)
			has_header = sniffer.has_header(f.read(2048))
			f.seek(0)
			reader = csv.reader(f, dialect=sniffed_dialect)
			if has_header is True:
				rownum = 0
				print 'Header found in CSV'
				
					
				for row in reader:
					if rownum == 0:
						header = row
						# Process column names from header
						index = 0
						name_col = -1
						val_col = -1
						dev_col = -1
						pkg_col = -1
						desc_col = -1
						prod_col = -1
						bom_attribs = {}	# Key = column index, value = name of attribute
						for column in header:
							col = column.lower()
							if 'part' in col or 'name' in col:
								name_col = index
							elif 'value' in col:
								val_col = index
							elif 'device' in col:
								dev_col = index
							elif 'package' in col:
								pkg_col = index
							elif 'description' in col:
								desc_col = index
							elif 'partno' in col or 'partnum' in col or 'part number' in col or 'part#' in col or ('pn' in col and 'vendor' not in col):
								prod_col = index
							else:
								bom_attribs[index] = column
							index += 1
					else:
						print 'Row: ', row
						#row_attribs = {}
						row_attribs = dict({})
						row_attribs.clear()
						for attrib in bom_attribs.items():
							if len(row[attrib[0]]) > 0:
								row_attribs[attrib[1]] = row[attrib[0]]
						#print 'Row attribs: ', row_attribs
						if prod_col == -1:
							part = Part(row[name_col], self, row[val_col], row[dev_col], row[pkg_col], row[desc_col], None, row_attribs)
						else:
							prod = Product.select_by_pn(row[prod_col], connection)
							if prod is not None and len(prod) > 0:
								part = Part(row[name_col], self, row[val_col], row[dev_col], row[pkg_col], row[desc_col], prod[0], row_attribs)
							else:
								part = Part(row[name_col], self, row[val_col], row[dev_col], row[pkg_col], row[desc_col], None, row_attribs)
						
						part.product_updater(connection)
						if part.product is None:
							self.parts.append([part.name, part.value, ''])
						else:
							self.parts.append([part.name, part.value, part.product.manufacturer_pn])
					rownum += 1
					
			else:	# No column headers
				for row in reader:
					print row
					# Check for optional product column
					if len(row) == 6:
						if len(row[5]) > 0:
							prod = Product.select_by_pn(row[5], connection)
							if prod is not None and len(prod) > 0:
								part = Part(row[0], self, row[1], row[2], row[3], row[4], prod[0])
							else:
								new_prod = Product('NULL', row[5])
								new_prod.insert(connection)
								new_prod.scrape(connection)
								part = Part(row[0], self, row[1], row[2], row[3], row[4], new_prod)
						else:
							part = Part(row[0], self, row[1], row[2], row[3], row[4], None)
					else:
						part = Part(row[0], self, row[1], row[2], row[3], row[4], None)
					#print 'Got part from CSV: '
					#part.show() 
					part.product_updater(connection)
					if part.product is None:
						self.parts.append([part.name, part.value, ''])
					else:
						self.parts.append([part.name, part.value, part.product.manufacturer_pn])
				
		#print "Parts list: ", self.parts
	
	def select_parts_by_name(self, name, connection):
		''' Return the Part(s) of given name. '''
		parts = []
		try:
			cur = connection.cursor()
			
			#sql = 'SELECT * FROM parts WHERE name=? INTERSECT SELECT * FROM parts WHERE project=?'
			sql = 'SELECT * FROM parts WHERE name=? AND project=?'
			params = (name, self.name)
			for row in cur.execute(sql, params):
				parts.append(Part.new_from_row(row, connection, self))
			
		finally:
			cur.close()
			return parts
	
	def select_parts_by_value(self, val, connection):
		''' Return the Part(s) of given value in a list. '''
		parts = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT * FROM parts WHERE value=? INTERSECT SELECT * FROM parts WHERE project=?'
			params = (val, self.name)
			for row in cur.execute(sql, params):
				parts.append(Part.new_from_row(row, connection, self))
			
		finally:
			cur.close()
			return parts
	
	def select_parts_by_product(self, prod, connection):
		''' Return the Part(s) of given product in a list. '''
		parts = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT * FROM parts WHERE product=? INTERSECT SELECT * FROM parts WHERE project=?'
			params = (prod, self.name)
			for row in cur.execute(sql, params):
				parts.append(Part.new_from_row(row, connection, self))
			
		finally:
			cur.close()
			return parts
		