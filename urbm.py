import urllib2
import csv
from BeautifulSoup import BeautifulSoup
import shutil
import os
import urlparse

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
	def __init__(self, vendor, vendor_pn)
		self.vendor = vendors.vendor
		self.vendor_pn = vendor_pn
		self.mfg_pn = ""
		self.prices = {}
		self.inventory = 0
		self.datasheet = ""
	
	def scrape(self)
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
			
		else:
			print 'Error: %s has invalid vendor: %s' % (self.pn, self.vendor)

# Database header: 	vendor, vendor_pn, mfg_pn, prices, inventory, datasheet
# Ex: 
# "DK", "445-5146-1-ND", "C1608X5R1E105K", "1:0.27,10:0.18,100:0.072,250:0.05176,500:0.0369,1000:0.027", "434671", "general_B11.pdf"

	def writeToDB(self, databaseFile)
		# TODO: Find any existing entry for this part and remove it
		db = csv.writer(open(databaseFile, 'wb'), delimiter',', quotechar = '"', quoting=csv.QUOTE_ALL)
		iter = 0
		for key in sorted(self.prices.iterkeys(), reverse=True):
			pricesStr = pricesStr + key + ":" + self.prices[key]
			iter++
			if iter < len(self.prices):
				pricesStr = pricesStr + ","
		writer.writerow(self.vendor, self.vendor_pn, self.mfg_pn, pricesStr, self.inventory, self.datasheet)


#call sorted(prices.keys(), reverse=True) on prices.keys() to evaluate the price breaks in order
