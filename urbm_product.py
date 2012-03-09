import y_serial_v060 as y_serial
import urllib2
import csv
from BeautifulSoup import BeautifulSoup
import shutil
import os
import urlparse

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
	VENDOR_DK = "Digi-Key"
	VENDOR_FAR = "Farnell"
	VENDOR_FUE = "Future"
	VENDOR_JAM = "Jameco"
	VENDOR_ME = "Mouser"
	VENDOR_NEW = "Newark"
	VENDOR_SFE = "SparkFun"
	
	# String for selecting parts from all vendors from product table
	PROD_SEL_ALL = "#" + VENDOR_DK + ",#" + VENDOR_FAR + ",#" + VENDOR_FUE + ",#" + VENDOR_JAM + ",#" + VENDOR_ME + ",#" + VENDOR_NEW + ",#" + VENDOR_SFE
	def __init__(self, vendor, vendor_pn, database):
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
		self.db = database
	
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
		
	''' Returns the (price break, unit price) list pair for the given purchase quantity.
	If qty is below the lowest break, the lowest is returned.'''
	def getPriceBreak(self, qty):
		breaks = self.prices.keys()
		breaks.sort()
		if breaks[0] > qty:
			print "Warning: Purchase quantity is below minimum!"
			return [breaks[0], self.prices[breaks[0]]]
			# TODO : GUI warning
		for i in range(len(breaks)):
			if breaks[i] == qty or breaks[i] == max(breaks):
				return [breaks[i], self.prices[breaks[i]]]
			elif  breaks[i] > qty:
				return [breaks[i-1], self.prices[breaks[i-1]]]			
		
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
		if(len(self.db.selectdic(self.vendor_pn, "products")) != 0):
			return True
		else:
			return False
	
	def writeToDB(self):
		self.db.delete(self.vendor_pn, 'products')
		self.db.insert(self, self.vendor_pn + " #" + self.vendor + " #" + \
		self.mfg_pn, 'products')
		
	''' Sets the product fields, pulling from the local DB if possible.'''	
	def selectOrScrape(self):
		if(self.isInDB()):
			temp = self.db.select(self.vendor_pn, 'products')
			self.vendor = temp.vendor
			self.vendor_pn = temp.vendor_pn
			self.manufacturer = temp.manufacturer
			self.mfg_pn = temp.mfg_pn
			self.prices = temp.prices
			self.inventory = temp.inventory
			self.datasheet = temp.datasheet
			self.description = temp.description
			self.category = temp.category
			self.family = temp.family
			self.series = temp.series
			self.package = temp.package
		elif self.vendor_pn != "none":
			self.scrape()

#call sorted(prices.keys(), reverse=True) on prices.keys() to evaluate the price breaks in order