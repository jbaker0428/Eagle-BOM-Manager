import csv
import shutil
import os
import urlparse
from operator import itemgetter
import sqlite3
from urbm import Workspace
from urbm_bompart import bomPart
from urbm_product import Product

			
class BOM:
	'''For determining the name of a project's bomPart table.'''
	
	@staticmethod
	def readFromDB(name, wspace):
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
	def newProject(name, desc, infile, wspace):
		''' Create a new BOM object and its part table.
		Add the BOM to the Workspace's projects table.
		Returns the created BOM object. '''
		new = BOM(name, desc, infile)
		new.createTable(wspace)
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (name, desc, infile,)
			cur.execute('INSERT INTO projects VALUES (?,?,?)', symbol)
			
		finally:
			cur.close()
			con.close()
			return new
	
	def __init__(self, name, desc, inputFile="bom.csv"):
		self.name = name	# Table name
		self.description = desc # Longer description string
		self.input = inputFile
		self.parts = [] # List of 3-element lists of part name, value, and product.name
		# This is used for sorting in the BOM table in the GUI
		self.valCounts = {}
		self.prodCounts = {}
	
	def createTable(self, wspace):
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
	
	def sortByName(self):
		self.parts.sort(key=itemgetter(0))
		
	def sortByVal(self):
		self.parts.sort(key=itemgetter(1))
		
	def sortByProd(self):
		self.parts.sort(key=itemgetter(2))
	
	def setValCounts(self, wspace):
		print "BOM.setValCounts"
		self.valCounts.clear()
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
				self.valCounts[v] = len(cursor.fetchall())
			
		finally:
			cur.close()
			con.close()

	def setProdCounts(self, wspace):
		print "BOM.setProdCounts"
		self.prodCounts.clear()
		
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
				self.prodCounts[p] = len(cursor.fetchall())
			
		finally:
			cur.close()
			con.close()
	
	def getCost(self, wspace, runSize=1):
		''' Get the total project BOM cost for a given production run size. '''
		self.setProdCounts()
		projProdCounts = self.prodCounts.copy()
		cost = 0
		for x in projProdCounts.keys():
			projProdCounts[x] = self.prodCounts[x] * runSize
			
		for x in projProdCounts.items():
			# Find x[0] (the dict key) in the product DB
			if x[0] is 'NULL':
				# TODO : Print a warning on screen?
				print "Warning: BOM.getCost() skipped a part with no product"
			else:
				prod = Product.select_by_pn(x[0], wspace)[0]
				prod.fetchListings(wspace)
				listing = product.bestListing(projProdCounts[x[0]])
				priceBreak = listing.getPriceBreak(x[1])
				cost += (priceBreak[1] * projProdCounts[x[0]]) + listing.reelFee
				
		return cost
	
	def updateParts(self, part):
		''' Take in a bomPart, find it in self.parts, update product.name entry'''
		# Find p in self.parts by name
		for p in self.parts:
			if p[0] == part.name:
				p[2] = part.product
		# TODO : If inline addition of parts is added later (as in, not from a
		# CSV file), a check needs to be added here to make sure part is in self.parts
	
	# TODO: Should the read/write methods write the actual BOM object?		
		
	def readPartsListFromDB(self, wspace):
		print "BOM.readPartsListFromDB"
		newParts = []	# List of 3-element lists of part name, value, and product
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT name, value, product FROM %s' % self.name
			cur.execute(sql)
			for row in cur.fetchall():
				newParts.append([row[0], row[1], row[2]])
			
		finally:
			cur.close()
			con.close()
			print 'readPartsListFromDB: newParts = ', newParts
			return newParts
		
	def readFromFile(self, wspace):
		print "BOM.readFromFile"
		# Clear self.parts
		del self.parts[:]
		with open(self.input, 'rb') as f:
			reader = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			for row in reader:
				print row
				# Check for optional product column
				if len(row) > 5:
					part = bomPart(row[0], row[1], row[2], row[3], row[4], row[5])
				else:
					part = bomPart(row[0], row[1], row[2], row[3], row[4])
				#print "Part: %s %s %s %s" % (part.name, part.value, part.device, part.package)
				# Check if identical part is already in DB with a product
				# If so, preserve the product entry
				if(part.isInDB(self.name, wspace)):
					print "Part already in DB"
					oldPart = bomPart.select_by_name(part.name, self.name, wspace)[0]
					print "oldPart: ", oldPart.name, oldPart.value, oldPart.package, oldPart.product
					if(part.value == oldPart.value and part.device == oldPart.device and part.package == oldPart.package):
						if oldPart.product != 'none':
							print "Part found in DB with existing product ", oldPart.product
							part.product = oldPart.product
						else:
							print "Part found in DB without product entry, overwriting..."
							part.update(self.name, wspace)
				else:
					print "Part not in DB, inserting as", part.show()
					part.insert(self.name, wspace)
				self.parts.append([part.name, part.value, part.product])
				
		print "Parts list: ", self.parts
	
	def select_parts_by_name(self, name, wspace):
		''' Return the bomPart(s) of given name. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE name=?' % self.name
			symbol = (name,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = bomPart(row[0], row[1], row[2], row[3], row[4], row[5])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
	
	def select_parts_by_value(self, val, wspace):
		''' Return the bomPart(s) of given value in a list. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE value=?' % self.name
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
	def select_parts_by_product(self, prod, wspace):
		''' Return the bomPart(s) of given product in a list. '''
		parts = []
		try:
			(con, cur) = wspace.con_cursor()
			
			sql = 'SELECT * FROM %s WHERE product=?' % self.name
			symbol = (prod,)
			cur.execute(sql, symbol)
			for row in cur.fetchall():
				part = bomPart(row[0], row[1], row[2], row[3], row[4], row[5])
				parts.append(part)
			
		finally:
			cur.close()
			con.close()
			return parts
		