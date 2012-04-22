import os
import unittest
from manager import Workspace

class DatabaseTestCase(unittest.TestCase):
	def setUp(self):
		unittest.TestCase.setUp(self)
		from product import *
		from part import Part
		
		self.wspace = Workspace('DB Tests', os.path.join(os.getcwd(), 'dbtests.sqlite'))
		self.test_product = Product('TDK Corporation', 'C1608X5R1E105K', 'general_B11.pdf', 'CAP CER 1UF 25V 10% X5R 0603', '0603 (1608 Metric)')
		self.prices_ct = dict({10 : 0.09000, 100 : 0.04280, 250 : 0.03600, 500 : 0.03016, 1000 : 0.02475})
		self.prices_tr = dict({4000 : 0.01935, 8000 : 0.01800, 12000 : 0.01710, 280000 : 0.01620, 100000 : 0.01227})
		self.prices_dr = dict({10 : 0.09000, 100 : 0.04280, 250 : 0.03600, 500 : 0.03016, 1000 : 0.02475})
		self.test_listing_ct = Listing(VENDOR_DK, '445-5146-1-ND', 'C1608X5R1E105K', self.prices_ct, 566342, 'Cut Tape (CT)', 0, 'Capacitors', 'Ceramic', 'C')
		self.test_listing_tr = Listing(VENDOR_DK, '445-5146-2-ND', 'C1608X5R1E105K', self.prices_tr, 552000, 'Tape & Reel (TR)', 0, 'Capacitors', 'Ceramic', 'C')
		self.test_listing_dr = Listing(VENDOR_DK, '445-5146-6-ND', 'C1608X5R1E105K', self.prices_dr, 566342, 'Digi-Reel', 7, 'Capacitors', 'Ceramic', 'C')
		self.test_product.listings[self.test_listing_ct.key()] = self.test_listing_ct
		self.test_product.listings[self.test_listing_tr.key()] = self.test_listing_tr
		self.test_product.listings[self.test_listing_dr.key()] = self.test_listing_dr
		self.part_attribs = dict({'TOL' : '10%', 'VOLT' : '25V', 'TC' : 'X5R'})
		self.test_part = Part('C1', 'dbtests', '1uF', 'C-USC0603', 'C0603', 'CAPACITOR, American symbol', self.test_product, self.part_attribs)
		
	def testdb(self):
		try:
			self.wspace.create_tables()
			from product import Product, Listing
			from part import Part
			from bom import BOM
			tables = []
			(con, cur) = self.wspace.con_cursor()
			cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
			for row in cur.fetchall():
				tables.append(row[0])
			
			cur.close()
			
			assert 'products' in tables
			assert 'parts' in tables
			assert 'part_attributes' in tables
			assert 'listings' in tables
			assert 'projects' in tables
			assert 'pricebreaks' in tables
			
			self.test_BOM = BOM.new_project('dbtests', 'Databse Unit tests', '', self.wspace, con)
			self.wspace.projects = self.wspace.list_projects(con)
			
			assert len(self.wspace.projects) == 1
			assert 'dbtests' in self.wspace.projects
			
			self.test_product.insert(self.wspace, con)
			self.test_listing_ct.insert(self.wspace, con)
			self.test_listing_tr.insert(self.wspace, con)
			self.test_listing_dr.insert(self.wspace, con)
			self.test_part.insert(self.wspace, con)
			
			# Product.select_by_pn fetches listings for the product, and fetch_listings fetches the price dicts
			ret_products = Product.select_by_pn(self.test_product.manufacturer_pn, self.wspace, con)
			assert self.test_product.is_in_db(self.wspace, con)
					
			# Should only return one result:
			assert len(ret_products) == 1
			
			# Product.equals() calls Listing.equals() as part of the check
			assert len (Listing.select_by_vendor_pn(self.test_listing_ct.vendor_pn, self.wspace, con)) == 1
			assert len (Listing.select_by_vendor_pn(self.test_listing_tr.vendor_pn, self.wspace, con)) == 1
			assert len (Listing.select_by_vendor_pn(self.test_listing_dr.vendor_pn, self.wspace, con)) == 1
			assert len (Listing.select_by_manufacturer_pn(self.test_product.manufacturer_pn, self.wspace, con)) == 3
			assert self.test_product.equals(ret_products[0])
			
			assert self.test_part.has_attribute('TOL', self.wspace, con)
			assert self.test_part.has_attribute('VOLT', self.wspace, con)
			assert self.test_part.has_attribute('TC', self.wspace, con)
			ret_parts = Part.select_by_name(self.test_part.name, self.wspace, self.test_BOM.name, con)
			assert len(ret_parts) == 1
			assert self.test_part.equals(ret_parts[0])
			assert self.test_part.is_in_db(self.wspace, con)
			ret_parts = self.test_BOM.select_parts_by_name(self.test_part.name, self.wspace, con)
			assert len(ret_parts) == 1
			assert self.test_part.equals(ret_parts[0])
			
			self.test_part.delete(self.wspace, con)
			assert len(self.test_BOM.select_parts_by_name(self.test_part.name, self.wspace, con)) == 0
			assert self.test_part.is_in_db(self.wspace, con) == False
			
			assert len (Listing.select_by_manufacturer_pn(self.test_product.manufacturer_pn, self.wspace, con)) == 3
			self.test_listing_ct.delete(self.wspace, con)
			assert len (Listing.select_by_manufacturer_pn(self.test_product.manufacturer_pn, self.wspace, con)) == 2
			assert len (Listing.select_by_vendor_pn(self.test_listing_ct.vendor_pn, self.wspace)) == 0
			self.test_listing_tr.delete(self.wspace, con)
			assert len (Listing.select_by_manufacturer_pn(self.test_product.manufacturer_pn, self.wspace, con)) == 1
			assert len (Listing.select_by_vendor_pn(self.test_listing_tr.vendor_pn, self.wspace, con)) == 0
			self.test_listing_dr.delete(self.wspace, con)
			assert len (Listing.select_by_manufacturer_pn(self.test_product.manufacturer_pn, self.wspace, con)) == 0
			assert len (Listing.select_by_vendor_pn(self.test_listing_dr.vendor_pn, self.wspace, con)) == 0
			
			assert len(Product.select_by_pn(self.test_product.manufacturer_pn, self.wspace, con)) == 1
			self.test_product.delete(self.wspace, con)
			assert len(Product.select_by_pn(self.test_product.manufacturer_pn, self.wspace, con)) == 0
			assert self.test_product.is_in_db(self.wspace, con) == False
			
			self.test_BOM.delete(self.wspace, con)
			self.wspace.projects = self.wspace.list_projects(con)
			assert len(self.wspace.projects) == 0
			assert 'dbtests' not in self.wspace.projects
			
			tables = []
			cur = con.cursor()
			cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
			for row in cur.fetchall():
				tables.append(row[0])
			
			
			
			assert 'products' in tables
			assert 'parts' in tables
			assert 'part_attributes' in tables
			assert 'listings' in tables
			assert 'projects' in tables
			assert 'pricebreaks' in tables
			assert 'dbtests' not in tables
		finally:
			cur.close()
			con.close()
	
	def tearDown(self):
		unittest.TestCase.tearDown(self)
		del self.wspace
		os.remove(os.path.join(os.getcwd(), 'dbtests.sqlite'))

if __name__ == '__main__':
	unittest.main()	