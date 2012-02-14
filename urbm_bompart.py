from urbm_bom import BOM

class bomPart:
	def __init__(self, name, value, device, package, description="", product="none", parent_bom):
		self.name = name
		self.value = value
		self.device = device
		self.package = package
		self.description = description
		self.product = product
		self.bom = parent_bom

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
			query = self.name + ",#val=" + self.value + ",#dev=" + self.device + ",#pkg=" + self.package
		else:
			query = self.name + ",#val=" + self.value + ",#dev=" + self.device + ",#pkg=" + self.package + ",#prod=" + self.product
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
		self.bom.db.insert(self, self.name + " #val=" + self.value + " #dev=" + \
		self.device + " #pkg=" + self.package + " #prod=" + self.product, self.bom.name)