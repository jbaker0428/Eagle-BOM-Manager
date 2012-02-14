class bomPart:
	def __init__(self, name, value, device, package, description="", product="none"):
		self.name = name
		self.value = value
		self.device = device
		self.package = package
		self.description = description
		self.product = product

	def findInBOM(self, bomFile):
		with open(bomFile, 'rb') as f:
			db = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			rownum = 0
			for row in db:
				if row[0] == self.name:
					return rownum
				rownum = rownum + 1
			return -1
	
	def isInDB(self, bomName):
		print "bomPart.isInDB was passed %s" % bomName
		if self.product == "none":
			query = self.name + ",#val=" + self.value + ",#dev=" + self.device + ",#pkg=" + self.package
		else:
			query = self.name + ",#val=" + self.value + ",#dev=" + self.device + ",#pkg=" + self.package + ",#prod=" + self.product
		print "Query: %s" % query
		dict = urbmDB.selectdic(query, bomName)
		#test = urbmDB.select(self.name, bomName)
		if len(dict) == 0:
			return False
		else:
			return True		
			
	def writeToDB(self, bomName):
		print "bomPart.writeToDB writing part %s to table %s" % (self.name, bomName)
		print "Part's product: %s" % self.product
		urbmDB.delete(self.name, bomName)
		urbmDB.insert(self, self.name + " #val=" + self.value + " #dev=" + \
		self.device + " #pkg=" + self.package + " #prod=" + self.product, bomName)