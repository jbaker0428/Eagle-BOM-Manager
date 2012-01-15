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
	def __init__(self, name, value, device, package, product = "none"):
		self.name = name
		self.value = value
		self.device = device
		self.package = package
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
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.notebook = gtk.Notebook()
		notebook.set_tab_pos(POS_TOP)
		
		bomToolbar = gtk.Toolbar()
		bomVPane = gtk.VPaned()	# First tab in notebook
		bomHPane = gtk.HPaned()	# Goes in one half of bomVPane
		
		bomFrame = gtk.Frame("BOM") # Goes in left side of bomHPane
		bomSortName = gtk.RadioButton(None, "Name")
		bomSortName.connect("toggled", self.callback, "BOM sort name")
		bomSortValue = gtk.RadioButton(bomSortName, "Value")
		bomSortValue.connect("toggled", self.callback, "BOM sort value")
		bomSortPN = gtk.RadioButton(bomSortName, "Part Number")
		bomSortPN.connect("toggled", self.callback, "BOM sort PN")
		
		partInfoFrame = gtk.Frame("Part information") # Goes in right side of bomHPane
		
		pricingFrame = gtk.frame("Pricing") # Second tab in notebook
		pricingToolbar = gtk.Toolbar()
		
		partDBFRame = gtk.Frame("Product database") # Third tab in notebook
		dbToolbar = gtk.Toolbar()
		
def main():
	gtk.main()
	
if __name__ == "__main__":
	URBM()
	main()
