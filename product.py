import urllib2
from BeautifulSoup import BeautifulSoup, Tag, NavigableString
from octopart import *
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

OCTOPART_API_KEY = '3b6a195e'

VENDOR_DK = "Digi-Key"
VENDOR_FAR = "Farnell"
VENDOR_FUE = "Future"
VENDOR_JAM = "Jameco"
VENDOR_ME = "Mouser"
VENDOR_NEW = "Newark"
VENDOR_SFE = "SparkFun"

# TODO : Set these based on program config file
# This will allow the user to disable vendors they do not purchase from
OCTOPART_EN = True
VENDOR_DK_EN = False
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
	if OCTOPART_EN == True:
		ret = False
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
	errors = {0: 'No offers found on source.', \
			  1: 'No offers found across all vendors.', \
			  2: 'Found no offers with inventory in stock.', \
			  3: 'No vendors enabled.', \
			  4: 'Could not find pricing table on vendor page.'}
	soup_errors = {}
	def __init__(self, source, mfg_pn, error_number):
		self.source = source
		self.mpn = mfg_pn
		
		self.error = error_number
	def __str__(self):
		str = errors[self.error] + ' Source: ' + self.source + ' Manufacturer Part Number: ' + self.mpn
		return repr(str)

class Brand(OctopartBrand):
	'''Database methods for the OctopartBrand class. '''
	@staticmethod
	def new_from_row(row, connection):
		''' Given a brands row from the DB, returns a Brand object. '''
		brand = ProductAttribute(row[0], row[1], row[2])
		return brand
	
	@staticmethod
	def select_by_name(displayname, connection):
		''' Return the Brand of given field displayname. '''
		try:
			cur = connection.cursor()
			
			params = (displayname,)
			for row in cur.execute('SELECT * FROM brands WHERE displayname=?', params):
				brand = Brand.new_from_row(row, connection)
			
		finally:
			cur.close()
			return brand
	
	def __init__(self, id, dispname, homepage):
		OctopartBrand.__init__(id, dispname, homepage)
	
	def show(self):
		''' A detailed print method. '''
		print 'Octopart ID: ', self.id
		print 'Name: ', self.displayname
		print 'Homepage: ', self.homepage_url
	
	def update(self, connection):
		''' Update an existing Brand record in the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.id, self.displayname, self.homepage_url,)
			cur.execute('''UPDATE brands 
			SET id=?1, displayname=?2, homepage_url=?3 
			WHERE id=?1''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		''' Write the Brand to the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.id, self.displayname, self.homepage_url,)
			cur.execute('INSERT OR REPLACE INTO brands VALUES (?,?,?)', params)
				
		finally:
			cur.close()
	
	def delete(self, connection):
		''' Delete the Brand from the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.id,)
			cur.execute('DELETE FROM brands WHERE id=?', params)
			
		finally:
			cur.close()

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
			for row in cur.execute('SELECT * FROM offers WHERE vendor_pn=?', params):
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
			for row in cur.execute('SELECT * FROM offers WHERE manufacturer_pn=?', params):
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
			cur.execute('''UPDATE offers 
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
			cur.execute('INSERT OR REPLACE INTO offers VALUES (?,?,?,?,?,?,?,?,?)', params)
			
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
			cur.execute('DELETE FROM offers WHERE vendor_pn=?', params)
			
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

class ProductAttribute(OctopartPartAttribute):
	'''Database methods for the OctopartPartAttribute class. '''
	
	@staticmethod
	def fetch_unit(fieldname, connection):
		''' Fetch the units table entry for a ProductAttribute of given fieldname. '''
		try:
			cur = connection.cursor()
			
			sql = 'SELECT name, symbol FROM units WHERE name IN (SELECT unit FROM product_attributes WHERE fieldname=?)'
			params = (fieldname,)
			for row in cur.execute(sql, params):
				unit = {'name' : row[0], 'symbol' : row[1]}
		
		finally:
			cur.close()
			return unit
	
	@staticmethod
	def new_from_row(row, connection):
		''' Given a product_attributes row from the DB, returns a ProductAttribute object. '''
		unit = ProductAttribute.fetch_unit(row[0], connection)
		metadata = {'datatype' : row[3], 'unit' : unit}
		attrib = ProductAttribute(row[0], row[1], row[2], metadata)
		return attrib
	
	@staticmethod
	def select_by_fieldname(fieldname, connection):
		''' Return the ProductAttribute of given field fieldname. '''
		try:
			cur = connection.cursor()
			
			params = (fieldname,)
			for row in cur.execute('SELECT * FROM product_attributes WHERE fieldname=?', params):
				attrib = ProductAttribute.new_from_row(row, connection)
			
		finally:
			cur.close()
			return attrib
	
	def __init__(self, fieldname, displayname, type, metadata):
		OctopartPartAttribute.__init__(fieldname, displayname, type, metadata)
	
	def update(self, connection):
		''' Update an existing ProductAttribute record in the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.fieldname, self.displayname, self.type, self.metadata['datatype'], self.metadata['unit'].name,)
			cur.execute('''UPDATE product_attributes 
			SET fieldname=?1, displayname=?2, type=?3, datatype=?4, unit=?5 
			WHERE fieldname=?1''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		''' Write the ProductAttribute to the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.fieldname, self.displayname, self.type, self.metadata['datatype'], self.metadata['unit'].name,)
			cur.execute('INSERT OR REPLACE INTO product_attributes VALUES (?,?,?,?,?)', params)
				
		finally:
			cur.close()
	
	def delete(self, connection):
		''' Delete the ProductAttribute from the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.fieldname,)
			cur.execute('DELETE FROM product_attributes WHERE fieldname=?', params)
			
		finally:
			cur.close()

class Product(OctopartPart):
	''' A physical product, independent of distributor.
	The primary identifying key is the manufacturer PN. '''
	
	@staticmethod
	def new_from_row(row, connection):
		''' Given a product row from the DB, returns a Product object. '''
		part_dict = {}
		part_dict['uid'] = row[0]
		part_dict['mpn'] = row[1]
		part_dict['manufacturer'] = Brand.select_by_name(row[2], connection)
		part_dict['detail_url'] = row[3]
		part_dict['avg_price'] = row[4]
		part_dict['avg_avail'] = row[5]
		part_dict['market_status'] = row[6]
		part_dict['num_suppliers'] = row[7]
		part_dict['num_authsuppliers'] = row[8]
		part_dict['short_description'] = row[9]
		part_dict['category_ids'] = Product.fetch_category_ids(part_dict['mpn'], connection)
		part_dict['images'] = Product.fetch_images(part_dict['mpn'], connection)
		part_dict['datasheets'] = Product.fetch_datasheets(part_dict['mpn'], connection) 
		part_dict['descriptions'] = Product.fetch_descriptions(part_dict['mpn'], connection) 
		part_dict['hyperlinks'] = {'freesample' : row[10], 'evalkit' : row[11], 'manufacturer' : row[12]}
		part_dict['offers'] = Product.fetch_offers(part_dict['mpn'], connection)
		part_dict['specs'] = Product.fetch_specs(part_dict['mpn'], connection)
		prod = Product(part_dict)
		return prod
	
	@staticmethod
	def fetch_category_ids(mpn, connection):
		''' Fetch the list of category IDs for a given MPN. '''
		ids = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT id FROM categories WHERE id IN (SELECT category FROM product_categories WHERE product=?)'
			params = (mpn,)
			for row in cur.execute(sql, params):
				ids.append(row[0])
			
		finally:
			cur.close()
			return ids
	
	@staticmethod
	def fetch_images(mpn, connection):
		''' Fetch the list of images for a given MPN. '''
		images = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT url, url_30px, url_35px, url_55px, url_90px, credit_url, credit_domain FROM product_images WHERE product=?'
			params = (mpn,)
			for row in cur.execute(sql, params):
				result = {}
				result['url'] = row[0]
				result['url_30px'] = row[1]
				result['url_35px'] = row[2]
				result['url_55px'] = row[3]
				result['url_90px'] = row[4]
				result['credit_url'] = row[5]
				result['credit_domain'] = row[6]
				images.append(result)
			
		finally:
			cur.close()
			return images
	
	@staticmethod
	def fetch_datasheets(mpn, connection):
		''' Fetch the list of datasheets for a given MPN. '''
		datasheets = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT url, score FROM datasheets WHERE product=?'
			params = (mpn,)
			for row in cur.execute(sql, params):
				datasheets.append({'url': row[0], 'score' : row[1]})
			
		finally:
			cur.close()
			return datasheets
	
	@staticmethod
	def fetch_descriptions(mpn, connection):
		''' Fetch the list of descriptions for a given MPN. '''
		descriptions = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT txt FROM descriptions WHERE product=?'
			params = (mpn,)
			for row in cur.execute(sql, params):
				descriptions.append(row[0])
			
		finally:
			cur.close()
			return descriptions
	
	@staticmethod
	def fetch_offers(mpn, connection):
		''' Fetch the list of offers for a given MPN. '''
		offers = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT * FROM offers WHERE mpn=? ORDER BY supplier'
			params = (mpn,)
			for row in cur.execute(sql, params):
				# TODO: Revise this line when the Listing class is revamped
				listing = Listing.new_from_row(row, connection)
				offers.append(listing)
			
		finally:
			cur.close()
			return offers
	
	@staticmethod
	def fetch_specs(mpn, connection):
		''' Fetch the list of specs for a given MPN. '''
		specs = []
		attrib = ProductAttribute('', '', 'text', None)
		previous_fieldname = ''
		spec = {}
		try:
			cur = connection.cursor()
			
			sql = 'SELECT attribute, name, value FROM specs WHERE product=? ORDER BY attribute'
			params = (mpn,)
			for attribute, name, value in cur.execute(sql, params):
				if previous_fieldname == '':
					previous_fieldname = attribute
				else:
					if attribute != previous_fieldname:
						specs.append(spec)
						spec = {}
						previous_fieldname = attribute
						attrib = ProductAttribute.select_by_fieldname(attribute, connection)
						spec['attribute'] = attrib
						spec['values'] = [{}]
				spec['values'][0]['name'] = name
				if value is not None:
					spec['values'][0]['value'] = value
			
		finally:
			cur.close()
			return specs
	
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
			for row in cur.execute('SELECT * FROM products WHERE mpn=?', params):
				prods.append(Product.new_from_row(row, connection))
			
		finally:
			cur.close()
			return prods
		
	def __init__(self, part_dict):
		OctopartPart.__init__(self, part_dict)
	
	def show(self, show_offers=False):
		''' A detailed print method. '''
		print 'Octopart UID: ', self.uid, type(self.uid)
		print 'Manufacturer PN: ', self.mpn, type(self.mpn)
		print 'Manufacturer: ', self.manufacturer.show(), type(self.manufacturer.show())
		print 'Detail URL: ', self.detail_url, type(self.detail_url)
		print 'Average price: ', self.avg_price, type(self.avg_price)
		print 'Average available: ', self.avg_avail, type(self.avg_avail)
		print 'Market status: ', self.market_status, type(self.market_status)
		print 'Number of suppliers: ', self.num_suppliers, type(self.num_suppliers)
		print 'Number of authorized suppliers: ', self.num_authsuppliers, type(self.num_authsuppliers)
		print 'Description: ', self.short_description, type(self.short_description)
		print 'Free sample: ', self.hyperlinks['freesample'], type(self.hyperlinks['freesample'])
		print 'Evaluation kit: ', self.hyperlinks['evalkit'], type(self.hyperlinks['evalkit'])
		print 'Manufacturer page: ', self.hyperlinks['manufacturer'], type(self.hyperlinks['manufacturer'])
		if show_offers is True:
			print 'Offers: '
			for offer in self.offers:
				offer.show()
	
	def equals(self, p):
		''' Compares the Product to another Product.'''
		if type(p) != type(self):
			return False
		eq = True
		if self.uid != p.uid:
			eq = False
		if self.mpn != p.mpn:
			eq = False
		elif self.manufacturer != p.manufacturer:
			eq = False
		elif self.detail_url != p.detail_url:
			eq = False
		elif self.avg_price != p.avg_price:
			eq = False
		elif self.avg_avail != p.avg_avail:
			eq = False
		elif self.market_status != p.market_status:
			eq = False
		elif self.num_suppliers != p.num_suppliers:
			eq = False
		elif self.num_authsuppliers != p.num_authsuppliers:
			eq = False
		elif self.short_description != p.short_description:
			eq = False
		elif self.hyperlinks['freesample'] != p.hyperlinks['freesample']:
			eq = False
		elif self.hyperlinks['evalkit'] != p.hyperlinks['evalkit']:
			eq = False
		elif self.hyperlinks['manufacturer'] != p.hyperlinks['manufacturer']:
			eq = False
		return eq
	
	def update(self, connection):
		''' Update an existing Product record in the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.manufacturer, self.mpn, self.datasheet, self.description, 
					self.package, self.mpn,)
			cur.execute('''UPDATE products 
			SET manufacturer=?, mpn=?, datasheet=?, description=?, package=? 
			WHERE mpn=?''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		''' Write the Product to the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.manufacturer, self.mpn, self.datasheet, self.description, self.package,)
			cur.execute('INSERT OR REPLACE INTO products VALUES (?,?,?,?,?)', params)
				
		finally:
			cur.close()
	
	def delete(self, connection):
		''' Delete the Product from the DB. '''
		try:
			cur = connection.cursor()
			
			params = (self.mpn,)
			cur.execute('DELETE FROM products WHERE mpn=?', params)
			
		finally:
			cur.close()
	
	def fetch_listings(self, connection):
		''' Fetch offers dictionary for this Product. 
		Clears and sets the self.offers dictionary directly. '''
		self.offers.clear()
		try:
			cur = connection.cursor()
			
			params = (self.mpn,)
			for row in cur.execute('SELECT * FROM offers WHERE mpn=? ORDER BY vendor', params):
				listing = Listing.new_from_row(row, connection)
				self.offers[listing.key()] = listing
				#print 'Setting offers[%s] = ' % listing.key()
				#listing.show()
			
		finally:
			cur.close()
		
	def best_listing(self, qty):
		''' Return the Listing with the best price for the given order quantity. 
		
		If the "enforce minimum quantities" option is checked in the program config,
		only returns offers where the order quantity meets/exceeds the minimum
		order quantity for the listing.'''
		print 'Entering %s.best_listing(%s)' % (self.mpn, str(qty))
		best = None
		lowest_price = float("inf")
		for listing in self.offers.values():
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
			
			params = (project.name, self.mpn,)
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
				params = (project.name, self.mpn, listing.vendor_pn,)
				cur.execute('INSERT INTO preferred_listings VALUES (NULL,?,?,?)', params) 
			else:
				params = (listing.vendor_pn, project.name, self.mpn,)
				cur.execute('UPDATE preferred_listings SET listing=? WHERE project=? AND product=?', params)
			
		finally:
			cur.close()
	
	def in_stock(self):
		''' Returns true if any Listings have inventory > 0. '''
		stocked = False
		for listing in self.offers.values():
			if listing.inventory > 0:
				stocked = True
				break
	
	def search_octopart(self):
		''' Multi-vendor search using Octopart.
		Uses the Octopart API instead of HTML scraping. '''
		octo = Octopart(OCTOPART_API_KEY)
	
	def scrape_dk(self):
		''' Scrape method for Digikey. '''
		# Clear previous pricing data (in case price break keys change)
		search_url = 'http://search.digikey.com/us/en/products/' + self.mpn
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
				raise ScrapeException(VENDOR_DK, self.mpn, 4)
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
			self.manufacturer = soup.body("th", text="Manufacturer")[0].parent.nextSibling.contents[0].contents[0].string.__str__()
			#print "manufacturer is: %s" % self.manufacturer
			self.mpn = soup.body('th', text="Manufacturer Part Number")[0].parent.nextSibling.contents[0].string.__str__()
			#print "mpn is: %s" % self.mpn
			
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
			self.offers[key] = Listing(VENDOR_DK, vendor_pn, self.mpn, prices, inventory, packaging)
			#v = Listing(VENDOR_DK, vendor_pn, self.mpn, prices, inventory, pkg, reel, cat, fam, ser)
			self.offers[key].category = category
			self.offers[key].family = family
			self.offers[key].series = series
			if "Digi-Reel" in packaging:
				self.offers[key].reel_fee = 7
	
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
		
		search_url = 'http://www.mouser.com/Search/Refine.aspx?Keyword=' + self.mpn
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
				raise ScrapeException(self.scrape.__name__, self.mpn, 3)
		
		else:
			self.offers.clear()
			# Proceed based on source config
			if OCTOPART_EN:
				self.search_octopart()
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
			for listing in self.offers.values():
				if listing.is_in_db(connection):
					listing.update(connection)
				else:
					listing.insert(connection)
			if len(self.offers.values()) == 0:
				raise ScrapeException(self.scrape.__name__, self.mpn, 1)
			if self.in_stock() == False:
				raise ScrapeException(VENDOR_DK, self.mpn, 2)
			
				

	def is_in_db(self, connection):
		''' Check if this Product is in the database. '''
		result = Product.select_by_pn(self.mpn, connection)
		if len(result) == 0:
			return False
		else:
			return True

	def select_or_scrape(self, connection):
		''' Sets the product fields, pulling from the local DB if possible.
		Passing an open connection to this method is recommended. '''	
		if(self.is_in_db(connection)):
			temp = Product.select_by_pn(self.mpn, connection)[0]
			self.manufacturer = temp.manufacturer
			self.mpn = temp.mpn
			self.datasheet = temp.datasheet
			self.description = temp.description
			self.package = temp.package
			self.fetch_listings(connection)
		elif self.mpn != 'none' and self.mpn != 'NULL':
			self.scrape(connection)

