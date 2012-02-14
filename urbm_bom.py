import csv
import shutil
import os
import urlparse
from urbm_bompart import bomPart
from urbm_product import Product
import y_serial_v060 as y_serial
from operator import itemgetter

'''For determining the name of a project's bomPart table.'''			
class BOM:
	def __init__(self, name, database, inputFile="bom.csv"):
		self.name = name
		self.input = inputFile
		self.parts = [] # List of 3-element lists of part name, value, and product.name
		# This is used for sorting in the BOM table in the GUI
		self.valCounts = {}
		self.prodCounts = {}
		self.db = database
		self.db.createtable(self.name)
		
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
		
		for x in self.parts:
			if x[1] in self.valCounts.keys():
				self.valCounts[x[1]] += 1
			else:
				self.valCounts[x[1]] = 1

	def setProdCounts(self):
		print "BOM.setProdCounts"
		self.prodCounts.clear()
		print "BOM.parts: ", self.parts
		for x in self.parts:
			print "x in BOM.parts: ", x
			if x[2] in self.prodCounts.keys():
				self.prodCounts[x[2]] += 1
			else:
				self.prodCounts[x[2]] = 1
	
	''' Get the total project BOM cost for a given production run size'''		
	def getCost(self, runSize=1):
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
				priceBreak = product.getPriceBreak(x[1])
				cost += priceBreak[1] * projProdCounts[x[0]]
				
		return cost
	
	''' Take in a bomPart, find it in self.parts, update product.name entry'''
	def updateParts(self, part):
		# Find p in self.parts by name
		for p in self.parts:
			if p[0] == part.name:
				p[2] = part.product
		# TODO : If inline addition of parts is added later (as in, not from a
		# CSV file), a check needs to be added here to make sure part is in self.parts
		self.writeToDB()
	
	def writeToDB(self):
		print "BOM.writeToDB to table %s" % self.name
		self.db.delete("bomlist", self.name)
		self.db.insert(self.parts, "bomlist", self.name)
		
	def readFromDB(self):
		print "BOM.readFromDB"
		newParts = []
		self.parts = self.db.select("bomlist", self.name)
		print "BOM.parts from DB: ", self.parts
		partsDic = self.db.selectdic("#prt", self.name)
		print "partsDic: \n", partsDic
		return partsDic
		
	def readFromFile(self):
		# TODO : Check if already in DB and compare part numbers
		print "BOM.readFromFile"
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
							self.updateParts(part)
							part.writeToDB()
				else:
					print "Part not in DB, writing..."
					part.writeToDB()
					self.parts.append([part.name, part.value, part.product])
		self.writeToDB()