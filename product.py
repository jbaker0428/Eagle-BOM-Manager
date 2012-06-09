import urllib2
import datetime
import shutil
import os
import urlparse

import apsw
from BeautifulSoup import BeautifulSoup, Tag, NavigableString
from octopart import *

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
VENDOR_FUE = "Future Electronics"
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
	"""Return True if all VENDOR_*_EN config vars are False."""
	
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
	
	"""Raised when something goes wrong scraping."""
	
	errors = {0: 'No offers found on supplier.', \
			  1: 'No offers found across all vendors.', \
			  2: 'Found no offers with inventory in stock.', \
			  3: 'No suppliers enabled.', \
			  4: 'Could not find pricing table on supplier page.'}
	soup_errors = {}
	def __init__(self, supplier, mpn, error_number):
		self.supplier = supplier
		self.mpn = mpn
		
		self.error = error_number
	def __str__(self):
		str = errors[self.error] + ' Source: ' + self.supplier + ' Manufacturer Part Number: ' + self.mpn
		return repr(str)

class Brand(OctopartBrand):
	
	"""Database methods for the OctopartBrand class."""
	
	@staticmethod
	def new_from_row(row, connection):
		"""Given a brands row from the DB, returns a Brand object."""
		
		brand = Brand(row[0], row[1], row[2])
		return brand
	
	@staticmethod
	def promote_octopart_brand(octo_brand):
		"""Given an OctopartBrand instance, returns a corresponding Brand instance."""
		
		return Brand(octo_brand.id, octo_brand.displayname, octo_brand.homepage_url)
	
	@staticmethod
	def select_by_name(displayname, connection):
		"""Return the Brand of given displayname."""
		
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
		"""A detailed print method."""
		
		print 'Octopart ID: ', self.id
		print 'Name: ', self.displayname
		print 'Homepage: ', self.homepage_url
	
	def update(self, connection):
		"""Update an existing Brand record in the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.id, self.displayname, self.homepage_url,)
			cur.execute('''UPDATE brands 
			SET id=?1, displayname=?2, homepage_url=?3 
			WHERE id=?1''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		"""Write the Brand to the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.id, self.displayname, self.homepage_url,)
			cur.execute('INSERT OR REPLACE INTO brands VALUES (?,?,?)', params)
				
		finally:
			cur.close()
	
	def delete(self, connection):
		"""Delete the Brand from the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.id,)
			cur.execute('DELETE FROM brands WHERE id=?', params)
			
		finally:
			cur.close()

class Category(OctopartCategory):
	
	"""Database methods for the OctopartCategory class."""
	
	@staticmethod
	def new_from_row(row, connection, get_ancestors=True):
		"""Given a categories row from the DB, returns a Category object."""
		
		images = Category.fetch_images(row[0], connection)
		children_ids = Category.fetch_children_ids(row[0], connection)
		ancestor_ids = Category.fetch_ancestor_ids(row[1], connection)
		if get_ancestors is True:
			ancestors = Category.fetch_ancestors(row[1], connection)
		else:
			ancestors = None
		category = Category(row[0], row[1], row[2], images, children_ids, ancestor_ids, ancestors, row[3])
		return category
	
	@staticmethod
	def promote_octopart_category(oc):
		"""Given an OctopartCategory instance, returns a corresponding Category instance."""
		
		cat = Category(oc.id, oc.parent_id, oc.nodename, oc.images, oc.children_ids, oc.ancestor_ids, oc.ancestors, oc.num_parts)
		for ancestor in cat.ancestors:
			ancestor = Category.promote_octopart_category(ancestor)
		return cat
	
	@staticmethod
	def fetch_images(id, connection):
		"""Fetch the list of images for the Category of given ID."""
		
		images = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT url, url_40px, url_50px FROM category_images WHERE category=?'
			params = (id,)
			for row in cur.execute(sql, params):
				result = {}
				result['url'] = row[0]
				result['url_40px'] = row[1]
				result['url_50px'] = row[2]
				images.append(result)
			
		finally:
			cur.close()
			return images
	
	@staticmethod
	def fetch_children_ids(id, connection):
		"""Fetch all immediate children IDs of the Category of given ID."""
		
		ids = []
		try:
			cur = connection.cursor()
			
			params = (id,)
			for row in cur.execute('SELECT id FROM categories WHERE parent_id=?', params):
				ids.append(row[0])
			
		finally:
			cur.close()
			return ids
	
	@staticmethod
	def fetch_ancestor_ids(parent_id, connection):
		"""Fetch all ancestor IDs of the Category of given parent ID."""
		
		ids = []
		try:
			cur = connection.cursor()
			
			params = (parent_id,)
			for row in cur.execute('SELECT parent_id FROM categories WHERE id=?', params):
				if row[0] is not None:
					ids.append(row[0])
					ids.append(Category.fetch_ancestor_ids(row[0], connection))
			# The API docs specify "immediate parent is last" sorting
			ids.reverse()
			
		finally:
			cur.close()
			return ids
	
	@staticmethod
	def fetch_ancestors(parent_id, connection):
		"""Fetch all ancestors of the Category of given parent ID."""
		
		ancestor_ids = Category.fetch_ancestor_ids(parent_id, connection)
		ancestors = []
		try:
			cur = connection.cursor()
			
			for id in ancestor_ids:
				# ancestor_ids is tree root first
				params = (id,)
				for row in cur.execute('SELECT * FROM categories WHERE id=?', params):
					ancestor = Category.new_from_row(row, connection, False)
					ancestor.ancestors.append(ancestors)
					ancestors.append(ancestor)
			
		finally:
			cur.close()
			return ancestors
	
	@staticmethod
	def select_by_id(id, connection):
		"""Return the Category of given ID."""
		
		try:
			cur = connection.cursor()
			
			params = (id,)
			for row in cur.execute('SELECT * FROM categories WHERE id=?', params):
				category = Category.new_from_row(row, connection)
			
		finally:
			cur.close()
			return category
	
	@staticmethod
	def select_by_name(nodename, connection):
		"""Return the Category of given node name."""
		
		try:
			cur = connection.cursor()
			
			params = (nodename,)
			for row in cur.execute('SELECT * FROM categories WHERE nodename=?', params):
				category = Category.new_from_row(row, connection)
			
		finally:
			cur.close()
			return category
	
	def __init__(self, id, parent_id, nodename, images, children_ids, ancestor_ids, ancestors, num_parts):
		OctopartCategory.__init__(id, parent_id, nodename, images, children_ids, ancestor_ids, ancestors, num_parts)
	
	def show(self):
		"""A detailed print method."""
		
		print 'Octopart ID: ', self.id
		print 'Parent ID: ', self.parent_id
		print 'Name: ', self.nodename
		print 'Images: ', self.images
		print 'Children IDs: ', self.children_ids
		print 'Ancestor IDs: ', self.ancestor_ids
		print 'Number of parts: ', self.num_parts
	
	def update(self, connection):
		"""Update an existing Category record in the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.id, self.parent_id, self.nodename, self.num_parts,)
			cur.execute('''UPDATE categories 
			SET id=?1, parent_id=?2, nodename=?3, num_parts=?4 
			WHERE id=?1''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		"""Write the Category to the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.id, self.parent_id, self.nodename, self.num_parts,)
			cur.execute('INSERT OR REPLACE INTO categories VALUES (?,?,?,?)', params)
				
		finally:
			cur.close()
	
	def delete(self, connection):
		"""Delete the Category from the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.id,)
			cur.execute('DELETE FROM categories WHERE id=?', params)
			
		finally:
			cur.close()

class Offer(object):
	
	"""A supplier's offer for a Product object."""
	
	# Known flat reeling fees
	REEL_FEES = {"Digi-Reel" : 7, "MouseReel" : 7}
	
	@staticmethod
	def new_from_octopart(mpn, odict):
		"""Return an Offer from an Octopart API JSON dictionary.
		
		@param mpn: Manufacturer part number string of parent Product instance.
		@param odict: JSON dictionary of offer data from Octopart.
		"""
		
		supplier = Brand.promote_octopart_brand(odict['supplier'])
		if 'packaging' in odict and odict['packaging'] is not None:
			packaging = odict['packaging']
		else:
			packaging = ''
		
		if packaging in Offer.REEL_FEES:
			reel_fee = Offer.REEL_FEES[packaging]
		else:
			reel_fee = 0
		if 'is_brokered' in odict:
			brokered = odict['is_brokered']
		else:
			brokered = False
		
		if 'update_ts' in odict:
			ts = odict['update_ts']
		else:
			ts = None
		
		offer = Offer(mpn, odict['sku'], supplier, odict['avail'], odict['is_authorized'], \
					brokered, odict['clickthrough_url'], odict['buynow_url'], \
					odict['sendrfq_url'], packaging, reel_fee, ts, odict['prices'])
		return offer
	
	@staticmethod
	def new_from_row(row, connection):
		"""Given a offer row from the DB, returns a Offer object."""
		
		offer = Offer(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11], [])
		offer.fetch_price_breaks(connection)
		return offer
		
	@staticmethod
	def select_by_sku(pn, connection):
		"""Return the Offer(s) of given supplier part number in a list."""
		
		offers = []
		try:
			cur = connection.cursor()
			
			params = (pn,)
			for row in cur.execute('SELECT * FROM offers WHERE sku=?', params):
				offers.append(Offer.new_from_row(row, connection))
			
		finally:
			cur.close()
			return offers
	
	@staticmethod
	def select_by_manufacturer_pn(pn, connection):
		"""Return the Offer(s) of given manufacturer part number in a list."""
		
		offers = []
		try:
			cur = connection.cursor()
			
			params = (pn,)
			for row in cur.execute('SELECT * FROM offers WHERE manufacturer_pn=?', params):
				offers.append(Offer.new_from_row(row, connection))
			
		finally:
			cur.close()
			return offers
	
	def __init__(self, manufacturer_pn, sku, supplier, inv, authorized, brokered, clickthrough, buynow, rfq, pkg, reel, updated, prices):
		self.manufacturer_pn = manufacturer_pn
		self.sku = sku
		self.supplier = supplier	# A Brand instance
		""" 
		From the Octopart API documentation regarding special inventory values: 
		-1: "non-stocked"
		-2: "yes"
		-3: "unknown"
		-4: "RFQ"  
		"""
		self.inventory = inv
		self.is_authorized = authorized	# Boolean
		self.is_brokered = brokered	# Boolean
		self.clickthrough_url = clickthrough
		self.buynow_url = buynow
		self.sendrfq_url = rfq
		self.packaging = pkg	# Cut Tape, Tape/Reel, Tray, Tube, etc.
		self.reel_fee = reel	# Flat per-order reeling fee (Digi-reel, MouseReel, etc)
		self.update_ts = updated	# A datetime object (UTC)
		"""
		Old prices format: prices[break] = unit_price
		New format: Sorted list of (break, unit price, currency) tuples 
		"""
		self.prices = prices
	
	def show(self):
		"""A verbose print method.
		
		Mainly intended for debugging purposes.
		"""
		
		print 'Manufacturer PN: ', self.manufacturer_pn, type(self.manufacturer_pn)
		print 'SKU: ', self.sku, type(self.sku)
		print 'Supplier: ', self.supplier, type(self.supplier)
		print 'Inventory: ', self.inventory, type(self.inventory)
		print 'Authorized: ', self.is_authorized, type(self.is_authorized)
		print 'Brokered: ', self.is_brokered, type(self.is_brokered)
		print 'Clickthrough URL: ', self.clickthrough_url, type(self.clickthrough_url)
		print 'Buy Now URL: ', self.buynow_url, type(self.buynow_url)
		print 'Send RFQ URL: ', self.sendrfq_url, type(self.sendrfq_url)
		print 'Packaging: ', self.packaging, type(self.packaging)
		print 'Reel Fee: ', self.reel_fee, type(self.reel_fee)
		print 'Data updated: ', self.update_ts.isoformat(), type(self.update_ts)
		print 'Prices: ', self.prices, type(self.prices)
	
	def show_brief(self):
		"""A less verbose print method for debugging."""
		
		print self.key()
		print 'Prices: ', self.prices.items()
	
	def equals(self, offer):
		"""Compares the Offer to another Offer."""
		
		if type(offer) != type(self):
			return False
		eq = True
		if self.manufacturer_pn != offer.manufacturer_pn:
			eq = False
		if self.sku != offer.sku:
			eq = False
		if self.supplier != offer.supplier:
			eq = False
		if self.inventory != offer.inventory:
			eq = False
		if self.is_authorized != offer.is_authorized:
			eq = False
		if self.is_brokered != offer.is_brokered:
			eq = False
		if self.clickthrough_url != offer.clickthrough_url:
			eq = False
		if self.buynow_url != offer.buynow_url:
			eq = False
		if self.sendrfq_url != offer.sendrfq_url:
			eq = False
		if self.packaging != offer.packaging:
			eq = False
		if self.reel_fee != offer.reel_fee:
			eq = False
		if self.update_ts != offer.update_ts:
			eq = False
		for p in self.prices:
			if p not in offer.prices:
				eq = False
		return eq
	
	def __eq__(self, o):
		return self.equals(o)
	
	def key(self):
		"""Return a dictionary key as used by the GUI for this Offer.
		
		Format: key = 'supplier: sku (packaging)'.
		"""
		
		key = self.supplier + ': ' + self.sku + ' (' + self.packaging + ')'
		return key
	
	def update(self, connection):
		"""Update an existing Offer record in the DB."""
		
		try:
			cur = connection.cursor()
			
			cur.execute('DELETE FROM prices WHERE sku=?', (self.sku,))
			for price_break, unit_price, currency in self.prices:
				params = (self.sku, price_break, unit_price, currency,)
				cur.execute('INSERT INTO prices VALUES (NULL,?,?,?,?)', params)
			
			update_str = self.update_ts.strftime('%Y-%m-%d %H:%M:%S')
			params = (self.manufacturer_pn, self.supplier, self.inventory, self.is_authorized, \
					self.is_brokered, self.clickthrough_url, self.buynow_url, self.sendrfq_url, \
					self.packaging, self.reel_fee, update_str, self.sku,)
			cur.execute('''UPDATE offers 
			SET mpn=?, supplier=?, inventory=?, is_authorized=?, is_brokered=?, 
			clickthrough_url=?, buynow_url=?, sendrfq_url=?, packaging=?, reelfee=?, update_ts=? 
			WHERE sku=?''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		"""Write the Offer to the DB."""
		
		try:
			cur = connection.cursor()
			
			self.delete(connection)	# Cascade-delete any old price data
			
			update_str = self.update_ts.strftime('%Y-%m-%d %H:%M:%S')
			params = (self.manufacturer_pn, self.sku, self.supplier, self.inventory, self.is_authorized, \
					self.is_brokered, self.clickthrough_url, self.buynow_url, self.sendrfq_url, \
					self.packaging, self.reel_fee, update_str,)
			cur.execute('INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', params)
			
			for price_break, unit_price, currency in self.prices:
				params = (self.sku, price_break, unit_price, currency,)
				cur.execute('INSERT INTO prices VALUES (NULL,?,?,?,?)', params)
		finally:
			cur.close()
	
	def delete(self, connection):
		"""Delete the Offer from the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.sku,)
			cur.execute('DELETE FROM offers WHERE sku=?', params)
			
		finally:
			cur.close()
	
	def is_in_db(self, connection):
		"""Check if this Offer is in the database."""
		
		result = Offer.select_by_sku(self.sku, connection)
		if len(result) == 0:
			return False
		else:
			return True
	
	def fetch_price_breaks(self, connection, currency=None):
		"""Fetch tne price breaks tuples list for this Offer. 
		
		Clears and sets the self.prices list directly. 
		@param currency: Optional sequence of currency strings to filter by.
		If no currency filter strings are passed, fetches price breaks for all available currencies.
		"""
		
		self.prices.clear()
		try:
			cur = connection.cursor()
			
			if currency is None:
				sql = 'SELECT qty, unit, currency FROM prices WHERE sku=? ORDER BY currency ASC, qty ASC'
				params = (self.sku,)
			
			else:
				def currency_filter_expr(param_number):
					return 'currency=?%s' % param_number
				
				filter_args = {1: self.sku}
				currency_exprs = []
				for filter in currency:
					greatest_param = max(filter_args.keys())
					new_key = greatest_param + 1
					filter_args[new_key] = filter
					currency_exprs.append(currency_filter_expr(new_key))
				
				full_currency_expr = ' AND (' + ' OR '.join(currency_exprs) + ') '
					
				sql = 'SELECT qty, unit, currency FROM prices WHERE sku=?1' + full_currency_expr + 'ORDER BY currency ASC, qty ASC'
				params = []
				for key in sorted(filter_args.keys()):
					params.append(filter_args[key])
				params = tuple(params)
				
			for row in cur.execute(sql, params):
				self.prices.append(row)

		finally:
			cur.close()
		
	def get_price_break(self, qty, currency):
		"""Returns the prices tuple for the given purchase quantity and currency.
		
		If qty is below the lowest break, the lowest is returned.
		TODO : Raise some kind of error/warning if not ordering enough PCBs to make the lowest break.
		"""
		
		if self.prices[0][0] > qty:
			print "Warning: Purchase quantity is below minimum!"
			if ENFORCE_MIN_QTY:
				return None
			else:
				return self.prices[0]
			# TODO : GUI warning, maybe by raising an exception?
		for i in range(len(self.prices)):
			if self.prices[i][0] == qty or self.prices[i][0] == max(self.prices):
				return self.prices[i]
			elif self.prices[i][0] > qty:
				return self.prices[i-1]

class ProductAttribute(OctopartPartAttribute):
	
	"""Database methods for the OctopartPartAttribute class."""
	
	@staticmethod
	def fetch_unit(fieldname, connection):
		"""Fetch the units table entry for a ProductAttribute of given fieldname."""
		
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
		"""Given a product_attributes row from the DB, returns a ProductAttribute object."""
		
		unit = ProductAttribute.fetch_unit(row[0], connection)
		metadata = {'datatype' : row[3], 'unit' : unit}
		attrib = ProductAttribute(row[0], row[1], row[2], metadata)
		return attrib
	
	@staticmethod
	def promote_octopart_part_attribute(attrib):
		"""Given an OctopartPartAttribute instance, returns a corresponding ProductAttribute instance."""
		
		return ProductAttribute(attrib.fieldname, attrib.displayname, attrib.type, attrib.metadata)
	
	@staticmethod
	def select_by_fieldname(fieldname, connection):
		"""Return the ProductAttribute of given field fieldname."""
		
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
		"""Update an existing ProductAttribute record in the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.fieldname, self.displayname, self.type, self.metadata['datatype'], self.metadata['unit'].name,)
			cur.execute('''UPDATE product_attributes 
			SET fieldname=?1, displayname=?2, type=?3, datatype=?4, unit=?5 
			WHERE fieldname=?1''', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		"""Write the ProductAttribute to the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.fieldname, self.displayname, self.type, self.metadata['datatype'], self.metadata['unit'].name,)
			cur.execute('INSERT OR REPLACE INTO product_attributes VALUES (?,?,?,?,?)', params)
				
		finally:
			cur.close()
	
	def delete(self, connection):
		"""Delete the ProductAttribute from the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.fieldname,)
			cur.execute('DELETE FROM product_attributes WHERE fieldname=?', params)
			
		finally:
			cur.close()

class Product(OctopartPart):
	
	"""A physical product, independent of distributor.
	
	The primary identifying key is the manufacturer PN.
	"""
	
	@staticmethod
	def new_from_row(row, connection):
		"""Given a product row from the DB, returns a Product object."""
		
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
	def promote_octopart_part(part):
		"""Given an OctopartPart instance, returns a corresponding Product instance."""
		
		return Product(part.__dict__)
	
	@staticmethod
	def fetch_category_ids(mpn, connection):
		"""Fetch the list of category IDs for a given MPN."""
		
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
		"""Fetch the list of images for a given MPN."""
		
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
		"""Fetch the list of datasheets for a given MPN."""
		
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
		"""Fetch the list of descriptions for a given MPN."""
		
		descriptions = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT txt FROM descriptions WHERE product=?'
			params = (mpn,)
			for row in cur.execute(sql, params):
				descriptions.append({'text' : row[0]})
			
		finally:
			cur.close()
			return descriptions
	
	@staticmethod
	def fetch_offers(mpn, connection):
		"""Fetch the list of offers for a given MPN."""
		
		offers = []
		try:
			cur = connection.cursor()
			
			sql = 'SELECT * FROM offers WHERE mpn=? ORDER BY supplier'
			params = (mpn,)
			for row in cur.execute(sql, params):
				offer = Offer.new_from_row(row, connection)
				offers.append(offer)
			
		finally:
			cur.close()
			return offers
	
	@staticmethod
	def fetch_specs(mpn, connection):
		"""Fetch the list of specs for a given MPN."""
		
		specs = []
		attrib = ProductAttribute('', '', 'text', None)
		previous_fieldname = ''
		spec = {}
		try:
			cur = connection.cursor()
			
			sql = 'SELECT attribute, name, value FROM product_specs WHERE product=? ORDER BY attribute'
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
				spec['values'][0]['value'] = value
			
		finally:
			cur.close()
			return specs
	
	@staticmethod
	def select_all(connection):
		"""Return the entire products table as Product instances."""
		
		prods = []
		try:
			cur = connection.cursor()
			
			for row in cur.execute('SELECT * FROM products'):
				prods.append(Product.new_from_row(row, connection))
			
		finally:
			cur.close()
			return prods
	
	@staticmethod
	def select_by_pn(pn, connection):
		"""Return the Product(s) of given part number in a list."""
		
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
		self.manufacturer = Brand.promote_octopart_brand(self.manufacturer)
		for offer in self.offers:
			offer = Offer.new_from_octopart(self.mpn, offer)
		for spec in self.specs:
			spec['attribute'] = ProductAttribute.promote_octopart_part_attribute(spec['attribute'])
	
	def show(self, show_offers=False):
		"""A detailed print method."""
		
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
		"""Compares the Product to another Product."""
		
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
	
	def __eq__(self, p):
		return self.equals(p)
	
	def __contains__(self, item):
		"""Type-checks the passed item and performs a membership test on the relevant Product sequence attribute."""
		
		# An Offer instance
		if type(item) == Offer:
			return item in self.offers
		# A ProductAttribute instance (no associated attribute values)
		elif type(item) == ProductAttribute:
			return item in [spec['attribute'] for spec in self.specs]
		# A full spec dictionary (ProductAttribute and values)
		elif type(item) == dict and 'attribute' in item and 'values' in item:
			return item in self.specs
		# An images dictionary
		elif type(item) == dict and len(item) == 7 and 'url' in item:
			return item in self.images
		# A datasheet dictionary
		elif type(item) == dict and len(item) == 2 and 'url' in item and 'score' in item:
			return item in self.datasheets
		# A description dictionary
		elif type(item) == dict and len(item) == 1 and 'text' in item:
			return item in self.descriptions
		# A Category instance
		elif type(item) == Category:
			return item.id in self.category_ids
		# An integer: Most likely a category ID (there are no other sequences of just ints)
		elif type(item) == int:
			return item in self.category_ids
		else:
			return False
		
			
	
	def update(self, connection):
		"""Update an existing Product record in the DB."""
		
		try:
			cur = connection.cursor()
			sql = '''UPDATE products 
			SET uid=?1, mpn=?2, manufacturer=?3, detail_url=?4, avg_price=?5, 
			avg_avail=?6, market_status=?7, num_suppliers=?8, num_authsuppliers=?9, 
			short_description=?10, freesample_url=?11, evalkit_url=?12, manufacturer_url=?13
			WHERE mpn=?2'''
			params = (self.uid, self.mpn, self.manufacturer, self.detail_url, \
					self.avg_price, self.avg_avail, self.market_status, self.num_suppliers, \
					self.num_authsuppliers, self.short_description, self.hyperlinks['freesample'], \
					self.hyperlinks['evalkit'], self.hyperlinks['manufacturer'])
			cur.execute(sql, params)
			
			# Update product categories
			old_category_ids = []
			delete_category_ids = []
			for row in cur.execute('SELECT sheet FROM product_categories WHERE product=?', (self.mpn,)):
				old_category_ids.append(row[0])
				if row[0] not in self.category_ids:
					delete_category_ids.append(row)
			cur.executemany('DELETE FROM product_categories WHERE sheet=?', delete_category_ids)
			to_insert = list(set(self.category_ids).difference(old_category_ids))
			for sheet in to_insert:
				cur.execute('INSERT INTO product_categories VALUES (NULL,?,?)', (self.mpn, sheet,))
			
			# Update product images
			sql = '''UPDATE product_images 
			SET url=?2, url_30px=?3, url_35px=?4, url_55px=?5, url_90px=?6, 
			credit_url=?7, credit_domain=?8
			WHERE product=?1'''
			params = (self.mpn, self.images['url'], self.images['url_30px'], \
					self.images['url_35px'], self.images['url_55px'], self.images['url_90px'], \
					self.images['credit_url'], self.images['credit_domain'],)
			cur.execute(sql, params)
			
			# Update datasheets
			old_datasheets = set()
			old_ids = {}
			new_datasheets = set()
			
			for sheet in self.datasheets:
				new_datasheets.add((sheet['url'], sheet['score'],))
			
			for id, url, score in cur.execute('SELECT id, url, score FROM datasheets WHERE product=?', (self.mpn,)):
				old_datasheets.add((url, score,))
				old_ids[url] = id
			
			to_update = old_datasheets & new_datasheets
			to_insert = new_datasheets - old_datasheets
			to_delete = old_datasheets - new_datasheets
			
			for url, score in to_update:
				cur.execute('UPDATE datasheets SET url=?, score=?, product=? WHERE id=?', (url, score, self.mpn, old_ids[url]))
			
			for url, score in to_insert:
				cur.execute('INSERT INTO datasheets VALUES (NULL,?,?,?)', (self.mpn, url, score,))
				
			for url, score in to_delete:
				cur.execute('DELETE FROM datasheets WHERE product=? AND url=?', (self.mpn, url,))
			
			# Update descriptions
			old_descriptions = set()
			old_ids = {}
			new_descriptions = set()
			
			for desc in self.descriptions:
				new_descriptions.add((desc['text'],))
			
			for id, text in cur.execute('SELECT id, txt FROM descriptions WHERE product=?', (self.mpn,)):
				old_descriptions.add((text,))
				old_ids[text] = id
			
			to_update = old_descriptions & new_descriptions
			to_insert = new_descriptions - old_descriptions
			to_delete = old_descriptions - new_descriptions
			
			for desc in to_update:
				cur.execute('UPDATE descriptions SET txt=?, product=? WHERE id=?', (desc, self.mpn, old_ids[desc],))
			
			for desc in to_insert:
				cur.execute('INSERT INTO descriptions VALUES (NULL,?,?)', (self.mpn, desc,))
				
			for desc in to_delete:
				cur.execute('DELETE FROM descriptions WHERE id=?', (old_ids[desc],))
			
			# Update specs
			# specs field format: a list of dicts of format ('attribute': ProductAttribute, 'values' : [dicts of name : value pairs]
			# DB columns: (id, product, attribute(fieldname), name, value)
			old_specs = set()
			old_ids = {}
			new_specs = set(self.specs)
			
			for spec in self.specs:
				for vals_dict in spec['values']:
					for name, value in vals_dict.items():
						new_specs.add((spec['attribute'].fieldname, name, value,))
			
			for id, fieldname, name, value in cur.execute('SELECT id, attribute, name, value FROM product_specs WHERE product=?', (self.mpn,)):
				old_specs.add((fieldname, name, value,))
				old_ids[fieldname + '.' + name] = id
				
			to_update = old_specs & new_specs
			to_insert = new_specs - old_specs
			to_delete = old_specs - new_specs
			
			for spec in to_update:
				for vals_dict in spec['values']:
					for name, value in vals_dict.items():
						params = (self.mpn, spec['attribute'].fieldname, name, value, old_ids[spec['attribute'].fieldname + '.' + name],)
						cur.execute('UPDATE product_specs SET product=?, attribute=?, name=?, value=? WHERE id=?', params)
			
			for spec in to_insert:
				for vals_dict in spec['values']:
					for name, value in vals_dict.items():
						params = (self.mpn, spec['attribute'].fieldname, name, value,)
						sql = 'INSERT INTO product_specs VALUES (NULL,?,?,?,?)' 
						# Try and catch a FK violation here
						# Can't actually tell what kind of constraint is being violated
						# Attempt to correct FK violation by writing the ProductAttribute 
						# instance to DB and try again
						try:
							cur.execute(sql, params)
						except apsw.ConstraintError:
							spec['attribute'].insert(connection)
							cur.execute(sql, params)
			
			for spec in to_delete:
				for vals_dict in spec['values']:
					for name, value in vals_dict.items():
						params = (old_ids[spec['attribute'].fieldname + '.' + name],)
						cur.execute('DELETE FROM product_specs WHERE id=?', params)
			
		finally:
			cur.close()
	
	def insert(self, connection):
		"""Write the Product to the DB."""
		
		try:
			cur = connection.cursor()
			
			# Since we're inserting a fresh copy of the product, we should wipe
			# any existing entries/references to ensure that there are no extra
			# references to this product left over in the DB
			# One delete call should take care of everything via cascading
			# foreign key constraints
			self.delete(connection)
			
			params = (self.uid, self.mpn, self.manufacturer, self.detail_url, \
					self.avg_price, self.avg_avail, self.market_status, self.num_suppliers, \
					self.num_authsuppliers, self.short_description, self.hyperlinks['freesample'], \
					self.hyperlinks['evalkit'], self.hyperlinks['manufacturer'])
			cur.execute('INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', params)
			
			# Write product categories
			for id in self.category_ids:
				cur.execute('INSERT INTO product_categories VALUES (NULL,?,?)', (self.mpn, id,))
			
			# Write product images
			params = (self.mpn, self.images['url'], self.images['url_30px'], \
					self.images['url_35px'], self.images['url_55px'], self.images['url_90px'], \
					self.images['credit_url'], self.images['credit_domain'],)
			cur.execute('INSERT OR REPLACE INTO product_images VALUES (?,?,?,?,?,?,?,?)', params)
			
			# Write datasheets
			for sheet in self.datasheets:
				params = (self.mpn, sheet['url'], sheet['score'])
				cur.execute('INSERT INTO datasheets VALUES (NULL,?,?,?)', params)
			
			# Write descriptions
			for desc in self.descriptions:
				params = (self.mpn, desc['text'])
				cur.execute('INSERT INTO descriptions VALUES (NULL,?,?)', params)
			
			# Write specs
			for spec in self.specs:
				for vals_dict in spec['values']:
					for name, value in vals_dict.items():
						params = (self.mpn, spec['attribute'].fieldname, name, value,)
						sql = 'INSERT INTO product_specs VALUES (NULL,?,?,?,?)' 
						# Try and catch a FK violation here
						# Can't actually tell what kind of constraint is being violated
						# Attempt to correct FK violation by writing the ProductAttribute 
						# instance to DB and try again
						try:
							cur.execute(sql, params)
						except apsw.ConstraintError:
							spec['attribute'].insert(connection)
							cur.execute(sql, params)
				
		finally:
			cur.close()
	
	def delete(self, connection):
		"""Delete the Product from the DB."""
		
		try:
			cur = connection.cursor()
			
			params = (self.mpn,)
			cur.execute('DELETE FROM products WHERE mpn=?', params)
			
		finally:
			cur.close()
	
	def fetch_offers(self, connection):
		"""Fetch offers list for this Product.
		
		Clears and sets the self.offers list directly.
		"""
		
		self.offers.clear()
		try:
			cur = connection.cursor()
			
			params = (self.mpn,)
			for row in cur.execute('SELECT * FROM offers WHERE mpn=? ORDER BY supplier', params):
				offer = Offer.new_from_row(row, connection)
				self.offers.append(offer)
			
		finally:
			cur.close()
		
	def best_offer(self, qty):
		"""Return the Offer with the best price for the given order quantity. 
		
		If the "enforce minimum quantities" option is checked in the program config,
		only returns offers where the order quantity meets/exceeds the minimum
		order quantity for the offer.
		"""
		print 'Entering %s.best_offer(%s)' % (self.mpn, str(qty))
		best = None
		lowest_price = float("inf")
		for offer in self.offers:
			offer.show_brief()
			price_break = offer.get_price_break(qty)
			print 'price_break from offer.get_price_break( %s ) = ' % str(qty)
			print price_break
			if price_break == None or (price_break[0] > qty and ENFORCE_MIN_QTY):
				pass
			else:
				if (price_break[1]*qty) + offer.reel_fee < lowest_price:
					lowest_price = (price_break[1]*qty) + offer.reel_fee
					best = offer
					print 'Set best offer: ', best.show_brief()
		return best
	
	def get_preferred_offer(self, project, connection):
		"""Get a project's preferred Offer for this Product."""
		
		try:
			offer = None
			cur = connection.cursor()
			
			params = (project.name, self.mpn,)
			rows = list(cur.execute('SELECT offer FROM preferred_offers WHERE project=? AND product=?', params))
			if len(rows) > 0:
				offer = Offer.select_by_sku(rows[0][0], connection)[0]
			
		finally:
			cur.close()
			return offer
	
	def set_preferred_offer(self, project, offer, connection):
		"""Set a project's preferred Offer for this Product."""
		
		try:
			cur = connection.cursor()
			current_offer = self.get_preferred_offer(project, connection)
			if current_offer is None:
				params = (project.name, self.mpn, offer.sku,)
				cur.execute('INSERT INTO preferred_offers VALUES (NULL,?,?,?)', params) 
			else:
				params = (offer.sku, project.name, self.mpn,)
				cur.execute('UPDATE preferred_offers SET offer=? WHERE project=? AND product=?', params)
			
		finally:
			cur.close()
	
	def in_stock(self):
		"""Returns true if any Offers have inventory > 0 or == -2 ("yes")."""
		
		return True in [x > 0 or x == -2 for x in [offer.inventory for offer in self.offers]]
	
	def search_octopart(self):
		"""Multi-vendor search using Octopart.
		
		Uses the Octopart REST API instead of HTML scraping.
		"""
		
		octo = Octopart(OCTOPART_API_KEY)
	
	def scrape_dk(self):
		"""HTML scrape method for Digi-Key."""
		
		offer_dicts = []
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
			offer_dict = {}
			offer_dict['url'] = url
			page = urllib2.urlopen(url)
			soup = BeautifulSoup(page)
			#print "URL: %s" % url
			# Get prices
			# TODO: Currency
			prices = []
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
						prices.append(new_break, new_unit_price,)
						#print 'Adding break/price to prices list: ', (new_break, new_unit_price)
			offer_dict['prices'] = prices
			
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
			
			offer_dict['inventory'] = inventory 
			offer_dict['sku'] = soup.body("th", text="Digi-Key Part Number")[0].parent.nextSibling.contents[0].string.__str__()
			# Get manufacturer and PN
			offer_dict['manufacturer'] = soup.body("th", text="Manufacturer")[0].parent.nextSibling.contents[0].contents[0].string.__str__()
			#print "manufacturer is: %s" % manufacturer
			offer_dict['mpn'] = soup.body('th', text="Manufacturer Part Number")[0].parent.nextSibling.contents[0].string.__str__()
			#print "mpn is: %s" % mpn
			
			# Get datasheet filename and download
			# TODO: This can only get one datasheet
			datasheet_soup = soup.body('th', text="Datasheets")[0].parent.nextSibling
			datasheet_anchor = datasheet_soup.findAllNext('a')[0]
			#print "datasheet_soup is: %s" % datasheet_soup
			#print "datasheet_anchor is: %s" % datasheet_anchor
			datasheet_url = datasheet_anchor['href']
			#print "datasheet_url is: %s" % datasheet_url
			offer_dict['datasheet_url'] = datasheet_url
			row = urllib2.urlopen(urllib2.Request(datasheet_url))
			try:
				file_name = get_filename(url,row)
				offer_dict['datasheet'] = file_name;
				# TODO: Do not re-download if already saved
				if DOWNLOAD_DATASHEET:
					with open(file_name, 'wb') as f:
						shutil.copyfileobj(row,f)
			finally:
				row.close()
			#print "datasheet is: %s" % datasheet
			# Get remaining strings (desc, category, family, series, package)
			offer_dict['description'] = soup.body('th', text="Description")[0].parent.nextSibling.contents[0].string.__str__()
			#print "description is: %s" % description
			offer_dict['category'] = soup.body('th', text="Category")[0].parent.nextSibling.contents[0].string.__str__()
			#print "category is: %s" % category
			offer_dict['family'] = soup.body('th', text="Family")[0].parent.nextSibling.contents[0].string.__str__()
			#print "family is: %s" % family
			offer_dict['series'] = soup.body('th', text="Series")[0].parent.nextSibling.contents[0].string.__str__()
			#print "series is: %s" % series
			offer_dict['package'] = soup.body('th', text="Package / Case")[0].parent.nextSibling.contents[0].string.__str__()
			#print "package is: %s" % package
			
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
			offer_dict['packaging'] = packaging
			if packaging in Offer.REEL_FEES:
				offer_dict['reel_fee'] = Offer.REEL_FEES[packaging]
			else:
				offer_dict['reel_fee'] = 0
			offer_dicts.append(offer_dict)
		
		return offer_dicts
	
	def scrape_far(self):
		"""Scrape method for Farnell."""
		
		raise NotImplementedError("Farnell scraping not yet implemented!")
	
	def scrape_fue(self):
		"""Scrape method for Future Electronics."""
		
		raise NotImplementedError("Future scraping not yet implemented!")
		
	def scrape_jam(self):
		"""Scrape method for Jameco."""
		
		raise NotImplementedError("Jameco scraping not yet implemented!")
		
	def scrape_me(self):
		"""Scrape method for Mouser Electronics."""
		
		raise NotImplementedError("Mouser scraping not yet implemented!")
		
		search_url = 'http://www.mouser.com/Search/Refine.aspx?Keyword=' + self.mpn
		search_page = urllib2.urlopen(search_url)
		search_soup = BeautifulSoup(search_page)
		
		# Create a list of product URLs from the search page
		prod_urls = []
		# Check "Mouser Part #" column in table -- ignore any rows where that cell says "Not Assigned"
	
	def scrape_new(self):
		"""Scrape method for Newark."""
		
		raise NotImplementedError("Newark scraping not yet implemented!")
	
	def scrape_sfe(self, sku):
		"""Scrape method for Sparkfun."""
		
		raise NotImplementedError("SparkFun scraping not yet implemented!")
		# Clear previous pricing data (in case price break keys change)
		
		# The URL contains the numeric portion of the part number, minus any leading zeroes
		url = "http://www.sparkfun.com/products/" + str(int(sku.split("-")))
		page = urllib2.urlopen(url)
		soup = BeautifulSoup(page)
			
	def scrape(self, connection):
		"""Scrape each supplier page to refresh product pricing info."""
		
		if no_vendors_enabled() == True:
			if VENDOR_WARN_IF_NONE_EN == True:
				raise ScrapeException(self.scrape.__name__, self.mpn, 3)
		
		else:
			self.offers.clear()
			# Proceed based on supplier config
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
			for offer in self.offers:
				if offer.is_in_db(connection):
					offer.update(connection)
				else:
					offer.insert(connection)
			if len(self.offers) == 0:
				raise ScrapeException(self.scrape.__name__, self.mpn, 1)
			if self.in_stock() == False:
				raise ScrapeException(VENDOR_DK, self.mpn, 2)
			
				

	def is_in_db(self, connection):
		"""Check if this Product is in the database."""
		
		result = Product.select_by_pn(self.mpn, connection)
		if len(result) == 0:
			return False
		else:
			return True

	def select_or_scrape(self, connection):
		"""Sets the Product fields, pulling from the local DB if possible."""
		if(self.is_in_db(connection)):
			temp = Product.select_by_pn(self.mpn, connection)[0]
			self.manufacturer = temp.manufacturer
			self.mpn = temp.mpn
			self.datasheet = temp.datasheet
			self.description = temp.description
			self.package = temp.package
			self.fetch_offers(connection)
		elif self.mpn is not None and self.mpn != 'none' and self.mpn != 'NULL':
			self.scrape(connection)

