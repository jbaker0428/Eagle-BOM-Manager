import csv
import shutil
import os
import urlparse
from urbm_bompart import bomPart
from urbm_product import Product
import y_serial_v060 as y_serial
from operator import itemgetter
import sqlite3
from urbm import Workspace

'''For determining the name of a project's bomPart table.'''			
class BOM:
	@staticmethod
	def readFromDB(database, name):
		''' Return any BOM object from a DB based on its table name. '''
		bom = database.select('bom', name)
		return bom
	
	@staticmethod
	def newProject(name, desc, infile, wspace):
		''' Create a new BOM object and its part table.
		Add the BOM to the Workspace's projects table.
		Returns the created BOM object. '''
		new = BOM(name, desc, infile)
		new.createTable(wspace)
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (name,)
			cur.execute('INSERT INTO projects VALUES (?)', symbol)
			
		except:
			print 'BOM.newProject exception.'
			
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
			
			symbol = (self.name,)
			cur.execute('''CREATE TABLE IF NOT EXISTS ?
			(name TEXT PRIMARY KEY, 
			value TEXT, 
			device TEXT, 
			package TEXT, 
			description TEXT, 
			product TEXT REFERENCES products(manufacturer_pn))''', symbol)
			
		except:
			print 'BOM(%s).createTable exception, probably because table already created.' % self.name
			
		finally:
			cur.close()
			con.close()
		
	def delete(self):
		self.db.droptable(self.name)
	
	def sortByName(self):
		self.parts.sort(key=itemgetter(0))
		
	def sortByVal(self):
		self.parts.sort(key=itemgetter(1))
		
	def sortByProd(self):
		self.parts.sort(key=itemgetter(2))
	
	def setValCounts(self):
		print "BOM.setValCounts"
		self.valCounts.clear()
		vals = set()
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.name,)
			cur.execute('SELECT DISTINCT value FROM ?', symbol)
			for row in cur.fetchall():
				vals.add(row[0])
			for v in vals:
				symbol = (self.name, v,)
				cur.execute('SELECT name FROM ? WHERE value=?', symbol)
				self.valCounts[v] = len(cursor.fetchall())

		except:
			print 'Exception in BOM(%s).setValCounts()' % self.name
			
		finally:
			cur.close()
			con.close()		

	def setProdCounts(self):
		# TODO: see new plan below, replacing "value" with product...
		''' 
		Select value column for all parts in project
		Make a list of the values
		For each item in the values list, select name column from 
		parts in project where value = vallist[iter]
		Record len(cursor.fetchall()
		valCounts[val list iter] = len(cursor.fetchall())
		'''
		print "BOM.setProdCounts"
		self.prodCounts.clear()
		print "BOM.parts: ", self.parts
		for x in self.parts:
			#print "x in BOM.parts: ", x
			if x[2] in self.prodCounts.keys():
				self.prodCounts[x[2]] += 1
			else:
				self.prodCounts[x[2]] = 1
	
	def getCost(self, runSize=1):
		''' Get the total project BOM cost for a given production run size'''
		# Beware of sorting self.parts screwing with GUI BOM list sorting!
		self.setProdCounts()
		projProdCounts = self.prodCounts.copy()
		cost = 0
		for x in projProdCounts.keys():
			projProdCounts[x] = projProdCounts[x] * runSize
			
		for x in projProdCounts.items():
			# Find x[0] (the dict key) in the product DB
			if x[0] is "none":
				# TODO : Print a warning on screen?
				print "Warning: BOM.getCost() skipped a part with no product"
			else:
				product = self.db.select(x[0], 'products')
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
		self.writePartsListToDB()
	
	# TODO: Should the read/write methods write the actual BOM object?
	def writePartsListToDB(self):
		print "BOM.writePartsListToDB to table %s" % self.name
		self.db.delete("partslist", self.name)
		self.db.insert(self.parts, "partslist", self.name)
		
	def writeToDB(self):
		self.db.delete("bom", self.name)
		self.db.insert(self, "bom", self.name)
		
		
	def readPartsListFromDB(self):
		print "BOM.readPartsListFromDB"
		newParts = []
		self.parts = self.db.select("parts", self.name)
		print "BOM.parts from DB: ", self.parts
		# Delete any erroneously saved "init" entry
		self.db.delete("init", self.name)
		partsDic = self.db.selectdic("#prt", self.name)
		print "partsDic: \n", partsDic
		return partsDic
		
	def readFromFile(self):
		print "BOM.readFromFile"
		# Clear self.parts
		del self.parts[:]
		with open(self.input, 'rb') as f:
			reader = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			for row in reader:
				print row
				part = bomPart(row[0], row[1], row[2], row[3], self, row[4])
				#print "Part: %s %s %s %s" % (part.name, part.value, part.device, part.package)
				# Check if identical part is already in DB with a product
				# If so, preserve the product entry
				if(part.isInDB()):
					print "Part already in DB"
					oldPart = self.db.select(part.name + " #prt", self.name)
					print "oldPart: ", oldPart.name, oldPart.value, oldPart.package, oldPart.product
					if(part.value == oldPart.value and part.device == oldPart.device and part.package == oldPart.package):
						if oldPart.product != 'none':
							print "Part found in DB with existing product ", oldPart.product
							part.product = oldPart.product
						else:
							print "Part found in DB without product entry, overwriting..."
							part.writeToDB()
				else:
					print "Part not in DB, writing..."
					part.writeToDB()
				self.parts.append([part.name, part.value, part.product])
		self.writePartsListToDB() # deletes old partslist
		self.writeToDB()
		print "Parts list: ", self.parts
		