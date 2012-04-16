import csv
import shutil
import os
import urlparse
from operator import itemgetter
import sqlite3
from manager import Workspace
from part import Part
from product import Product

			
class BOM:
	'''For determining the name of a project's Part table.'''
	
	@staticmethod
	def read_from_db(name, wspace):
		''' Return any BOM object from a DB based on its table name. '''
		boms = []
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (name,)
			cur.execute('SELECT * FROM projects WHERE name=?', symbol)
			for row in cur.fetchall():
				bom = BOM(row[0], row[1], row[2])
				boms.append(bom)
			
		finally:
			cur.close()
			con.close()
			return boms
	
	@staticmethod
	def new_project(name, desc, infile, wspace):
		''' Create a new BOM object and its part table.
		Add the BOM to the Workspace's projects table.
		Returns the created BOM object. '''
		new = BOM(name, desc, infile)
		new.create_table(wspace)
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (name, desc, infile,)
			cur.execute('INSERT INTO projects VALUES (?,?,?)', symbol)
			
		finally:
			cur.close()
			con.close()
			return new
	
	def __init__(self, name, desc, input_file="bom.csv"):
		self.name = name	# Table name
		self.description = desc # Longer description string
		self.input = input_file
		self.parts = [] # List of 3-element lists of part name, value, and product.name
		# This is used for sorting in the BOM table in the GUI
		self.val_counts = {}
		self.prod_counts = {}
	
	def create_table(self, wspace):
		''' Create the Parts table for a project in the given Workspace. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'CREATE TABLE IF NOT EXISTS %s (name TEXT PRIMARY KEY, value TEXT, device TEXT, package TEXT, description TEXT, product TEXT REFERENCES products(manufacturer_pn) )' % self.name
			cur.execute(sql)
		
		finally:
			cur.close()
			con.close()
		
	def delete(self, wspace):
		''' Delete the BOM table for a project from the given Workspace. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'DROP TABLE %s' % self.name
			symbol = (self.name,)
			cur.execute(sql)
			cur.execute('DELETE FROM projects WHERE name=?', symbol)
			
		finally:
			cur.close()
			con.close()
	
	def rename(self, new_name, wspace):
		''' Rename the project. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.name, new_name,)
			cur.execute('RENAME ? TO ?', symbol)
			symbol = (new_name, self.name,)
			cur.execute('UPDATE projects SET name=? WHERE name=?', symbol)
			
		finally:
			cur.close()
			con.close()
	
	def sort_by_name(self):
		self.parts.sort(key=itemgetter(0))
		
	def sort_by_val(self):
		self.parts.sort(key=itemgetter(1))
		
	def sort_by_prod(self):
		self.parts.sort(key=itemgetter(2))
	
	def set_val_counts(self, wspace):
		print "BOM.set_val_counts"
		self.val_counts.clear()
		vals = set()
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT DISTINCT value FROM %s' % self.name
			cur.execute(sql)
			for row in cur.fetchall():
				vals.add(row[0])
			for v in vals:
				sql = 'SELECT name FROM %s WHERE value=?' % self.name
				symbol = (v,)
				cur.execute(sql, symbol)
				self.val_counts[v] = len(cur.fetchall())
			
		finally:
			cur.close()
			con.close()

	def set_prod_counts(self, wspace):
		print "BOM.set_prod_counts"
		self.prod_counts.clear()
		
		prods = set()
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT DISTINCT product FROM %s' % self.name
			cur.execute(sql)
			for row in cur.fetchall():
				prods.add(row[0])
			for p in prods:
				sql = 'SELECT name FROM %s WHERE product=?' % self.name
				symbol = (p,)
				cur.execute(sql, symbol)
				self.prod_counts[p] = len(cur.fetchall())
			
		finally:
			cur.close()
			con.close()
	
	def get_cost(self, wspace, run_size=1):
		''' Get the total project BOM cost and unit price for a given production run size.
		Returns a pair (unit_price, total_cost).'''
		self.set_prod_counts(wspace)
		project_prod_counts = self.prod_counts.copy()
		unit_price = 0
		total_cost = 0
		for x in project_prod_counts.keys():
			project_prod_counts[x] = self.prod_counts[x] * run_size
			
		for x in project_prod_counts.items():
			# Find x[0] (the dict key) in the product DB
			# x is [manufacturer_pn, qty]
			if x[0] == 'NULL':
				# TODO : Print a warning on screen?
				print "Warning: BOM.get_cost() skipped a part with no product"
			else:
				prod = Product.select_by_pn(x[0], wspace)[0]
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
				p[2] = part.product
		# TODO : If inline addition of parts is added later (as in, not from a
		# CSV file), a check needs to be added here to make sure part is in self.parts
	
	def read_parts_list_from_db(self, wspace):
		print "BOM.read_parts_list_from_db"
		new_parts = []	# List of 3-element lists of part name, value, and product
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT name, value, product FROM %s' % self.name
			cur.execute(sql)
			for row in cur.fetchall():
				new_parts.append([row[0], row[1], row[2]])
			
		finally:
			cur.close()
			con.close()
			#print 'read_parts_list_from_db: new_parts = ', new_parts
			return new_parts
		
	def read_from_file(self, wspace):
		print "BOM.read_from_file"
		# Clear self.parts
		del self.parts[:]
		with open(self.input, 'rb') as f:
			reader = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			for row in reader:
				print row
				# Check for optional product column
				if len(row) > 5:
					part = Part(row[0], row[1], row[2], row[3], row[4], row[5])
				else:
					part = Part(row[0], row[1], row[2], row[3], row[4])
				#print "Part: %s %s %s %s" % (part.name, part.value, part.device, part.package)
				# Check if identical part is already in DB with a product
				# If so, preserve the product entry
				if(part.is_in_db(self.name, wspace)):
					print "Part of same name already in DB"
					old_part = Part.select_by_name(part.name, self.name, wspace)[0]
					if(part.value == old_part.value and part.device == old_part.device and part.package == old_part.package):
						if part.product != 'NULL':
							if old_part.product != 'NULL':
								# TODO: prompt? Defaulting to old_part.product for now (aka do nothing)
								print 'Matching CSV and DB parts with non-NULL product mismatch, keeping DB version...'
							elif old_part.product == 'NULL':
								part.update(self.name, wspace)
						elif part.product == 'NULL':
							if old_part.product != 'NULL':
								pass	# Do nothing in this case
							elif old_part.product == 'NULL':
								candidate_products = list(part.find_matching_products(wspace))
								if len(candidate_products) == 0:
									#print 'No matching products found, nothing to do'
									pass
								elif len(candidate_products) == 1:
									part.product = candidate_products[0].manufacturer_pn
									print 'Found exactly one matching product, setting product and updating', part.show()
									part.update(self.name, wspace)
								else:
									print 'Found multiple product matches, prompting for selection...'
									# TODO: Currently going with first result, need to prompt for selection
									part.product = candidate_products[0].manufacturer_pn
									part.update(self.name, wspace)
								
					else:	# Value/device/package mismatch
						if part.product != 'NULL':
							part.update(self.name, wspace)
						elif part.product == 'NULL':
							candidate_products = list(part.find_matching_products(wspace))
							if len(candidate_products) == 0:
								print 'No matching products found, updating as-is'
							elif len(candidate_products) == 1:
								part.product = candidate_products[0].manufacturer_pn
								print 'Found exactly one matching product, setting product and updating', part.show()
							else:
								print 'Found multiple product matches, prompting for selection...'
								# TODO: Currently going with first result, need to prompt for selection
								part.product = candidate_products[0].manufacturer_pn
							part.update(self.name, wspace)
				
				else:
					print 'Part not in DB'
					if part.product == 'NULL':
						candidate_products = list(part.find_matching_products(wspace))
						if len(candidate_products) == 0:
							print 'No matching products found, inserting as-is', part.show()
						elif len(candidate_products) == 1:
							part.product = candidate_products[0].manufacturer_pn
							print 'Found exactly one matching product, setting product and inserting', part.show()
						else:
							print 'Found multiple product matches, prompting for selection...'
							# TODO: Currently going with first result, need to prompt for selection
							part.product = candidate_products[0].manufacturer_pn
					
					part.insert(self.name, wspace)
				self.parts.append([part.name, part.value, part.product])
				
		print "Parts list: ", self.parts
	
	def select_parts_by_name(self, name, wspace):
		''' Return the Part(s) of given name. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE name=?' % self.name
			symbol = (name,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
	
	def select_parts_by_value(self, val, wspace):
		''' Return the Part(s) of given value in a list. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE value=?' % self.name
			symbol = (val,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
	
	def select_parts_by_product(self, prod, wspace):
		''' Return the Part(s) of given product in a list. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE product=?' % self.name
			symbol = (prod,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = Part(row[0], row[1], row[2], row[3], row[4], row[5])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
		