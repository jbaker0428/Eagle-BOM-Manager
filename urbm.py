import urllib2
import csv
from BeautifulSoup import BeautifulSoup
import shutil
import os
import urlparse
import pygtk
pygtk.require('2.0')
import gtk
import y_serial_v060 as y_serial
from operator import itemgetter

urbmDB = y_serial.Main(os.path.join(os.getcwd(), "urbm.sqlite"))
urbmDB.createtable('products')
def enum(*sequential, **named):
	enums = dict(zip(sequential, range(len(sequential))), **named)
	return type('Enum', (), enums)

def getFileName(url,openUrl):
	if 'Content-Disposition' in openUrl.info():
		# If the response has Content-Disposition, try to get filename from it
		cd = dict(map(
			lambda x: x.strip().split('=') if '=' in x else (x.strip(),''),
			openUrl.info().split(';')))
		if 'filename' in cd:
			filename = cd['filename'].strip("\"'")
			if filename: return filename
	# if no filename was found above, parse it out of the final URL.
	return os.path.basename(urlparse.urlsplit(openUrl.url)[2])

def getProductDBSize():
	dict = urbmDB.selectdic("?", 'products')
	
class Product:
	VENDOR_DK = "Digi-Key"
	VENDOR_ME = "Mouser"
	VENDOR_SFE = "SparkFun"
	#vendors = enum('DK', 'ME', 'SFE')
	def __init__(self, vendor, vendor_pn):
		self.vendor = vendor
		self.vendor_pn = vendor_pn
		self.manufacturer = ""
		self.mfg_pn = ""
		self.prices = {}
		self.inventory = 0
		self.datasheet = ""
		self.description = ""
		self.category = ""
		self.family = ""
		self.series = ""
		self.package = ""
	
	'''def __init__(self, vendor, vendor_pn, databaseFile):
		with open(databaseFile, 'wb') as f:
			db = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			rownum = 0
			for row in db:
				if row[0] == vendor and row[1] == vendor_pn:
					self.vendor = vendor
					self.vendor_pn = vendor_pn
					self.mfg_pn = row[2]
					
					# prices... need to split the string two ways
					pricesStr = row[3].split(",")
					for pair in pricesStr:
						keyVal = pair.split(":")
						self.prices[keyVal[0]] = keyVal[1]
					
					self.inventory = row[4]
					self.datasheet = row[5]'''
	
	def scrape(self):
		# Proceed based on vendor
		#if self.vendor == self.vendors.DK:
		if self.vendor == Product.VENDOR_DK:
			# Clear previous pricing data (in case price break keys change)
			self.prices.clear()
			
			url = "http://search.digikey.com/us/en/products/soup/" + self.vendor_pn
			page = urllib2.urlopen(url)
			soup = BeautifulSoup(page)
			print "URL: %s" % url
			# Get prices
			priceTable = soup.body('table', id="pricing")
			# priceTable.contents[x] should be the tr tags...
			for t in priceTable:
				for r in t:
					# r.contents should be td Tags... except the first!
					if r == '\n':
						pass
					elif r.contents[0].name == 'th':
						print "Found r.name == th"
						#pass	# do nothing
					else:
						newBreakString = r.contents[0].string
						# Remove commas
						if newBreakString.isdigit() == False:
							newBreakString = newBreakString.replace(",", "")
						print "newBreakString is: %s" % newBreakString					
						newBreak = int(newBreakString)
						newUnitPrice = float(r.contents[1].string)
						self.prices[newBreak] = newUnitPrice
					
			# Get inventory
			# If the item is out of stock, the <td> that normally holds the
			# quantity available will have a text input box that we need to
			# watch out for
			invSoup = soup.body('td', id="quantityavailable")
			print "Length of form search results: %s" % len(invSoup[0].findAll('form'))
			if len(invSoup[0].findAll('form')) > 0:
				self.inventory = 0
			
			else:
				invString = invSoup[0].contents[0]
				if invString.isdigit() == False:
					invString = invString.replace(",", "")
				self.inventory = int(invString)
			
			# Get manufacturer and PN
			self.manufacturer = soup.body('th', text="Manufacturer")[0].parent.nextSibling.contents[0].string
			print "manufacturer is: %s" % self.manufacturer
			self.mfg_pn = soup.body('th', text="Manufacturer Part Number")[0].parent.nextSibling.contents[0].string
			print "mfg_pn is: %s" % self.mfg_pn
			
			# Get datasheet filename and download
			datasheetSoup = soup.body('th', text="Datasheets")[0].parent.nextSibling
			datasheetA = datasheetSoup.findAllNext('a')[0]
			print "datasheetSoup is: %s" % datasheetSoup
			print "datasheetA is: %s" % datasheetA
			datasheetURL = datasheetA['href']
			print "datasheetURL is: %s" % datasheetURL
			
			r = urllib2.urlopen(urllib2.Request(datasheetURL))
			try:
				fileName = getFileName(url,r)
				self.datasheet = fileName;
				# TODO: Do not re-download if already saved
				with open(fileName, 'wb') as f:
					shutil.copyfileobj(r,f)
			finally:
				r.close()
			print "datasheet is: %s" % self.datasheet
			# Get remaining strings (desc, category, family, series, package)
			self.description = soup.body('th', text="Description")[0].parent.nextSibling.contents[0].string
			print "description is: %s" % self.description
			self.category = soup.body('th', text="Category")[0].parent.nextSibling.contents[0].string
			print "category is: %s" % self.category
			self.family = soup.body('th', text="Family")[0].parent.nextSibling.contents[0].string
			print "family is: %s" % self.family
			self.series = soup.body('th', text="Series")[0].parent.nextSibling.contents[0].string
			print "series is: %s" % self.series
			self.package = soup.body('th', text="Package / Case")[0].parent.nextSibling.contents[0].string
			print "package is: %s" % self.package
			
			self.writeToDB()
			# TODO: Write to persistent database
		elif self.vendor == Product.VENDOR_ME:
			pass
		
		elif self.vendor == Product.VENDOR_SFE:
			# Clear previous pricing data (in case price break keys change)
			self.prices.clear()
			
			# The URL contains the numeric portion of the part number, minus any leading zeroes
			url = "http://www.sparkfun.com/products/" + str(int(self.pn.split("-")))
			page = urllib2.urlopen(url)
			soup = BeautifulSoup(page)
		else:
			print 'Error: %s has invalid vendor: %s' % (self.pn, self.vendor)

	def isInDB(self):
		dict = urbmDB.selectdic(self.vendor_pn, 'products')
		if len(dict) == 0:
			return False
		else:
			return True
	
	def writeToDB(self):
		urbmDB.delete(self.vendor_pn, 'products')
		urbmDB.insert(self, self.vendor_pn + " #" + self.vendor + " #" + \
		self.mfg_pn, 'products')

#call sorted(prices.keys(), reverse=True) on prices.keys() to evaluate the price breaks in order

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
		
'''For determining the name of a project's bomPart table.'''			
class BOM:
	def __init__(self, name, inputFile="bom.csv"):
		self.name = name
		self.input = inputFile
		self.parts = [] # List of 3-element lists of part name, value, and product.name
		# This is used for sorting in the BOM table in the GUI
		self.valCounts = {}
		self.prodCounts = {}
		
	def delete(self):
		urbmDB.droptable(self.name)
	
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
			
	def writeToDB(self):
		print "BOM.writeToDB to table %s" % self.name
		urbmDB.delete("bomparts", self.name)
		urbmDB.insert(self.parts, "bomparts", self.name)
		
	def readFromFile(self):
		print "BOM.readFromFile"
		newParts = []
		urbmDB.insert(1, "touch", self.name) # Touch DB first
		with open(self.input, 'rb') as f:
			reader = csv.reader(f, delimiter=',', quotechar = '"', quoting=csv.QUOTE_ALL)
			for row in reader:
				print row
				part = bomPart(row[0], row[1], row[2], row[3], row[4])
				print "Part: %s %s %s %s" % (part.name, part.value, part.device, part.package)
				# Check if identical part is already in DB with a product
				# If so, preserve the product entry
				if(part.isInDB(self.name)):
					oldPart = urbmDB.select(part.name, self.name)
					if(part.value == oldPart.value and part.device == oldPart.device \
					and part.package == oldPart.package):
						part.product = oldPart.product
				part.writeToDB(self.name)
				self.parts.append((part.name, part.value, part.product))
		#parts = newParts
		self.writeToDB()

active_bom = BOM("test1", os.path.join(os.getcwd(), "test.csv"))

'''GUI class'''
class URBM:
	def delete_event(self, widget, event, data=None):
		print "delete event occurred"
		return False
		
	def destroy(self, widget, data=None):
		gtk.main_quit()

	# -------- CALLBACK METHODS --------
	def readInputCallback(self, widget, data=None):
		active_bom.readFromFile()
		#Read back last entry
		urbmDB.view(1, active_bom.name)
	
	def bomRadioCallback(self, widget, data=None):
		# Set class fields for currently selected item
		self.curBomRow = int(data) 	# Convert str to int
		print "curBomRow is: %s" % self.curBomRow
		print "Selected item name label: %s" % self.bomContentLabels[self.curBomRow][0].get_text()
		self.selectedBomPart = urbmDB.select(self.bomContentLabels[self.curBomRow][0].get_text(), active_bom.name)
		# Grab the vendor part number for the selected item from the label text
		selectedPN = self.bomContentLabels[self.curBomRow][5].get_text()
		print "selectedPN is: %s" % selectedPN
		if selectedPN != "none": # Look up part in DB
			# Set class field for currently selected product
			print "Querying with selectedPN: %s" % selectedPN
			#self.selectedProduct = Product(Product.vendors.DK, "init")
			print "Number of results in dic: %s" % len(urbmDB.selectdic(selectedPN, "products"))
			if(len(urbmDB.selectdic(selectedPN, "products")) != 0):
				self.selectedProduct = urbmDB.select(selectedPN, "products")
			else:
				print "Reached scrape call"
				self.selectedProduct.vendor_pn = selectedPN
				self.selectedProduct.scrape()
				#self.selectedProduct.writeToDB()
			self.setPartInfolabels(self.selectedProduct)
	
	def bomSortCallback(self, widget, data=None):
		#print "%s was toggled %s" % (data, ("OFF", "ON")[widget.get_active()])
		
		def populateBomRow(self, part, quantity=""):
			self.bomContentLabels[rowNum][0].set_label(part.name)
			self.bomContentLabels[rowNum][1].set_label(part.value)
			self.bomContentLabels[rowNum][2].set_label(part.device)
			self.bomContentLabels[rowNum][3].set_label(part.package)
			self.bomContentLabels[rowNum][4].set_label(part.description)
			self.bomContentLabels[rowNum][5].set_label(part.product)
			self.bomContentLabels[rowNum][6].set_label(quantity)
			
		def attachBomRow(self):
			i = 0
			for label in self.bomContentLabels[rowNum]:
				self.bomTable.attach(label,  i, i+1, rowNum+1, rowNum+2)
				i += 1
				
		# Figure out which button is now selected
		if widget.get_active():
			if 'name' in data:
				active_bom.parts = sorted(active_bom.parts, key=itemgetter(0))
				old = len(self.bomContentLabels)
				self.destroyBomLabels()
				self.destroyBomRadios()
				del self.bomRadios[0:old]
				del self.bomContentLabels[0:old]
				self.bomTable.resize(len(active_bom.parts)+1, 8)
				self.bomRadios = self.createBomRadios(len(active_bom.parts))
				self.attachBomRadios()
				self.bomContentLabels = self.createBomLabels(len(active_bom.parts))
				rowNum = 0
				for p in active_bom.parts:
					# temp is a bomPart object from the DB
					temp = urbmDB.select(p[0], active_bom.name)
					populateBomRow(self, temp)
					attachBomRow(self)
					rowNum += 1
			
				
			elif 'value' in data:
				active_bom.parts = sorted(active_bom.parts, key=itemgetter(1))
				active_bom.setValCounts()
				tableLen = 1 + len(active_bom.valCounts)
				old = len(self.bomContentLabels)
				self.destroyBomLabels()
				self.destroyBomRadios()
				del self.bomRadios[0:old]
				del self.bomContentLabels[0:old]
				self.bomTable.resize(tableLen, 8)
				self.bomRadios = self.createBomRadios(len(active_bom.parts))
				self.attachBomRadios()
				self.bomContentLabels = self.createBomLabels(len(active_bom.valCounts))
				groupName = ""
				rowNum = 0
				for val in active_bom.valCounts.keys():
					group = urbmDB.selectdic("#val=" + val, active_bom.name)
					for parts in group:		# TODO: Ensure this data is what we expect
						groupName += parts.part.name + ", "
					temp = urbmDB.select("#val=" + val, bom.name)
					populateBomRow(self, temp, active_bom.valCounts[val])
					self.bomContentLabels[rowNum][0].set_label(groupName)
					attachBomRow(self)
					rowNum += 1
					
			elif 'product' in data:
				active_bom.parts = sorted(active_bom.parts, key=itemgetter(2))
				active_bom.setProdCounts()
				tableLen = 1 + len(active_bom.prodCounts)
				old = len(self.bomContentLabels)
				self.destroyBomLabels()
				self.destroyBomRadios()
				del self.bomRadios[0:old]
				del self.bomContentLabels[0:old]
				self.bomTable.resize(tableLen, 8)
				self.bomRadios = self.createBomRadios(len(active_bom.parts))
				self.attachBomRadios()
				self.bomContentLabels = self.createBomLabels(len(bom.prodCounts))
				groupName = ""
				rowNum = 0
				for prod in active_bom.prodCounts.keys():
					group = urbmDB.selectdic("#prod=" + prod, active_bom.name)
					for parts in group:	# TODO: Ensure this data is what we expect
						groupName += parts.part.name + ", "
					temp = urbmDB.select("#prod=" + prod, active_bom.name)
					populateBomRow(self, temp, active_bom.prodCounts[prod])
					self.bomContentLabels[rowNum][0].set_label(groupName)
					attachBomRow(self)
					rowNum += 1
					
			self.window.show_all()
	
	def bomSetProductCallback(self, widget, data=None):
		# Open a text input prompt window
		setProductDialog = gtk.Dialog("Set part number", self.window, 
						gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
		#, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, 
		#				gtk.STOCK_OK, gtk.RESPONSE_ACCEPT)
		self.setProductEntry = gtk.Entry()
		self.productEntryText = ""
		
		setProductDialogHBox1 = gtk.HBox()
		setProductDialogHBox2 = gtk.HBox()
		setProductVendorLabel = gtk.Label("Vendor: ")
		setProductVendorPNLabel = gtk.Label("Vendor Part Number: ")
		setProductVendorCombo = gtk.combo_box_new_text()
		
		setProductVendorCombo.append_text(Product.VENDOR_DK)
		setProductVendorCombo.append_text(Product.VENDOR_ME)
		setProductVendorCombo.append_text(Product.VENDOR_SFE)
		setProductVendorLabel.set_alignment(0.5, 0.5)
		setProductVendorPNLabel.set_alignment(0.4, 0.5)
		
		self.setProductEntry.show()
		setProductVendorCombo.show() 
		setProductDialogHBox1.pack_start(setProductVendorLabel, True, True, 0)
		setProductDialogHBox1.pack_start(setProductVendorCombo, True, True, 0)
		setProductDialogHBox2.pack_start(setProductVendorPNLabel, True, True, 0)
		setProductDialogHBox2.pack_start(self.setProductEntry, gtk.RESPONSE_ACCEPT)
		setProductDialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT)
		setProductDialog.vbox.pack_start(setProductDialogHBox1, True, True, 0)
		setProductDialog.vbox.pack_start(setProductDialogHBox2, True, True, 0)
		setProductDialogHBox1.show()
		setProductDialogHBox2.show()
		setProductVendorLabel.show()
		setProductVendorPNLabel.show()
		setProductDialog.run()
		setProductDialog.hide()
		
		self.productEntryText = self.setProductEntry.get_text()
		print "Setting selectedBomPart.product to: %s" % self.productEntryText
		self.selectedBomPart.product = self.productEntryText
		print "selectedBomPart's product field: %s" % self.selectedBomPart.product
		self.selectedBomPart.writeToDB(active_bom.name)
		self.bomContentLabels[self.curBomRow][5].set_label(self.productEntryText)
		self.bomContentLabels[self.curBomRow][5].show()
		print "Part Number label text: %s" % self.bomContentLabels[self.curBomRow][5].get_text()
		
		self.selectedProduct.vendor = setProductVendorCombo.get_active_text()
		self.selectedProduct.vendor_pn = self.productEntryText
		#TODO: Check if in DB
		self.selectedProduct = urbmDB.select(self.productEntryText, "products")
		
		self.setPartInfolabels(self.selectedProduct)
		 
	# -------- HELPER METHODS --------
	''' Create an array of strings to set bomContentLabels texts to'''
	# TODO: Method incomplete
	def setBomLabelTextsName(self):
		self.bomLabelTexts = []
		#for x in range(numRows):
		#rowNum = 0
		for p in active_bom.parts:
			# temp is a bomPart object from the DB
			temp = urbmDB.select(p[0], active_bom.name)
			self.bomLabelTexts.append((part.name, part.value, part.device, part.package, part.description, part.product))
			#populateBomRow(self, temp)
			#attachBomRow(self)
			#rowNum += 1
		#rowLabels[0].set_label(part.name)
		#rowLabels[1].set_label(part.value)
		#rowLabels[2].set_label(part.device)
		#rowLabels[3].set_label(part.package)
		#rowLabels[4].set_label(part.description)
		#rowLabels[5].set_label(part.product.name)
		#rowLabels[6].set_label(quantity)
	
	# TODO: Method incomplete
	def populateBomRow(self, labelRow, stringsTuple, quantity=""):
		for i in range(6):
			labelRow[i].set_label(stringTuple[i])
			
		self.bomContentLabels[rowNum][0].set_label(part.name)
		self.bomContentLabels[rowNum][1].set_label(part.value)
		self.bomContentLabels[rowNum][2].set_label(part.device)
		self.bomContentLabels[rowNum][3].set_label(part.package)
		self.bomContentLabels[rowNum][4].set_label(part.description)
		self.bomContentLabels[rowNum][5].set_label(part.product)
		self.bomContentLabels[rowNum][6].set_label(quantity)
		
	def bomTableHeaders(self):
		self.bomTable.attach(self.bomColLabel1, 0, 1, 0, 1)
		self.bomTable.attach(self.bomColLabel2, 1, 2, 0, 1)
		self.bomTable.attach(self.bomColLabel3, 2, 3, 0, 1)
		self.bomTable.attach(self.bomColLabel4, 3, 4, 0, 1)
		self.bomTable.attach(self.bomColLabel5, 4, 5, 0, 1)
		self.bomTable.attach(self.bomColLabel6, 5, 6, 0, 1)
		self.bomTable.attach(self.bomColLabel7, 6, 7, 0, 1)
		
	def createBomLabels(self, numRows):	
		rows = []
		for x in range(numRows):
			#def createBomLabelRow(self):
			row = []
			for i in range(7):
				row.append(gtk.Label(None))
			#	return row
			#rows.append(createBomLabelRow(self))
			rows.append(row)
		return rows
	
	def destroyBomLabels(self):
		for x in self.bomContentLabels:
			for y in x:
				y.destroy()
	
	def createBomRadios(self, numRows):
		radios = []
		for x in range(numRows):
			radios.append(gtk.RadioButton(self.bomRadioGroup))
			radios[x].connect("toggled", self.bomRadioCallback, str(x))
		return radios
	
	def attachBomRadios(self):
		r = 0
		for radio in self.bomRadios:
			self.bomTable.attach(radio,  0, 7, r+1, r+2)
			r += 1
	
	def destroyBomRadios(self):
		for r in self.bomRadios:
			r.destroy()
	
	def setPartInfolabels(self, prod):
		self.partInfoVendorLabel2.set_text(prod.vendor)
		self.partInfoVendorPNLabel2.set_text(prod.vendor_pn)
		self.partInfoInventoryLabel2.set_text(str(prod.inventory))
		self.partInfoManufacturerLabel2.set_text(prod.manufacturer)
		self.partInfoManufacturerPNLabel2.set_text(prod.mfg_pn)
		self.partInfoDescriptionLabel2.set_text(prod.description)
		self.partInfoDatasheetLabel2.set_text(prod.datasheet)
		self.partInfoCategoryLabel2.set_text(prod.category)
		self.partInfoFamilyLabel2.set_text(prod.family)
		self.partInfoSeriesLabel2.set_text(prod.series)
		self.partInfoPackageLabel2.set_text(prod.package)

	#def populateBomRow(self, rowLabels, part, quantity=None):
	#def populateBomRow(self, rn, part, quantity=None):
	#	print self.bomContentLabels[rn][0]
		#rowLabels[0].set_label(part.name)
		#rowLabels[1].set_label(part.value)
		#rowLabels[2].set_label(part.device)
		#rowLabels[3].set_label(part.package)
		#rowLabels[4].set_label(part.description)
		#rowLabels[5].set_label(part.product.name)
		#rowLabels[6].set_label(quantity)
	
	''' @param rowNum considers index 0 to be the first row of content after headers'''
	#def attachBomRow(self, rowLabels, rowNum):
		#i = 0
		#for label in rowLabels:
			#self.bomTable.attach(label,  i, i+1, rowNum+1, rowNum+2)
		
	def __init__(self):
		# -------- DECLARATIONS --------
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.mainBox = gtk.VBox(False, 0)
		self.menuBar = gtk.MenuBar()
		self.notebook = gtk.Notebook()
		self.bomTabLabel = gtk.Label("BOM Editor")
		self.dbTabLabel = gtk.Label("Product Database")
		
		self.bomTabBox = gtk.VBox(False, 0) # First tab in notebook
		self.bomToolbar = gtk.Toolbar()
		self.bomReadInputButton = gtk.ToolButton(None, "Read CSV")
		self.bomSetProductButton = gtk.ToolButton(None, "Set Product")
		self.bomHPane = gtk.HPaned()	
		self.bomVPane = gtk.VPaned()	# Goes in right side of bomHPane
		
		self.bomFrame = gtk.Frame("BOM") # Goes in left side of bomHPane
		self.bomTableBox = gtk.VBox(False, 0) # Holds bomScrollWin and bomRadioBox
		self.bomScrollWin = gtk.ScrolledWindow() # Holds bomTable
		self.bomTable = gtk.Table(50, 8, False) 
		
		# first table row will be column labels
		self.bomColLabel1 = gtk.Label("Part")
		self.bomColLabel2 = gtk.Label("Value")
		self.bomColLabel3 = gtk.Label("Device")
		self.bomColLabel4 = gtk.Label("Package")
		self.bomColLabel5 = gtk.Label("Description")
		self.bomColLabel6 = gtk.Label("Part Number")
		self.bomColLabel7 = gtk.Label("Quantity")
		self.bomContentLabels = []
		self.bomRadioGroup = gtk.RadioButton(None)
		self.bomRadios = self.createBomRadios(49)
		
		self.bomRadioBox = gtk.HBox(False, 0)
		self.bomRadioLabel = gtk.Label("Group by:")
		self.bomSortName = gtk.RadioButton(None, "Name")
		self.bomSortValue = gtk.RadioButton(self.bomSortName, "Value")
		self.bomSortPN = gtk.RadioButton(self.bomSortName, "Part Number")
		
		self.selectedProduct = Product(Product.VENDOR_DK, "init")
		
		self.partInfoFrame = gtk.Frame("Part information") # Goes in top half of bomVPane
		self.partInfoRowBox = gtk.VBox(False, 0) # Fill with HBoxes 
		
		self.partInfoInfoTable = gtk.Table(11, 2, False) # Vendor, PNs, inventory, etc
		self.partInfoVendorLabel1 = gtk.Label("Vendor: ")
		self.partInfoVendorLabel2 = gtk.Label(None)
		self.partInfoVendorPNLabel1 = gtk.Label("Vendor Part Number: ")
		self.partInfoVendorPNLabel2 = gtk.Label(None)
		self.partInfoInventoryLabel1 = gtk.Label("Inventory: ")
		self.partInfoInventoryLabel2 = gtk.Label(None)
		self.partInfoManufacturerLabel1 = gtk.Label("Manufacturer: ")
		self.partInfoManufacturerLabel2 = gtk.Label(None)
		self.partInfoManufacturerPNLabel1 = gtk.Label("Manufacturer Part Number: ")
		self.partInfoManufacturerPNLabel2 = gtk.Label(None)
		self.partInfoDescriptionLabel1 = gtk.Label("Description: ")
		self.partInfoDescriptionLabel2 = gtk.Label(None)
		self.partInfoDatasheetLabel1 = gtk.Label("Datasheet filename: ")
		self.partInfoDatasheetLabel2 = gtk.Label(None)
		self.partInfoCategoryLabel1 = gtk.Label("Category: ")
		self.partInfoCategoryLabel2 = gtk.Label(None)
		self.partInfoFamilyLabel1 = gtk.Label("Family: ")
		self.partInfoFamilyLabel2 = gtk.Label(None)
		self.partInfoSeriesLabel1 = gtk.Label("Series: ")
		self.partInfoSeriesLabel2 = gtk.Label(None)
		self.partInfoPackageLabel1 = gtk.Label("Package/case: ")
		self.partInfoPackageLabel2 = gtk.Label(None)
		
		self.partInfoPricingTable = gtk.Table(8, 3 , False) # Price breaks
		self.priceBreakLabels = []
		for i in range(10):
			self.priceBreakLabels.append(gtk.Label(None))
		
		self.unitPriceLabels = []
		for i in range(10):
			self.unitPriceLabels.append(gtk.Label(None))
		
		self.extPriceLabels = []
		for i in range(10):
			self.extPriceLabels.append(gtk.Label(None))
		
		self.partInfoButtonBox = gtk.HBox(False, 0)

		self.scrapeButton = gtk.Button("Scrape", stock=gtk.STOCK_REFRESH)
		self.partDatasheetButton = gtk.Button("Datasheet", stock=gtk.STOCK_PROPERTIES)
		
		self.pricingFrame = gtk.Frame("Project pricing") # Goes in bottom half of bomVPane
		self.orderSizeScaleAdj = gtk.Adjustment(1, 1, 10000, 1, 10, 200)
		self.orderSizeScale = gtk.HScale(self.orderSizeScaleAdj)
		self.orderSizeText = gtk.Entry(10000)
		
		self.dbBox = gtk.VBox(False, 0) # Second tab in notebook
		self.dbToolbar = gtk.Toolbar()
		self.dbFrame = gtk.Frame("Product database") 
		self.dbScrollWin = gtk.ScrolledWindow()
		self.dbTable = gtk.Table(50, 6, False)
		self.dbVendorLabel = gtk.Label("Vendor")
		self.dbVendorPNLabel = gtk.Label("Vendor Part Number")
		self.dbInventoryLabel = gtk.Label("Inventory")
		self.dbManufacturerLabel = gtk.Label("Manufacturer")
		self.dbManufacturerPNLabel = gtk.Label("Manufacturer Part Number")
		self.dbDescriptionLabel = gtk.Label("Description")
		self.dbDatasheetLabel = gtk.Label("Datasheet filename")
		self.dbCategoryLabel = gtk.Label("Category")
		self.dbFamilyLabel = gtk.Label("Family")
		self.dbSeriesLabel = gtk.Label("Series")
		self.dbPackageLabel = gtk.Label("Package/case")
		
		# -------- CONFIGURATION --------
		self.window.set_title("Unified Robotics BOM Manager") 
		# TODO: Add project name to window title on file open
		self.window.connect("delete_event", self.delete_event)
		self.window.connect("destroy", self.destroy)
		
		self.notebook.set_tab_pos(gtk.POS_TOP)
		self.notebook.append_page(self.bomTabBox, self.bomTabLabel)
		self.notebook.append_page(self.dbBox, self.dbTabLabel)
		self.notebook.set_show_tabs(True)
		
		self.bomReadInputButton.connect("clicked", self.readInputCallback, "read")
		self.bomSetProductButton.connect("clicked", self.bomSetProductCallback, "setPN")
		self.bomScrollWin.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		
		self.dbScrollWin.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		
		self.bomSortName.connect("toggled", self.bomSortCallback, "name")
		self.bomSortValue.connect("toggled", self.bomSortCallback, "value")
		self.bomSortPN.connect("toggled", self.bomSortCallback, "product")
		
		self.partInfoVendorLabel1.set_alignment(0.0, 0.5)
		self.partInfoVendorLabel2.set_alignment(1.0, 0.5)
		self.partInfoVendorPNLabel1.set_alignment(0.0, 0.5)
		self.partInfoVendorPNLabel2.set_alignment(1.0, 0.5)
		self.partInfoInventoryLabel1.set_alignment(0.0, 0.5)
		self.partInfoInventoryLabel2.set_alignment(1.0, 0.5)
		self.partInfoManufacturerLabel1.set_alignment(0.0, 0.5)
		self.partInfoManufacturerLabel2.set_alignment(1.0, 0.5)
		self.partInfoManufacturerPNLabel1.set_alignment(0.0, 0.5)
		self.partInfoManufacturerPNLabel2.set_alignment(1.0, 0.5)
		self.partInfoDescriptionLabel1.set_alignment(0.0, 0.5)
		self.partInfoDescriptionLabel2.set_alignment(1.0, 0.5)
		self.partInfoDatasheetLabel1.set_alignment(0.0, 0.5)
		self.partInfoDatasheetLabel2.set_alignment(1.0, 0.5)
		self.partInfoCategoryLabel1.set_alignment(0.0, 0.5)
		self.partInfoCategoryLabel2.set_alignment(1.0, 0.5)
		self.partInfoFamilyLabel1.set_alignment(0.0, 0.5)
		self.partInfoFamilyLabel2.set_alignment(1.0, 0.5)
		self.partInfoSeriesLabel1.set_alignment(0.0, 0.5)
		self.partInfoSeriesLabel2.set_alignment(1.0, 0.5)
		self.partInfoPackageLabel1.set_alignment(0.0, 0.5)
		self.partInfoPackageLabel2.set_alignment(1.0, 0.5)
		
		# -------- PACKING AND ADDING --------
		self.mainBox.pack_start(self.menuBar)
		self.mainBox.pack_start(self.notebook)
		self.window.add(self.mainBox)
		
		self.bomTabBox.pack_start(self.bomToolbar)
		self.bomToolbar.insert(self.bomReadInputButton, 0)
		self.bomToolbar.insert(self.bomSetProductButton, 1)
		#self.bomTabBox.pack_start(self.bomReadInputButton)
		
		# TODO : Add toolbar elements
		
		self.bomTabBox.pack_start(self.bomHPane)
		self.bomHPane.pack1(self.bomFrame, True, True)
		self.bomHPane.add2(self.bomVPane)
		self.bomVPane.add1(self.partInfoFrame)
		self.bomVPane.add2(self.pricingFrame)
		
		# BOM Frame elements
		self.bomFrame.add(self.bomTableBox)
		
		self.bomTableBox.pack_start(self.bomScrollWin, True, True, 0)
		self.bomScrollWin.add_with_viewport(self.bomTable)
		self.bomTableBox.pack_end(self.bomRadioBox, False, False, 0)

		self.bomTable.set_col_spacings(10)
		self.bomTableHeaders()
		self.attachBomRadios()
		# The following commented lines are kept (for now) as a reference for
		# how to display the BOM in the table
		#self.testRadio1 = gtk.RadioButton(None)
		#self.aLabel1 = gtk.Label("R1")
		#self.aLabel2 = gtk.Label("10k")
		#self.testRadio2 = gtk.RadioButton(self.testRadio1)
		#self.bLabel1 = gtk.Label("C1")
		#self.bLabel2 = gtk.Label("10 uF")
		#self.bomTable.attach(self.testRadio1, 0, 7, 1, 2)
		#self.bomTable.attach(self.aLabel1, 0, 1, 1, 2)
		#self.bomTable.attach(self.aLabel2, 1, 2, 1, 2)
		#self.bomTable.attach(self.testRadio2, 0, 7, 2, 3)
		#self.bomTable.attach(self.bLabel1, 0, 1, 2, 3)
		#self.bomTable.attach(self.bLabel2, 1, 2, 2, 3)
		
		self.bomRadioBox.pack_start(self.bomRadioLabel)
		self.bomRadioBox.pack_start(self.bomSortName)
		self.bomRadioBox.pack_start(self.bomSortValue)
		self.bomRadioBox.pack_start(self.bomSortPN)
		
		# Part info frame elements
		self.partInfoFrame.add(self.partInfoRowBox)
		self.partInfoRowBox.pack_start(self.partInfoInfoTable)
		self.partInfoInfoTable.attach(self.partInfoVendorLabel1, 0, 1, 0, 1)
		self.partInfoInfoTable.attach(self.partInfoVendorPNLabel1, 0, 1, 1, 2)
		self.partInfoInfoTable.attach(self.partInfoInventoryLabel1, 0, 1, 2, 3)
		self.partInfoInfoTable.attach(self.partInfoManufacturerLabel1, 0, 1, 3, 4)
		self.partInfoInfoTable.attach(self.partInfoManufacturerPNLabel1, 0, 1, 4, 5)
		self.partInfoInfoTable.attach(self.partInfoDescriptionLabel1, 0, 1, 5, 6)
		self.partInfoInfoTable.attach(self.partInfoDatasheetLabel1, 0, 1, 6, 7)
		self.partInfoInfoTable.attach(self.partInfoCategoryLabel1, 0, 1, 7, 8)
		self.partInfoInfoTable.attach(self.partInfoFamilyLabel1, 0, 1, 8, 9)
		self.partInfoInfoTable.attach(self.partInfoSeriesLabel1, 0, 1, 9, 10)
		self.partInfoInfoTable.attach(self.partInfoPackageLabel1, 0, 1, 10, 11)
		
		self.partInfoInfoTable.attach(self.partInfoVendorLabel2, 1, 2, 0, 1)
		self.partInfoInfoTable.attach(self.partInfoVendorPNLabel2, 1, 2, 1, 2)
		self.partInfoInfoTable.attach(self.partInfoInventoryLabel2, 1, 2, 2, 3)
		self.partInfoInfoTable.attach(self.partInfoManufacturerLabel2, 1, 2, 3, 4)
		self.partInfoInfoTable.attach(self.partInfoManufacturerPNLabel2, 1, 2, 4, 5)
		self.partInfoInfoTable.attach(self.partInfoDescriptionLabel2, 1, 2, 5, 6)
		self.partInfoInfoTable.attach(self.partInfoDatasheetLabel2, 1, 2, 6, 7)
		self.partInfoInfoTable.attach(self.partInfoCategoryLabel2, 1, 2, 7, 8)
		self.partInfoInfoTable.attach(self.partInfoFamilyLabel2, 1, 2, 8, 9)
		self.partInfoInfoTable.attach(self.partInfoSeriesLabel2, 1, 2, 9, 10)
		self.partInfoInfoTable.attach(self.partInfoPackageLabel2, 1, 2, 10, 11)
		
		self.partInfoRowBox.pack_start(self.partInfoPricingTable)
		for i in range(len(self.priceBreakLabels)):
			self.partInfoPricingTable.attach(self.priceBreakLabels[i], 0, 1, i, i+1)
			self.priceBreakLabels[i].set_alignment(0.5, 0.5)
			
		for i in range(len(self.unitPriceLabels)):
			self.partInfoPricingTable.attach(self.unitPriceLabels[i], 1, 2, i, i+1)
			self.unitPriceLabels[i].set_alignment(1.0, 0.5)
			
		for i in range(len(self.extPriceLabels)):
			self.partInfoPricingTable.attach(self.extPriceLabels[i], 2, 3, i, i+1)
			self.extPriceLabels[i].set_alignment(1.0, 0.5)
			
		self.partInfoRowBox.pack_start(self.partInfoButtonBox)
		
		self.dbBox.pack_start(self.dbToolbar)
		self.dbBox.pack_start(self.dbFrame)
		self.dbFrame.add(self.dbScrollWin)
		self.dbScrollWin.add_with_viewport(self.dbTable)
		self.dbTable.attach(self.dbVendorLabel, 0, 1, 0, 1)
		self.dbTable.attach(self.dbVendorPNLabel, 1, 2, 0, 1)
		self.dbTable.attach(self.dbInventoryLabel, 2, 3, 0, 1)
		self.dbTable.attach(self.dbManufacturerLabel, 3, 4, 0, 1)
		self.dbTable.attach(self.dbManufacturerPNLabel, 4, 5, 0, 1)
		self.dbTable.attach(self.dbDescriptionLabel, 5, 6, 0, 1)
		self.dbTable.attach(self.dbDatasheetLabel, 6, 7, 0, 1)
		self.dbTable.attach(self.dbCategoryLabel, 7, 8, 0, 1)
		self.dbTable.attach(self.dbFamilyLabel, 8, 9, 0, 1)
		self.dbTable.attach(self.dbSeriesLabel, 9, 10, 0, 1)
		self.dbTable.attach(self.dbPackageLabel, 10, 11, 0, 1)
		self.dbTable.set_col_spacings(10)
		
		# Show everything
		self.mainBox.show_all()
		self.window.show()
def main():
	gtk.main()
	
if __name__ == "__main__":
	URBM()
	main()
