import y_serial_v060 as y_serial
import urllib2
import csv
from BeautifulSoup import BeautifulSoup, Tag, NavigableString
import shutil
import os
import urlparse
import sqlite3
from urbm import Workspace

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

VENDOR_DK = "Digi-Key"
VENDOR_FAR = "Farnell"
VENDOR_FUE = "Future"
VENDOR_JAM = "Jameco"
VENDOR_ME = "Mouser"
VENDOR_NEW = "Newark"
VENDOR_SFE = "SparkFun"

# TODO : Set these based on program config file
# This will allow the user to disable vendors they do not purchase from
VENDOR_DK_EN = True
VENDOR_FAR_EN = False
VENDOR_FUE_EN = False
VENDOR_JAM_EN = False
VENDOR_ME_EN = False
VENDOR_NEW_EN = False
VENDOR_SFE_EN = False

DOWNLOAD_DATASHEET = False	# TODO : Set these from program config
ENFORCE_MIN_QTY = True

class vendorProduct:
	''' A distributor's listing for a Product object. '''
	
	@staticmethod
	def createTables(wspace):
		''' Create the vendorProducts table for a given Workspace. '''
		try:
			(con, cur) = wspace.con_cursor()
			cur.execute('''CREATE TABLE IF NOT EXISTS vendorproducts
			(vendor TEXT, 
			vendor_pn TEXT PRIMARY KEY, 
			mfg_pn TEXT REFERENCES products(manufacturer_pn), 
			reelfee FLOAT, 
			inventory INTEGER, 
			packaging TEXT,
			category TEXT,
			family TEXT,
			series TEXT)''')
			
			cur.execute('''CREATE TABLE IF NOT EXISTS pricebreaks
			(id INTEGER PRIMARY KEY
			pn TEXT REFERENCES vendorproducts(vendor_pn) 
			qty INTEGER
			unit DOUBLE)''')
			
		except:
			print 'Product.createTables exception, probably because tables already created.'
			
		finally:
			cur.close()
			con.close()
	
	def __init__(self, vend, vendor_pn, pricesDict, inv, pkg, reel=0, cat='NULL', fam='NULL', ser='NULL'):
		self.vendor = vend
		self.vendorPN = vendor_pn
		self.prices = pricesDict
		self.reelFee = reel	# Flat per-order reeling fee (Digi-reel, MouseReel, etc)
		self.inventory = inv
		self.packaging = pkg	# Cut Tape, Tape/Reel, Tray, Tube, etc.
		self.category = cat	# "Capacitors"
		self.family = fam	# "Ceramic"
		self.series = ser	# "C" (TDK series C)
	
	def show(self):
		''' A simple print method. '''
		print 'Vendor: ', self.vendor, type(self.vendor)
		print 'Vendor PN: ', self.vendorPN, type(self.vendorPN)
		print 'Prices: ', self.prices.items(), type(self.prices.items())
		print 'Reel Fee: ', self.reelFee, type(self.reelFee)
		print 'Inventory: ', self.inventory, type(self.inventory)
		print 'Packaging: ', self.packaging, type(self.packaging)
		print 'Category: ', self.category, type(self.category)
		print 'Family: ', self.family, type(self.family)
		print 'Series: ', self.series, type(self.series)
	
	def update(self, wspace):
		''' Update an existing vendorProduct record in the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.vendor, self.vendorPN, self.reelFee, self.inventory, 
					self.packaging, self.category, self.family, self.series, self.vendorPN,)
			cur.execute('''UPDATE vendorproducts 
			SET vendor=?, vendor_pn=?, reelfee=?, inventory=?, packaging=?, 
			category=?, family=?, series=? 
			WHERE vendor_pn=?''', symbol)
				
		except:
			print 'Exception in vendorProduct(%s).update()' % self.vendorPN
			
		finally:
			cur.close()
			con.close()
	
	def insert(self, wspace):
		''' Write the vendorProduct to the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.vendor, self.vendorPN, self.reelFee, self.inventory, 
					self.packaging, self.category, self.family, self.series,)
			cur.execute('INSERT INTO vendorproducts VALUES (?,?,?,?,?,?,?,?)', symbol)
				
		except:
			print 'Exception in vendorProduct(%s).insert()' % self.vendorPN
			
		finally:
			cur.close()
			con.close()
	
	def delete(self, wspace):
		''' Delete the vendorProduct from the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.vendorPN,)
			cur.execute('DELETE FROM vendorproducts WHERE vendor_pn=?', symbol)
				
		except:
			print 'Exception in vendorProduct(%s).delete()' % self.vendorPN
			
		finally:
			cur.close()
			con.close()
	
	def fetchPriceBreaks(self, wspace):
		''' Fetch price breaks dictionary for this vendorProduct. 
		Clears and sets the self.prices dictionary directly. '''
		self.prices.clear()
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.vendorPN,)
			cur.execute('SELECT qty, unit FROM pricebreaks WHERE pn=? ORDER BY qty', symbol)
			for row in cur.fetchall():
				self.prices[row[0]] = row[1]
				
		except:
			print 'Exception in Product(%s).fetchPriceBreaks' % self.vendorPN
			
		finally:
			cur.close()
			con.close()
		
	def getPriceBreak(self, qty):
		''' Returns the (price break, unit price) list pair for the given purchase quantity.
		If qty is below the lowest break, the lowest is returned.
		TODO : Raise some kind of error/warning if not ordering enough PCBs to make the lowest break.'''
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

class Product:
	''' A physical product, independent of distributor.
	The primary identifying key is the manufacturer PN. '''
	
	@staticmethod
	def createTable(wspace):
		''' Create the Products table for a given Workspace. '''
		try:
			(con, cur) = wspace.con_cursor()
			cur.execute('''CREATE TABLE IF NOT EXISTS products
			(manufacturer TEXT, 
			manufacturer_pn TEXT PRIMARY KEY, 
			datasheet TEXT, 
			description TEXT, 
			package TEXT)''')
			
		except:
			print 'Product.createTable exception, probably because table already created.'
			
		finally:
			cur.close()
			con.close()
		
	def __init__(self, mfg, mfg_pn, database):
		self.manufacturer = mfg
		self.manufacturer_pn = mfg_pn
		self.datasheet = ""
		self.description = ""
		self.package = ""
		self.vendorProds = {}	# Key is vendorProduct.vendor + vendorProduct.vendor_pn
		self.db = database
	
	def show(self):
		''' A simple print method. '''
		print 'Manufacturer: ', self.manufacturer, type(self.manufacturer)
		print 'Manufacturer PN: ', self.manufacturer_pn, type(self.manufacturer_pn)
		print 'Datasheet: ', self.datasheet, type(self.datasheet)
		print 'Description: ', self.description, type(self.description)
		print 'Package: ', self.package, type(self.package)
		print 'Listings:'
		for listing in self.vendorProds.items():
			print "\nListing key: ", listing[0]
			listing[1].show()
		print 'DB: ', self.db, type(self.db), '\n'
	
	def update(self, wspace):
		''' Update an existing Product record in the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.manufacturer, self.manufacturer_pn, self.datasheet, self.description, 
					self.package, self.manufacturer_pn,)
			cur.execute('''UPDATE products 
			SET manufacturer=?, manufacturer_pn=?, datasheet=?, description=?, package=?, 
			WHERE manufacturer_pn=?''', symbol)
				
		except:
			print 'Exception in Product(%s).update()' % self.manufacturer_pn
			
		finally:
			cur.close()
			con.close()
	
	def insert(self, wspace):
		''' Write the Product to the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.manufacturer, self.manufacturer_pn, self.datasheet, self.description, self.package,)
			cur.execute('INSERT INTO products VALUES (?,?,?,?,?)', symbol)
				
		except:
			print 'Exception in Product(%s).insert()' % self.manufacturer_pn
			
		finally:
			cur.close()
			con.close()
	
	def delete(self, wspace):
		''' Delete the Product from the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.manufacturer_pn,)
			cur.execute('DELETE FROM products WHERE manufacturer_pn=?', symbol)
				
		except:
			print 'Exception in Product(%s).delete()' % self.manufacturer_pn
			
		finally:
			cur.close()
			con.close()
		
	def bestListing(self, qty):
		''' Return the vendorProduct listing with the best price for the given order quantity. 
		
		If the "enforce minimum quantities" option is checked in the program config,
		only returns listings where the order quantity meets/exceeds the minimum
		order quantity for the listing.'''
		lowestPrice = int('inf')
		for listing in self.vendorProds.values():
			priceBreak = listing.getPriceBreak(qty)
			if priceBreak[0] > qty and ENFORCE_MIN_QTY:
				pass
			else:
				if (priceBreak[1]*qty) + listing.reelFee < lowestPrice:
					lowestPrice = (priceBreak[1]*qty) + listing.reelFee
					best = listing
		return best
	
	def scrapeDK(self):
		''' Scrape method for Digikey. '''
		# Clear previous pricing data (in case price break keys change)
		searchURL = 'http://search.digikey.com/us/en/products/' + self.manufacturer_pn
		searchPage = urllib2.urlopen(searchURL)
		searchSoup = BeautifulSoup(searchPage)
		
		# Create a list of product URLs from the search page
		prodURLs = []
		searchTable = searchSoup.body('table', id="productTable")[0]
		#print 'searchTable: \n', searchTable
		#print 'searchTable.contents: \n', searchTable.contents
		
		# Find tbody tag in table
		tBody = searchTable.find('tbody')
		#print 'tbody: \n', type(tBody), tBody
		#print 'tbody.contents: \n', type(tBody.contents), tBody.contents
		#print 'tbody.contents[0]: \n', type(tBody.contents[0]), tBody.contents[0]
		prodRows = tBody.findAll('tr')
		#print 'prodrows: \n', type(prodRows), prodRows
		for row in prodRows:
			#print "Search row in prodRows: ", row
			anchor = row.find('a')
			# DK uses a relative path for these links
			prodURLs.append('http://search.digikey.com' + anchor['href'])
			#print 'Adding URL: ', 'http://search.digikey.com' + anchor['href']
		
		for url in prodURLs:
		
			page = urllib2.urlopen(url)
			soup = BeautifulSoup(page)
			print "URL: %s" % url
			# Get prices
			prices = {}
			priceTable = soup.body('table', id="pricing")
			# priceTable.contents[x] should be the tr tags...
			for t in priceTable:
				for r in t:
					# r.contents should be td Tags... except the first!
					if r == '\n':
						pass
					elif r.contents[0].name == 'th':
						pass
						#print "Found r.name == th"
					else:
						newBreakString = r.contents[0].string
						# Remove commas
						if newBreakString.isdigit() == False:
							newBreakString = newBreakString.replace(",", "")
						#print "newBreakString is: %s" % newBreakString					
						newBreak = int(newBreakString)
						newUnitPrice = float(r.contents[1].string)
						prices[newBreak] = newUnitPrice
						#print 'Adding break/price to pricing dict: ', (newBreak, newUnitPrice)
					
			# Get inventory
			# If the item is out of stock, the <td> that normally holds the
			# quantity available will have a text input box that we need to
			# watch out for
			invSoup = soup.body('td', id="quantityavailable")
			#print 'invSoup: ', type(invSoup), invSoup
			#print "Length of form search results: %s" % len(invSoup[0].findAll('form'))
			if len(invSoup[0].findAll('form')) > 0:
				inventory = 0
			
			else:
				invString = invSoup[0].contents[0]
				#print 'invString: ', type(invString), invString
				if invString.isdigit() == False:
					invString = invString.replace(",", "")
				inventory = int(invString)
				#print 'inventory: ', type(inventory), inventory
			
			vendor_pn = soup.body('th', text="Digi-Key Part Number")[0].parent.nextSibling.contents[0].string.__str__()
			# Get manufacturer and PN
			self.manufacturer = soup.body('th', text="Manufacturer")[0].parent.nextSibling.contents[0].string.__str__()
			#print "manufacturer is: %s" % self.manufacturer
			self.manufacturer_pn = soup.body('th', text="Manufacturer Part Number")[0].parent.nextSibling.contents[0].string.__str__()
			#print "manufacturer_pn is: %s" % self.manufacturer_pn
			
			# Get datasheet filename and download
			datasheetSoup = soup.body('th', text="Datasheets")[0].parent.nextSibling
			datasheetA = datasheetSoup.findAllNext('a')[0]
			#print "datasheetSoup is: %s" % datasheetSoup
			#print "datasheetA is: %s" % datasheetA
			self.datasheetURL = datasheetA['href']
			#print "self.datasheetURL is: %s" % self.datasheetURL
			
			r = urllib2.urlopen(urllib2.Request(self.datasheetURL))
			try:
				fileName = getFileName(url,r)
				self.datasheet = fileName;
				# TODO: Do not re-download if already saved
				if DOWNLOAD_DATASHEET:
					with open(fileName, 'wb') as f:
						shutil.copyfileobj(r,f)
			finally:
				r.close()
			#print "datasheet is: %s" % self.datasheet
			# Get remaining strings (desc, category, family, series, package)
			self.description = soup.body('th', text="Description")[0].parent.nextSibling.contents[0].string.__str__()
			#print "description is: %s" % self.description
			category = soup.body('th', text="Category")[0].parent.nextSibling.contents[0].string.__str__()
			#print "category is: %s" % category
			family = soup.body('th', text="Family")[0].parent.nextSibling.contents[0].string.__str__()
			#print "family is: %s" % family
			series = soup.body('th', text="Series")[0].parent.nextSibling.contents[0].string.__str__()
			#print "series is: %s" % series
			self.package = soup.body('th', text="Package / Case")[0].parent.nextSibling.contents[0].string.__str__()
			#print "package is: %s" % self.package
			
			packagingSoup = soup.body('th', text="Packaging")[0].parent.parent.nextSibling.contents[0]
			#print "packagingSoup: ", type(packagingSoup), packagingSoup
			if type(packagingSoup) == NavigableString:
				packaging = packagingSoup.string.__str__()
				#print "packaging (from text): ", type(packaging), packaging
			elif type(packagingSoup) == Tag:
				packaging = packagingSoup.contents[0].string.__str__()
				#print "packaging (from link): ", type(packaging), packaging
			else:
				print 'Error: DK Packaging scrape failure!'
			if "Digi-Reel" in packaging:
				packaging = "Digi-Reel"	# Remove Restricted symbol
			key = VENDOR_DK + ': ' + vendor_pn + ' (' + packaging + ')'
			self.vendorProds[key] = vendorProduct(VENDOR_DK, vendor_pn, prices, inventory, packaging)
			self.vendorProds[key].category = category
			self.vendorProds[key].family = family
			self.vendorProds[key].series = series
			if "Digi-Reel" in packaging:
				self.vendorProds[key].reelFee = 7
	
	def scrapeFAR(self):
		''' Scrape method for Farnell. '''
		print "Distributor scraping not yet implemented!"
	
	def scrapeFUE(self):
		''' Scrape method for Future Electronics. '''
		print "Distributor scraping not yet implemented!"
		
	def scrapeJAM(self):
		''' Scrape method for Jameco. '''
		print "Distributor scraping not yet implemented!"
		
	def scrapeME(self):
		''' Scrape method for Mouser Electronics. '''
		print "Distributor scraping not yet implemented!"
	
	def scrapeNEW(self):
		''' Scrape method for Newark. '''
		print "Distributor scraping not yet implemented!"
	
	def scrapeSFE(self):
		''' Scrape method for Sparkfun. '''	
		print "Distributor scraping not yet implemented!"
		# Clear previous pricing data (in case price break keys change)
		self.prices.clear()
		
		# The URL contains the numeric portion of the part number, minus any leading zeroes
		url = "http://www.sparkfun.com/products/" + str(int(self.pn.split("-")))
		page = urllib2.urlopen(url)
		soup = BeautifulSoup(page)
			
	def scrape(self):
		''' Scrape each vendor page to refresh product pricing info. '''
		self.vendorProds.clear()
		# Proceed based on vendor config
		if VENDOR_DK_EN:
			self.scrapeDK()
		if VENDOR_FAR_EN:
			self.scrapeFAR()
		if VENDOR_FUE_EN:
			self.scrapeFUE()
		if VENDOR_JAM_EN:
			self.scrapeJAM()
		if VENDOR_ME_EN:
			self.scrapeME()
		if VENDOR_NEW_EN:
			self.scrapeNEW()
		if VENDOR_SFE_EN:
			self.scrapeSFE()
		
		print 'Writing the following Product to DB: \n'
		self.show()
		self.writeToDB()
				

	def isInDB(self):
		d = self.db.selectdic(self.manufacturer_pn, "products")
		#print 'Product.isInDB: len(d) = ', len(d)
		if(len(d) != 0):
			#print 'Product.isInDB returning True.'
			return True
		else:
			return False
	
	def writeToDB(self):
		self.db.delete(self.manufacturer_pn, 'products')
		self.db.insert(self, self.manufacturer_pn + " #prod #" + self.manufacturer, 'products')
		self.db.insert(self.vendorProds, self.manufacturer_pn + " #listing", 'products')
		
	''' Sets the product fields, pulling from the local DB if possible.'''	
	def selectOrScrape(self):
		if(self.isInDB()):
			temp = self.db.select(self.manufacturer_pn + " #prod #", 'products')
			self.manufacturer = temp.manufacturer
			self.manufacturer_pn = temp.manufacturer_pn
			self.datasheet = temp.datasheet
			self.description = temp.description
			self.package = temp.package
			self.vendorProds = self.db.select(self.manufacturer_pn + " #listing", 'products')
		elif self.manufacturer_pn != "none":
			self.scrape()


		