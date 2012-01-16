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

urbmDB = y_serial.Main(os.path.join(os.getcwd() + "urbm.sqlite"))

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

class Product:
	vendors = enum('DK', 'ME', 'SFE')
	def __init__(self, vendor, vendor_pn):
		self.vendor = vendor
		self.vendor_pn = vendor_pn
		self.mfg_pn = ""
		self.prices = {}
		self.inventory = 0
		self.datasheet = ""
	
	def __init__(self, vendor, vendor_pn, databaseFile):
		with open(databaseFile, 'wb') as f:
			db = csv.reader(f, delimiter',', quotechar = '"', quoting=csv.QUOTE_ALL)
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
					self.datasheet = row[5]
	
	def scrape(self):
		# Proceed based on vendor
		if self.vendor == vendors.DK:
			# Clear previous pricing data (in case price break keys change)
			self.prices.clear()
			
			url = "http://search.digikey.com/scripts/DkSearch/dksus.dll?Detail&name=" + pn
			page = urllib2.urlopen(url)
			soup = BeautifulSoup(page)
			
			# Get prices
			priceTable = soup.body('table', id="pricing")
			# priceTable.contents[x] should be the tr tags...
			for r in priceTable.contents:
				# r.contents should be td Tags... except the first!
				if r.contents[0].name == 'th':
					;	# do nothing
				else:
					newBreakString = r.contents[0].string
					# Remove commas
					if newBreakString.isdigit() == False:
						newBreakString = newBreakString.replace(",", "")					
					newBreak = int(newBreakString)
					newUnitPrice = float(r.contents[1].string)
					prices[newBreak] = newUnitPrice
					
			# Get inventory
			invString = soup.body('td', id="quantityavailable").string
			if invString.isdigit() == false:
				invString = invString.replace(",", "")
			self.inventory = int(invString)
			
			# Get manufacturer PN
			self.mfg_pn = soup.body('th', text="Manufacturer Part Number").nextSibling.string
			
			# Get datasheet filename and download
			datasheetA = self.mfg_pn = soup.body('th', text="Datasheets").nextSibling.contents[0]
			datasheetURL = datasheetA['href']
			
			r = urllib2.urlopen(urllib2.Request(url))
			try:
				fileName = fileName or getFileName(url,r)
				self.datasheet = fileName;
				with open(fileName, 'wb') as f:
					shutil.copyfileobj(r,f)
			finally:
				r.close()
			
			# TODO: Write to persistent database
		elif self.vendor == vendors.ME:
			
		elif self.vendor == vendors.SFE:
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
		urbmDB.insert(self, "#" + self.vendor_pn, 'products')

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
			db = csv.reader(f, delimiter',', quotechar = '"', quoting=csv.QUOTE_ALL)
			rownum = 0
			for row in db:
				if row[0] == self.name:
					return rownum
				rownum++
			return -1
			
	def writeToDB(self, bom):
		urbmDB.delete(self.name, bom.name)
		urbmDB.insert(self, "#" + self.name, bom.name)
		
'''For determining the name of a project's bomPart table.'''			
class BOM:
	def __init__(self, name, inputFile="bom.csv"):
		self.name = name
		self.input = inputFile
		
	def delete(self):
		urbmDB.droptable(self.name)

'''GUI class'''
class URBM:
	def __init__(self):
		# Declarations
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.window.connect("delete event", self.delete_event)
		self.mainBox = gtk.VBox(False, 0)
		self.menuBar = gtk.MenuBar()
		self.notebook = gtk.Notebook()
		
		
		self.bomTabBox = gtk.VBox(False, 0) # First tab in notebook
		self.bomToolbar = gtk.Toolbar()
		self.bomHPane = gtk.HPaned()	
		self.bomVPane = gtk.VPaned()	# Goes in right side of bomHPane
		
		self.bomFrame = gtk.Frame("BOM") # Goes in left side of bomHPane
		self.bomTableBox = gtk.VBox(False, 0) # Holds bomTable and bomRadioBox
		self.bomTable = gtk.Table(50, 6, False) # call Table.resize(rows, cols) later
		# first table row will be column labels
		self.bomRadioBox = gtk.HBox(False, 0)
		self.bomSortName = gtk.RadioButton(None, "Name")
		self.bomSortValue = gtk.RadioButton(bomSortName, "Value")
		self.bomSortPN = gtk.RadioButton(bomSortName, "Part Number")
		
		self.partInfoFrame = gtk.Frame("Part information") # Goes in top half of bomVPane
		self.partInfoRowBox = gtk.VBox(False, 0) # Fill with HBoxes
		self.partDatasheetButton = gtk.Button("Datasheet", GTK_STOCK_PROPERTIES)
		
		self.pricingFrame = gtk.frame("Pricing") # Goes in bottom half of bomVPane
		self.orderSizeScaleAdj = gtk.Adjustment(1, 1, 10000, 1, 10, 200)
		self.orderSizeScale = gtk.HScale(orderSizeScaleAdj)
		self.orderSizeText = gtk.Entry(10000)
		
		self.dbBox = gtk.VBox(False, 0) # Second tab in notebook
		self.dbToolbar = gtk.Toolbar()
		self.dbFrame = gtk.Frame("Product database") 
		self.dbTable = gtk.Table(50, 6, False)
		
		# Configuration
		self.notebook.set_tab_pos(POS_TOP)
		self.notebook.append_page(bomTabBox, "BOM Editor")
		self.notebook.append_page(dbBox, "Product Database")
		self.notebook.set_show_tabs(True)
		
		self.bomSortName.connect("toggled", self.callback, "BOM sort name")
		self.bomSortValue.connect("toggled", self.callback, "BOM sort value")
		self.bomSortPN.connect("toggled", self.callback, "BOM sort PN")
		
		# Packing
		self.mainBox.pack_start(menuBar)
		self.mainBox.pack_start(notebook)
		
def main():
	gtk.main()
	
if __name__ == "__main__":
	URBM()
	main()
