import urllib2
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
			inventory INTEGER, 
			packaging TEXT,
			reelfee FLOAT, 
			category TEXT,
			family TEXT,
			series TEXT)''')
			
			cur.execute('''CREATE TABLE IF NOT EXISTS pricebreaks
			(id INTEGER PRIMARY KEY
			pn TEXT REFERENCES vendorproducts(vendor_pn) 
			qty INTEGER
			unit DOUBLE)''')
			
		finally:
			cur.close()
			con.close()
	
	@staticmethod
	def select_by_vendor_pn(pn, wspace):
		''' Return the vendorProduct(s) of given vendor part number in a list. '''
		vprods = []
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (pn,)
			cur.execute('SELECT * FROM vendorproducts WHERE vendor_pn=?', symbol)
			for row in cur.fetchall():
				vprod = vendorProduct(row[0], row[1], row[2], {}, row[3], row[4], row[5], row[6], row[7], row[8])
				vprod.fetchPriceBreaks(wspace)
				vprods.append(vprod)
			
		finally:
			cur.close()
			con.close()
			return vprods
	
	@staticmethod
	def select_by_manufacturer_pn(pn, wspace):
		''' Return the vendorProduct(s) of given manufacturer part number in a list. '''
		vprods = []
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (pn,)
			cur.execute('SELECT * FROM vendorproducts WHERE mfg_pn=?', symbol)
			for row in cur.fetchall():
				vprod = vendorProduct(row[0], row[1], row[2], {}, row[3], row[4], row[5], row[6], row[7], row[8])
				vprod.fetchPriceBreaks(wspace)
				vprods.append(vprod)
			
		finally:
			cur.close()
			con.close()
			return vprods
	
	def __init__(self, vend, vendor_pn, mfg_pn, pricesDict, inv, pkg, reel=0, cat='NULL', fam='NULL', ser='NULL'):
		self.vendor = vend
		self.vendorPN = vendor_pn
		self.manufacturer_pn = mfg_pn
		self.prices = pricesDict
		self.inventory = inv
		self.packaging = pkg	# Cut Tape, Tape/Reel, Tray, Tube, etc.
		self.reelFee = reel	# Flat per-order reeling fee (Digi-reel, MouseReel, etc)
		self.category = cat	# "Capacitors"
		self.family = fam	# "Ceramic"
		self.series = ser	# "C" (TDK series C)
	
	def show(self):
		''' A simple print method. '''
		print 'Vendor: ', self.vendor, type(self.vendor)
		print 'Vendor PN: ', self.vendorPN, type(self.vendorPN)
		print 'Product MFG PN: ', self.manufacturer_pn, type(self.manufacturer_pn)
		print 'Prices: ', self.prices.items(), type(self.prices.items())
		print 'Inventory: ', self.inventory, type(self.inventory)
		print 'Packaging: ', self.packaging, type(self.packaging)
		print 'Reel Fee: ', self.reelFee, type(self.reelFee)
		print 'Category: ', self.category, type(self.category)
		print 'Family: ', self.family, type(self.family)
		print 'Series: ', self.series, type(self.series)
	
	def equals(self, vp):
		''' Compares the vendorProduct to another vendorProduct.'''
		if type(vp) != type(self):
			return False
		eq = True
		if self.vendor != vp.vendor:
			eq = False
		if self.vendorPN != vp.vendorPN:
			eq = False
		if self.manufacturer_pn != vp.manufacturer_pn:
			eq = False
		for p in self.prices.items():
			if p not in vp.prices.items():
				eq = False
		if self.inventory != vp.inventory:
			eq = False
		if self.packaging != vp.packaging:
			eq = False
		if self.reelFee != vp.reelFee:
			eq = False
		if self.category != vp.category:
			eq = False
		if self.family != vp.family:
			eq = False
		if self.series != vp.series:
			eq = False
		return eq
	
	def key(self):
		''' Return a dictionary key as used by the GUI for this vendorProduct.
		Format: key = vendor + ': ' + vendor_pn + ' (' + packaging + ')' '''
		key = self.vendor + ': ' + self.vendorPN + ' (' + self.packaging + ')'
		return key
	
	def update(self, wspace):
		''' Update an existing vendorProduct record in the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			cur.execute('DELETE FROM pricebreaks WHERE pn=?', (self.vendorPN,))
			for pb in self.prices.items():
				t = (self.vendorPN, pb[0], pb[1],)
				cur.execute('INSERT OR REPLACE INTO pricebreaks VALUES (NULL,?,?,?)', t)
			
			symbol = (self.vendor, self.vendorPN, self.manufacturer_pn, self.inventory, self.packaging,
					self.reelFee, self.category, self.family, self.series, self.vendorPN,)
			cur.execute('''UPDATE vendorproducts 
			SET vendor=?, vendor_pn=?, self.mfg_pn=?, inventory=?, packaging=?, reelfee=?, 
			category=?, family=?, series=? 
			WHERE vendor_pn=?''', symbol)
			
		finally:
			cur.close()
			con.close()
	
	def insert(self, wspace):
		''' Write the vendorProduct to the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.vendor, self.vendorPN, self.manufacturer_pn, self.inventory, self.packaging,
					self.reelFee, self.category, self.family, self.series,)
			cur.execute('INSERT OR REPLACE INTO vendorproducts VALUES (?,?,?,?,?,?,?,?,?)', symbol)
			
			cur.execute('DELETE FROM pricebreaks WHERE pn=?', (self.vendorPN,))
			for pb in self.prices.items():
				t = (self.vendorPN, pb[0], pb[1],)
				cur.execute('INSERT OR REPLACE INTO pricebreaks VALUES (NULL,?,?,?)', t)
		finally:
			cur.close()
			con.close()
	
	def delete(self, wspace):
		''' Delete the vendorProduct from the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.vendorPN,)
			cur.execute('DELETE FROM pricebreaks WHERE pn=?', symbol)
			cur.execute('DELETE FROM vendorproducts WHERE vendor_pn=?', symbol)
			
		finally:
			cur.close()
			con.close()
	
	def fetchPriceBreaks(self, wspace):
		''' Fetch price breaks dictionary for this vendorProduct. 
		Clears and sets the self.prices dictionary directly. '''
		#print 'self.prices: ', type(self.prices), self.prices
		self.prices.clear()
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.vendorPN,)
			cur.execute('SELECT qty, unit FROM pricebreaks WHERE pn=? ORDER BY qty', symbol)
			for row in cur.fetchall():
				self.prices[row[0]] = row[1]

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
	
	@staticmethod
	def select_all(wspace):
		''' Return the entire product table except the 'NULL' placeholder row. '''
		prods = []
		try:
			(con, cur) = wspace.con_cursor()
			
			cur.execute('SELECT * FROM products')
			for row in cur.fetchall():
				if row[1] != 'NULL':
					prod = Product(row[0], row[1], row[2], row[3], row[4])
					prod.fetchListings(wspace)
					prods.append(prod)
			
		finally:
			cur.close()
			con.close()
			return prods
	
	@staticmethod
	def select_by_pn(pn, wspace):
		''' Return the Product(s) of given part number in a list. '''
		prods = []
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (pn,)
			cur.execute('SELECT * FROM products WHERE manufacturer_pn=?', symbol)
			for row in cur.fetchall():
				prod = Product(row[0], row[1], row[2], row[3], row[4])
				prod.fetchListings(wspace)
				prods.append(prod)
			
		finally:
			cur.close()
			con.close()
			return prods
		
	def __init__(self, mfg, mfg_pn, dsheet='NULL', desc='NULL', pkg='NULL'):
		self.manufacturer = mfg
		self.manufacturer_pn = mfg_pn
		self.datasheet = dsheet
		self.description = desc
		self.package = pkg
		self.vendorProds = {}	# Key is key = vendor + ': ' + vendor_pn + ' (' + packaging + ')'
	
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
	
	def equals(self, p):
		''' Compares the Product to another Product.'''
		if type(p) != type(self):
			return False
		eq = True
		if self.manufacturer != p.manufacturer:
			eq = False
		if self.manufacturer_pn != p.manufacturer_pn:
			eq = False
		if self.datasheet != p.datasheet:
			eq = False
		if self.description != p.description:
			eq = False
		if self.package != p.package:
			eq = False
		for k in self.vendorProds.keys():
			if k not in p.vendorProds.keys():
				eq = False
			else:
				if self.vendorProds[k].equals(p.vendorProds[k]) == False:
					eq = False
		return eq
	
	def update(self, wspace):
		''' Update an existing Product record in the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.manufacturer, self.manufacturer_pn, self.datasheet, self.description, 
					self.package, self.manufacturer_pn,)
			cur.execute('''UPDATE products 
			SET manufacturer=?, manufacturer_pn=?, datasheet=?, description=?, package=? 
			WHERE manufacturer_pn=?''', symbol)
			
		finally:
			cur.close()
			con.close()
	
	def insert(self, wspace):
		''' Write the Product to the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.manufacturer, self.manufacturer_pn, self.datasheet, self.description, self.package,)
			cur.execute('INSERT OR REPLACE INTO products VALUES (?,?,?,?,?)', symbol)
				
		finally:
			cur.close()
			con.close()
	
	def delete(self, wspace):
		''' Delete the Product from the DB. '''
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.manufacturer_pn,)
			cur.execute('DELETE FROM products WHERE manufacturer_pn=?', symbol)
			
		finally:
			cur.close()
			con.close()
	
	def fetchListings(self, wspace):
		''' Fetch vendorProds dictionary for this Product. 
		Clears and sets the self.vendorProds dictionary directly. '''
		self.vendorProds.clear()
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.manufacturer_pn,)
			cur.execute('SELECT * FROM vendorproducts WHERE mfg_pn=? ORDER BY vendor', symbol)
			for row in cur.fetchall():
				vprod = vendorProduct(row[0], row[1], row[2], {}, row[3], row[4], row[5], row[6], row[7], row[8])
				vprod.fetchPriceBreaks(wspace)
				self.vendorProds[vprod.key()] = vprod
				print 'Setting vendorProds[%s] = ' % vprod.key()
				vprod.show()
			
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
	
	def scrapeDK(self, wspace):
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
				print 'inventory: ', type(inventory), inventory
			
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
				print "packaging (from text): ", type(packaging), packaging
			elif type(packagingSoup) == Tag:
				packaging = packagingSoup.contents[0].string.__str__()
				print "packaging (from link): ", type(packaging), packaging
			else:
				print 'Error: DK Packaging scrape failure!'
			if "Digi-Reel" in packaging:
				packaging = "Digi-Reel"	# Remove Restricted symbol
			key = VENDOR_DK + ': ' + vendor_pn + ' (' + packaging + ')'
			self.vendorProds[key] = vendorProduct(VENDOR_DK, vendor_pn, self.manufacturer_pn, prices, inventory, packaging)
			#v = vendorProduct(VENDOR_DK, vendor_pn, self.manufacturer_pn, prices, inventory, pkg, reel, cat, fam, ser)
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
			
	def scrape(self, wspace):
		''' Scrape each vendor page to refresh product pricing info. '''
		self.vendorProds.clear()
		# Proceed based on vendor config
		if VENDOR_DK_EN:
			self.scrapeDK(wspace)
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
		#self.show()
		if self.isInDB(wspace):
			self.update(wspace)
		else:
			self.insert(wspace)
		for vprod in self.vendorProds.values():
			vprod.insert(wspace)
				

	def isInDB(self, wspace):
		try:
			(con, cur) = wspace.con_cursor()
			
			symbol = (self.manufacturer_pn,)
			cur.execute('SELECT * FROM products WHERE manufacturer_pn=?', symbol)
			#rows = cur.fetchall
			#if len(rows) == 0:
			#	return False
			#else:
			#	return True
			row = cur.fetchone()
			#if row == tuple:
			#	return True
			#else:
			#	return False
			print 'Row: ', row
			#print 'Rows: ', rows
			
		finally:
			cur.close()
			con.close()
			if row is None:
				return False
			else:
				return True
		
	''' Sets the product fields, pulling from the local DB if possible.'''	
	def selectOrScrape(self, wspace):
		if(self.isInDB(wspace)):
			temp = Product.select_by_pn(self.manufacturer_pn, wspace)[0]
			self.manufacturer = temp.manufacturer
			self.manufacturer_pn = temp.manufacturer_pn
			self.datasheet = temp.datasheet
			self.description = temp.description
			self.package = temp.package
			self.fetchListings(wspace)
		elif self.manufacturer_pn != 'none' and self.manufacturer_pn != 'NULL':
			self.scrape(wspace)

