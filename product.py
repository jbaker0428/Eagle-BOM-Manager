import urllib2
from BeautifulSoup import BeautifulSoup, Tag, NavigableString
import shutil
import os
import urlparse
import apsw
from manager import Workspace

def get_filename(url,openUrl):
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
VENDOR_WARN_IF_NONE_EN = True

def no_vendors_enabled():
	''' Return True if all VENDOR_*_EN config vars are False. '''
	ret = True
	if VENDOR_DK_EN == True:
		ret = False
	elif VENDOR_FAR_EN == True:
		ret = False
	elif VENDOR_FUE_EN == True:
		ret = False
	elif VENDOR_JAM_EN == True:
		ret = False
	elif VENDOR_ME_EN == True:
		ret = False
	elif VENDOR_NEW_EN == True:
		ret = False
	elif VENDOR_SFE_EN == True:
		ret = False
	return ret

DOWNLOAD_DATASHEET = False	# TODO : Set these from program config
ENFORCE_MIN_QTY = True

class ScrapeException(Exception):
	''' Raised when something goes wrong scraping. '''
	errors = {0: 'No listings found on source.', \
			  1: 'No listings found across all vendors.', \
			  2: 'Found no listings with inventory in stock.', \
			  3: 'No vendors enabled.', \
			  4: 'Could not find pricing table on vendor page.'}
	soup_errors = {}
	def __init__(self, source, mfg_pn, error_number):
		self.source = source
		self.manufacturer_pn = mfg_pn
		
		self.error = error_number
	def __str__(self):
		str = errors[self.error] + ' Source: ' + self.source + ' Manufacturer Part Number: ' + self.manufacturer_pn
		return repr(str)

class Listing:
	''' A distributor's listing for a Product object. '''
	
	@staticmethod
	def new_from_row(row, connection):
		''' Given a listing row from the DB, returns a Listing object. '''
		listing = Listing(row[0], row[1], row[2], {}, row[3], row[4], row[5], row[6], row[7], row[8])
		listing.fetch_price_breaks(connection)
		return listing
		
	@staticmethod
	def select_by_vendor_pn(pn, connection):
		''' Return the Listing(s) of given source part number in a list. '''
		listings = []
		try:
			cur = connection.cursor()
			
			params = (pn,)
			for row in cur.execute('SELECT * FROM listings WHERE vendor_pn=?', params):
				listings.append(Listing.new_from_row(row, connection))
			
		finally:
			cur.close()
			return listings
	
	@staticmethod
	def select_by_manufacturer_pn(pn, connection):
		''' Return the Listing(s) of given manufacturer part number in a list. '''
		listings = []
		try:
			cur = connection.cursor()
			
			params = (pn,)
			for row in cur.execute('SELECT * FROM listings WHERE manufacturer_pn=?', params):
				listings.append(Listing.new_from_row(row, connection))
			
		finally:
			cur.close()
			return listings
	
	def __init__(self, vend, vendor_pn, manufacturer_pn, prices_dict, inv, pkg, reel=0, cat='NULL', fam='NULL', ser='NULL'):
		self.source = vend
		self.vendor_pn = vendor_pn
		self.manufacturer_pn = manufacturer_pn
		self.prices = prices_dict
		self.inventory = inv
		self.packaging = pkg	# Cut Tape, Tape/Reel, Tray, Tube, etc.
		self.reel_fee = reel	# Flat per-order reeling fee (Digi-reel, MouseReel, etc)
		self.category = cat	# "Capacitors"
		self.family = fam	# "Ceramic"
		self.series = ser	# "C" (TDK series C)
	
	def show(self):
		''' A verbose print method. '''
		print 'Vendor: ', self.source, type(self.source)
		print 'Vendor PN: ', self.vendor_pn, type(self.vendor_pn)
		print 'Product MFG PN: ', self.manufacturer_pn, type(self.manufacturer_pn)
		print 'Prices: ', self.prices.items(), type(self.prices.items())
		print 'Inventory: ', self.inventory, type(self.inventory)
		print 'Packaging: ', self.packaging, type(self.packaging)
		print 'Reel Fee: ', self.reel_fee, type(self.reel_fee)
		print 'Category: ', self.category, type(self.category)
		print 'Family: ', self.family, type(self.family)
		print 'Series: ', self.series, type(self.series)
	
	def show_brief(self):
		''' A less verbose print method for easy debugging. '''
		print self.key()
		print 'Prices: ', self.prices.items()
	
	def equals(self, vp):
		''' Compares the Listing to another Listing.'''
		if type(vp) != type(self):
			return False
		eq = True
		if self.source != vp.source:
			eq = False
		if self.vendor_pn != vp.vendor_pn:
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
		if self.reel_fee != vp.reel_fee:
			eq = False
		if self.category != vp.category:
			eq = False
		if self.family != vp.family:
			eq = False
		if self.series != vp.series:
			eq = False
		return eq
	
	def key(self):
		''' Return a dictionary key as used by the GUI for this Listing.
		Format: key = source + ': ' + vendor_pn + ' (' + packaging + ')' '''
		key = self.source + ': ' + self.vendor_pn + ' (' + self.packaging + ')'
		return key
	
	def update(self, connection):
		''' Update an existing Listing record in the DB. '''
		try:
			cur = connection.cursor()
			
			cur.execute('DELETE FROM pricebreaks WHERE pn=?', (self.vendor_pn,))
			for pb in self.prices.items():
				params = (self.vendor_pn, pb[0], pb[1],)
				cur.execute('INSERT OR REPLACE INTO pricebreaks VALUES (NULL,?,?,?)', params)
			
			params = (self.source, self.vendor_pn, self.manufacturer_pn, self.inventory, self.packaging,
					self.reel_fee, self.category, self.family, self.series, self.vendor_pn,)
			cur.execute('''UPDATE listings 
			SET vendor=?, vendor_pn=?, manufacturer_pn=?, inventory=?, packaging=?, reelfee=?, 
			category=?, family=?, series=? 
			WHERE vendor_pn=?''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		''' Write the Listing to the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.source, self.vendor_pn, self.manufacturer_pn, self.inventory, self.packaging,
					self.reel_fee, self.category, self.family, self.series,)
			cur.execute('INSERT OR REPLACE INTO listings VALUES (?,?,?,?,?,?,?,?,?)', params)
			
			cur.execute('DELETE FROM pricebreaks WHERE pn=?', (self.vendor_pn,))
			for pb in self.prices.items():
				params = (self.vendor_pn, pb[0], pb[1],)
				cur.execute('INSERT OR REPLACE INTO pricebreaks VALUES (NULL,?,?,?)', params)
		finally:
			cur.close()
	
	def delete(self, connection):
		''' Delete the Listing from the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.vendor_pn,)
			cur.execute('DELETE FROM listings WHERE vendor_pn=?', params)
			
		finally:
			cur.close()
	
	def is_in_db(self, connection):
		''' Check if this Listing is in the database. '''
		result = Listing.select_by_vendor_pn(self.vendor_pn, connection)
		if len(result) == 0:
			return False
		else:
			return True
	
	def fetch_price_breaks(self, connection):
		''' Fetch price breaks dictionary for this Listing. 
		Clears and sets the self.prices dictionary directly. '''
		#print 'self.prices: ', type(self.prices), self.prices
		self.prices.clear()
		try:
			cur = connection.cursor()
			
			params = (self.vendor_pn,)
			for row in cur.execute('SELECT qty, unit FROM pricebreaks WHERE pn=? ORDER BY qty', params):
				self.prices[row[0]] = row[1]

		finally:
			cur.close()
		
	def get_price_break(self, qty):
		''' Returns the (price break, unit price) list pair for the given purchase quantity.
		If qty is below the lowest break, the lowest is returned.
		TODO : Raise some kind of error/warning if not ordering enough PCBs to make the lowest break.'''
		breaks = sorted(self.prices.keys())
		#breaks.sort()
		if breaks[0] > qty:
			print "Warning: Purchase quantity is below minimum!"
			if ENFORCE_MIN_QTY:
				return None
			else:
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
	def new_from_row(row, connection):
		''' Given a product row from the DB, returns a Product object. '''
		prod = Product(row[0], row[1], row[2], row[3], row[4])
		prod.fetch_listings(connection)
		return prod
	
	@staticmethod
	def select_all(connection):
		''' Return the entire product table except the 'NULL' placeholder row. '''
		prods = []
		try:
			cur = connection.cursor()
			
			for row in cur.execute('SELECT * FROM products'):
				if row[1] == 'NULL':
					continue
				else:
					prods.append(Product.new_from_row(row, connection))
			
		finally:
			cur.close()
			return prods
	
	@staticmethod
	def select_by_pn(pn, connection):
		''' Return the Product(s) of given part number in a list. '''
		prods = []
		try:
			cur = connection.cursor()
			
			params = (pn,)
			for row in cur.execute('SELECT * FROM products WHERE manufacturer_pn=?', params):
				prods.append(Product.new_from_row(row, connection))
			
		finally:
			cur.close()
			return prods
		
	def __init__(self, mfg, manufacturer_pn, dsheet='NULL', desc='NULL', pkg='NULL'):
		self.manufacturer = mfg
		self.manufacturer_pn = manufacturer_pn
		self.datasheet = dsheet
		self.description = desc
		self.package = pkg
		self.listings = {}	# Key is key = source + ': ' + vendor_pn + ' (' + packaging + ')'
	
	def show(self, show_listings=False):
		''' A simple print method. '''
		print 'Manufacturer: ', self.manufacturer, type(self.manufacturer)
		print 'Manufacturer PN: ', self.manufacturer_pn, type(self.manufacturer_pn)
		print 'Datasheet: ', self.datasheet, type(self.datasheet)
		print 'Description: ', self.description, type(self.description)
		print 'Package: ', self.package, type(self.package)
		if show_listings is True:
			print 'Listings:'
			for listing in self.listings.items():
				print "\nListing key: ", listing[0]
				listing[1].show()
	
	def equals(self, p):
		''' Compares the Product to another Product.'''
		if type(p) != type(self):
			return False
		eq = True
		if self.manufacturer != p.manufacturer:
			eq = False
		elif self.manufacturer_pn != p.manufacturer_pn:
			eq = False
		elif self.datasheet != p.datasheet:
			eq = False
		elif self.description != p.description:
			eq = False
		elif self.package != p.package:
			eq = False
		for k in self.listings.keys():
			if k not in p.listings.keys():
				eq = False
			else:
				if self.listings[k].equals(p.listings[k]) == False:
					eq = False
		for k in p.listings.keys():
			if k not in self.listings.keys():
				eq = False
		return eq
	
	def update(self, connection):
		''' Update an existing Product record in the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.manufacturer, self.manufacturer_pn, self.datasheet, self.description, 
					self.package, self.manufacturer_pn,)
			cur.execute('''UPDATE products 
			SET manufacturer=?, manufacturer_pn=?, datasheet=?, description=?, package=? 
			WHERE manufacturer_pn=?''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		''' Write the Product to the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.manufacturer, self.manufacturer_pn, self.datasheet, self.description, self.package,)
			cur.execute('INSERT OR REPLACE INTO products VALUES (?,?,?,?,?)', params)
				
		finally:
			cur.close()
	
	def delete(self, connection):
		''' Delete the Product from the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.manufacturer_pn,)
			cur.execute('DELETE FROM products WHERE manufacturer_pn=?', params)
			
		finally:
			cur.close()
	
	def fetch_listings(self, connection):
		''' Fetch listings dictionary for this Product. 
		Clears and sets the self.listings dictionary directly. '''
		self.listings.clear()
		try:
			cur = connection.cursor()
			
			params = (self.manufacturer_pn,)
			for row in cur.execute('SELECT * FROM listings WHERE manufacturer_pn=? ORDER BY vendor', params):
				listing = Listing.new_from_row(row, connection)
				self.listings[listing.key()] = listing
				#print 'Setting listings[%s] = ' % listing.key()
				#listing.show()
			
		finally:
			cur.close()
		
	def best_listing(self, qty):
		''' Return the Listing with the best price for the given order quantity. 
		
		If the "enforce minimum quantities" option is checked in the program config,
		only returns listings where the order quantity meets/exceeds the minimum
		order quantity for the listing.'''
		print 'Entering %s.best_listing(%s)' % (self.manufacturer_pn, str(qty))
		best = None
		lowest_price = float("inf")
		for listing in self.listings.values():
			listing.show_brief()
			price_break = listing.get_price_break(qty)
			print 'price_break from listing.get_price_break( %s ) = ' % str(qty)
			print price_break
			if price_break == None or (price_break[0] > qty and ENFORCE_MIN_QTY):
				pass
			else:
				if (price_break[1]*qty) + listing.reel_fee < lowest_price:
					lowest_price = (price_break[1]*qty) + listing.reel_fee
					best = listing
					print 'Set best listing: ', best.show_brief()
		return best
	
	def get_preferred_listing(self, project, connection):
		'''Get a project's preferred Listing for this Product. '''
		try:
			listing = None
			cur = connection.cursor()
			
			params = (project.name, self.manufacturer_pn,)
			rows = list(cur.execute('SELECT listing FROM preferred_listings WHERE project=? AND product=?', params))
			if len(rows) > 0:
				listing = Listing.select_by_vendor_pn(rows[0][0], connection)[0]
			
		finally:
			cur.close()
			return listing
	
	def set_preferred_listing(self, project, listing, connection):
		'''Set a project's preferred Listing for this Product. '''
		try:
			cur = connection.cursor()
			current_listing = self.get_preferred_listing(project, connection)
			if current_listing is None:
				params = (project.name, self.manufacturer_pn, listing.vendor_pn,)
				cur.execute('INSERT INTO preferred_listings VALUES (NULL,?,?,?)', params) 
			else:
				params = (listing.vendor_pn, project.name, self.manufacturer_pn,)
				cur.execute('UPDATE preferred_listings SET listing=? WHERE project=? AND product=?', params)
			
		finally:
			cur.close()
	
	def in_stock(self):
		''' Returns true if any Listings have inventory > 0. '''
		stocked = False
		for listing in self.listings.values():
			if listing.inventory > 0:
				stocked = True
				break
	
	def scrape_dk(self):
		''' Scrape method for Digikey. '''
		# Clear previous pricing data (in case price break keys change)
		search_url = 'http://search.digikey.com/us/en/products/' + self.manufacturer_pn
		search_page = urllib2.urlopen(search_url)
		search_soup = BeautifulSoup(search_page)
		
		# Create a list of product URLs from the search page
		prod_urls = []
		search_table = search_soup.body('table', id="productTable")
		if len(search_table) > 0:
			product_table = search_table[0]
			#print 'product_table: \n', product_table
			#print 'product_table.contents: \n', product_table.contents
			
			# Find tbody tag in table
			tbody_tag = product_table.find('tbody')
			#print 'tbody: \n', type(tbody_tag), tbody_tag
			#print 'tbody.contents: \n', type(tbody_tag.contents), tbody_tag.contents
			#print 'tbody.contents[0]: \n', type(tbody_tag.contents[0]), tbody_tag.contents[0]
			prod_rows = tbody_tag.findAll('tr')
			#print 'prod_rows: \n', type(prod_rows), prod_rows
			for row in prod_rows:
				#print "Search row in prod_rows: ", row
				anchor = row.find('a')
				# DK uses a relative path for these links
				prod_urls.append('http://search.digikey.com' + anchor['href'])
				#print 'Adding URL: ', 'http://search.digikey.com' + anchor['href']
		
		for url in prod_urls:
		
			page = urllib2.urlopen(url)
			soup = BeautifulSoup(page)
			#print "URL: %s" % url
			# Get prices
			prices = {}
			price_table = soup.body('table', id="pricing")
			#print 'price_table: ', type(price_table), price_table
			if len(price_table) == 0:
				raise ScrapeException(VENDOR_DK, self.manufacturer_pn, 4)
			# price_table.contents[x] should be the tr tags...
			for tag in price_table:
				#print 'tag: ', type(tag), tag
				for row in tag:
					#print 'row: ', type(row), row
					# row.contents should be td Tags... except the first!
					if row == '\n':
						pass
					elif row.contents[0].name == 'th':
						pass
						#print "Found row.name == th"
					else:
						new_break_str = row.contents[0].string
						# Remove commas
						if new_break_str.isdigit() == False:
							new_break_str = new_break_str.replace(",", "")
						#print "new_break_str is: %s" % new_break_str					
						new_break = int(new_break_str)
						new_unit_price = float(row.contents[1].string)
						prices[new_break] = new_unit_price
						#print 'Adding break/price to pricing dict: ', (new_break, new_unit_price)
					
			# Get inventory
			# If the item is out of stock, the <td> that normally holds the
			# quantity available will have a text input box that we need to
			# watch out for
			inv_soup = soup.body('td', id="quantityavailable")
			#print 'inv_soup: ', type(inv_soup), inv_soup
			#print "Length of form search results: %s" % len(inv_soup[0].findAll('form'))
			if len(inv_soup[0].findAll('form')) > 0:
				inventory = 0
			
			else:
				inv_str = inv_soup[0].contents[0]
				#print 'inv_str: ', type(inv_str), inv_str
				if inv_str.isdigit() == False:
					inv_str = inv_str.replace(",", "")
				inventory = int(inv_str)
				#print 'inventory: ', type(inventory), inventory
			
			vendor_pn = soup.body("th", text="Digi-Key Part Number")[0].parent.nextSibling.contents[0].string.__str__()
			# Get manufacturer and PN
			self.manufacturer = self.manufacturer_pn = soup.body("th", text="Manufacturer")[0].parent.nextSibling.contents[0].contents[0].string.__str__()
			#print "manufacturer is: %s" % self.manufacturer
			self.manufacturer_pn = soup.body('th', text="Manufacturer Part Number")[0].parent.nextSibling.contents[0].string.__str__()
			#print "manufacturer_pn is: %s" % self.manufacturer_pn
			
			# Get datasheet filename and download
			datasheet_soup = soup.body('th', text="Datasheets")[0].parent.nextSibling
			datasheet_anchor = datasheet_soup.findAllNext('a')[0]
			#print "datasheet_soup is: %s" % datasheet_soup
			#print "datasheet_anchor is: %s" % datasheet_anchor
			self.datasheet_url = datasheet_anchor['href']
			#print "self.datasheet_url is: %s" % self.datasheet_url
			
			row = urllib2.urlopen(urllib2.Request(self.datasheet_url))
			try:
				file_name = get_filename(url,row)
				self.datasheet = file_name;
				# TODO: Do not re-download if already saved
				if DOWNLOAD_DATASHEET:
					with open(file_name, 'wb') as f:
						shutil.copyfileobj(row,f)
			finally:
				row.close()
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
			
			packaging_soup = soup.body('th', text="Packaging")[0].parent.parent.nextSibling.contents[0]
			#print "packaging_soup: ", type(packaging_soup), packaging_soup
			if type(packaging_soup) == NavigableString:
				packaging = packaging_soup.string.__str__()
				#print "packaging (from text): ", type(packaging), packaging
			elif type(packaging_soup) == Tag:
				packaging = packaging_soup.contents[0].string.__str__()
				#print "packaging (from link): ", type(packaging), packaging
			else:
				print 'Error: DK Packaging scrape failure!'
			if "Digi-Reel" in packaging:
				packaging = "Digi-Reel"	# Remove Restricted symbol
			key = VENDOR_DK + ': ' + vendor_pn + ' (' + packaging + ')'
			self.listings[key] = Listing(VENDOR_DK, vendor_pn, self.manufacturer_pn, prices, inventory, packaging)
			#v = Listing(VENDOR_DK, vendor_pn, self.manufacturer_pn, prices, inventory, pkg, reel, cat, fam, ser)
			self.listings[key].category = category
			self.listings[key].family = family
			self.listings[key].series = series
			if "Digi-Reel" in packaging:
				self.listings[key].reel_fee = 7
	
	def scrape_far(self):
		''' Scrape method for Farnell. '''
		raise NotImplementedError("Farnell scraping not yet implemented!")
	
	def scrape_fue(self):
		''' Scrape method for Future Electronics. '''
		raise NotImplementedError("Future scraping not yet implemented!")
		
	def scrape_jam(self):
		''' Scrape method for Jameco. '''
		raise NotImplementedError("Jameco scraping not yet implemented!")
		
	def scrape_me(self):
		''' Scrape method for Mouser Electronics. '''
		raise NotImplementedError("Mouser scraping not yet implemented!")
		
		search_url = 'http://www.mouser.com/Search/Refine.aspx?Keyword=' + self.manufacturer_pn
		search_page = urllib2.urlopen(search_url)
		search_soup = BeautifulSoup(search_page)
		
		# Create a list of product URLs from the search page
		prod_urls = []
		# Check "Mouser Part #" column in table -- ignore any rows where that cell says "Not Assigned"
	
	def scrape_new(self):
		''' Scrape method for Newark. '''
		raise NotImplementedError("Newark scraping not yet implemented!")
	
	def scrape_sfe(self):
		''' Scrape method for Sparkfun. '''	
		raise NotImplementedError("SparkFun scraping not yet implemented!")
		# Clear previous pricing data (in case price break keys change)
		self.prices.clear()
		
		# The URL contains the numeric portion of the part number, minus any leading zeroes
		url = "http://www.sparkfun.com/products/" + str(int(self.pn.split("-")))
		page = urllib2.urlopen(url)
		soup = BeautifulSoup(page)
			
	def scrape(self, connection):
		''' Scrape each source page to refresh product pricing info. '''
		if no_vendors_enabled() == True:
			if VENDOR_WARN_IF_NONE_EN == True:
				raise ScrapeException(self.scrape.__name__, self.manufacturer_pn, 3)
		
		else:
			self.listings.clear()
			# Proceed based on source config
			if VENDOR_DK_EN:
				try:
					self.scrape_dk()
				except ScrapeException as e:
					if e.error == 0:
						pass
			if VENDOR_FAR_EN:
				self.scrape_far()
			if VENDOR_FUE_EN:
				self.scrape_fue()
			if VENDOR_JAM_EN:
				self.scrape_jam()
			if VENDOR_ME_EN:
				self.scrape_me()
			if VENDOR_NEW_EN:
				self.scrape_new()
			if VENDOR_SFE_EN:
				self.scrape_sfe()
			
			#print 'Writing the following Product to DB: \n'
			#self.show()
			if self.is_in_db(connection):
				self.update(connection)
			else:
				self.insert(connection)
			for listing in self.listings.values():
				if listing.is_in_db(connection):
					listing.update(connection)
				else:
					listing.insert(connection)
			if len(self.listings.values()) == 0:
				raise ScrapeException(self.scrape.__name__, self.manufacturer_pn, 1)
			if self.in_stock() == False:
				raise ScrapeException(VENDOR_DK, self.manufacturer_pn, 2)
			
				

	def is_in_db(self, connection):
		''' Check if this Product is in the database. '''
		result = Product.select_by_pn(self.manufacturer_pn, connection)
		if len(result) == 0:
			return False
		else:
			return True

	def select_or_scrape(self, connection):
		''' Sets the product fields, pulling from the local DB if possible.
		Passing an open connection to this method is recommended. '''	
		if(self.is_in_db(connection)):
			temp = Product.select_by_pn(self.manufacturer_pn, connection)[0]
			self.manufacturer = temp.manufacturer
			self.manufacturer_pn = temp.manufacturer_pn
			self.datasheet = temp.datasheet
			self.description = temp.description
			self.package = temp.package
			self.fetch_listings(connection)
		elif self.manufacturer_pn != 'none' and self.manufacturer_pn != 'NULL':
			self.scrape(connection)

