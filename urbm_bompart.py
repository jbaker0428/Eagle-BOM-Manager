import y_serial_v060 as y_serial
import types

class bomPart:
	def __init__(self, name, value, device, package, parent_bom, description="", product="none"):
		self.name = name
		self.value = value
		self.device = device
		self.package = package
		self.description = description
		self.product = product
		self.bom = parent_bom

	''' A simple print method. '''
	def show(self):
		print 'Name: ', self.name, type(self.name)
		print 'Value: ', self.value, type(self.value)
		print 'Device: ', self.device, type(self.device)
		print 'Package: ', self.package, type(self.package)
		print 'Description: ', self.description, type(self.description)
		print 'Product: ', self.product, type(self.product)
		print 'BOM: ', self.bom, type(self.bom), '\n'
		
	''' Compares the bomPart to another bomPart.'''
	def equals(self, p):
		if type(p) != type(self):
			return False
		eq = True
		if self.name != p.name:
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
		

	def findInBOM(self, bomFile):
		with open(bomFile, 'rb') as f:
			db = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			rownum = 0
			for row in db:
				if row[0] == self.name:
					return rownum
				rownum = rownum + 1
			return -1
	
	def isInDB(self):
		print "bomPart.isInDB was passed %s" % self.bom.name
		if self.product == "none":
			query = self.name + " #prt,#val=" + self.value + ",#dev=" + self.device + ",#pkg=" + self.package
		else:
			query = self.name + " #prt,#val=" + self.value + ",#dev=" + self.device + ",#pkg=" + self.package + ",#prod=" + self.product
		print "Query: %s" % query
		dict = self.bom.db.selectdic(query, self.bom.name)
		#test = self.bom.db.select(self.name, self.bom.name)
		if len(dict) == 0:
			return False
		else:
			return True		
			
	def writeToDB(self):
		print "bomPart.writeToDB writing part %s to table %s" % (self.name, self.bom.name)
		print "Part's product: %s" % self.product
		self.bom.db.delete(self.name, self.bom.name)
		self.bom.db.insert(self, self.name + " #prt, #val=" + self.value + " #dev=" + \
		self.device + " #pkg=" + self.package + " #prod=" + self.product, self.bom.name)
