import csv
import shutil
import os
import urlparse
from urbm_bompart import bomPart
from urbm_product import Product
import y_serial_v060 as y_serial

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
		
	def delete(self):
		self.db.droptable(self.name)
	
	'''Sort self.parts by value BEFORE calling setValCounts()!'''
	def setValCounts(self):
		print "BOM.setValCounts"
		prev = "previous"
		for x in self.parts:
			if x[1] != prev[1]:
				if x[1] in self.valCounts:
					self.valCounts[x[1]] += 1
			else:
				self.valCounts[x[1]] = 1
						
			prev = x;

	'''Sort self.parts by product BEFORE calling setProdCounts()!'''
	def setProdCounts(self):
		print "BOM.setProdCounts"
		prev = "previous"
		for x in self.parts:
			if x[2] != prev[2]:
				if x[2] in self.prodCounts:
					self.prodCounts[x[2]] += 1
			else:
				self.prodCounts[x[2]] = 1
						
			prev = x;
	
	''' Get the total project BOM cost for a given production run size'''		
	def getCost(self, runSize=1):
		# TODO : Sort self.parts by product
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
				
			
	
	def writeToDB(self):
		print "BOM.writeToDB to table %s" % self.name
		self.db.delete("bomparts", self.name)
		self.db.insert(self.parts, "bomparts", self.name)
		
	def readFromFile(self):
		print "BOM.readFromFile"
		newParts = []
		self.db.insert(1, "touch", self.name) # Touch DB first
		with open(self.input, 'rb') as f:
			reader = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			for row in reader:
				print row
				part = bomPart(row[0], row[1], row[2], row[3], self, row[4])
				print "Part: %s %s %s %s" % (part.name, part.value, part.device, part.package)
				# Check if identical part is already in DB with a product
				# If so, preserve the product entry
				if(part.isInDB()):
					oldPart = self.db.select(part.name, self.name)
					if(part.value == oldPart.value and part.device == oldPart.device \
					and part.package == oldPart.package):
						part.product = oldPart.product
				part.writeToDB()
				self.parts.append((part.name, part.value, part.product))
		#parts = newParts
		self.writeToDB()