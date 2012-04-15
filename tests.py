import os
import unittest
from manager import Workspace

class DatabaseTestCase(unittest.TestCase):
	def setUp(self):
		unittest.TestCase.setUp(self)
		from product import *
		from part import bomPart
		
		self.wspace = Workspace('DB Tests', os.path.join(os.getcwd(), 'dbtests.sqlite'))
		
		self.testPart = bomPart('C1', '1uF', 'C-USC0603', 'C0603', 'CAPACITOR, American symbol', 'C1608X5R1E105K')
		self.testProduct = Product('TDK Corporation', 'C1608X5R1E105K', 'general_B11.pdf', 'CAP CER 1UF 25V 10% X5R 0603', '0603 (1608 Metric)')
		self.pdictCT = dict({10 : 0.09000, 100 : 0.04280, 250 : 0.03600, 500 : 0.03016, 1000 : 0.02475})
		self.pdictTR = dict({4000 : 0.01935, 8000 : 0.01800, 12000 : 0.01710, 280000 : 0.01620, 100000 : 0.01227})
		self.pdictDR = dict({10 : 0.09000, 100 : 0.04280, 250 : 0.03600, 500 : 0.03016, 1000 : 0.02475})
		self.testListingCT = vendorProduct(VENDOR_DK, '445-5146-1-ND', 'C1608X5R1E105K', self.pdictCT, 566342, 'Cut Tape (CT)', 0, 'Capacitors', 'Ceramic', 'C')
		self.testListingTR = vendorProduct(VENDOR_DK, '445-5146-2-ND', 'C1608X5R1E105K', self.pdictTR, 552000, 'Tape & Reel (TR)', 0, 'Capacitors', 'Ceramic', 'C')
		self.testListingDR = vendorProduct(VENDOR_DK, '445-5146-6-ND', 'C1608X5R1E105K', self.pdictDR, 566342, 'Digi-Reel', 7, 'Capacitors', 'Ceramic', 'C')
		self.testProduct.vendorProds[self.testListingCT.key()] = self.testListingCT
		self.testProduct.vendorProds[self.testListingTR.key()] = self.testListingTR
		self.testProduct.vendorProds[self.testListingDR.key()] = self.testListingDR
		
	def testdb(self):
		self.wspace.createTables()
		from product import Product, vendorProduct
		from part import bomPart
		from bom import BOM
		tables = []
		(con, cur) = self.wspace.con_cursor()
		cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
		for row in cur.fetchall():
			tables.append(row[0])
		
		cur.close()
		con.close()
		
		assert 'products' in tables
		assert 'vendorproducts' in tables
		assert 'projects' in tables
		assert 'pricebreaks' in tables
		
		self.testBOM = BOM.newProject('dbtests', 'Databse Unit tests', '', self.wspace)
		self.wspace.projects = self.wspace.listProjects()
		
		assert len(self.wspace.projects) == 1
		assert 'dbtests' in self.wspace.projects
		
		self.testProduct.insert(self.wspace)
		self.testListingCT.insert(self.wspace)
		self.testListingTR.insert(self.wspace)
		self.testListingDR.insert(self.wspace)
		self.testPart.insert(self.testBOM.name, self.wspace)
		
		# Product.select_by_pn fetches listings for the product, and fetchListings fetches the price dicts
		retProducts = Product.select_by_pn(self.testProduct.manufacturer_pn, self.wspace)
		assert self.testProduct.isInDB(self.wspace)
		# Should only return one result:
		assert len(retProducts) == 1
		
		# Product.equals() calls vendorProduct.equals() as part of the check
		assert len (vendorProduct.select_by_vendor_pn(self.testListingCT.vendorPN, self.wspace)) == 1
		assert len (vendorProduct.select_by_vendor_pn(self.testListingTR.vendorPN, self.wspace)) == 1
		assert len (vendorProduct.select_by_vendor_pn(self.testListingDR.vendorPN, self.wspace)) == 1
		assert len (vendorProduct.select_by_manufacturer_pn(self.testProduct.manufacturer_pn, self.wspace)) == 3
		assert self.testProduct.equals(retProducts[0])
		
		retParts = bomPart.select_by_name(self.testPart.name, self.testBOM.name, self.wspace)
		assert len(retParts) == 1
		assert self.testPart.equals(retParts[0])
		assert self.testPart.isInDB(self.testBOM.name, self.wspace)
		retParts = self.testBOM.select_parts_by_name(self.testPart.name, self.wspace)
		assert len(retParts) == 1
		assert self.testPart.equals(retParts[0])
		
		self.testPart.delete(self.testBOM.name, self.wspace)
		assert len(self.testBOM.select_parts_by_name(self.testPart.name, self.wspace)) == 0
		assert self.testPart.isInDB(self.testBOM.name, self.wspace) == False
		
		assert len (vendorProduct.select_by_manufacturer_pn(self.testProduct.manufacturer_pn, self.wspace)) == 3
		self.testListingCT.delete(self.wspace)
		assert len (vendorProduct.select_by_manufacturer_pn(self.testProduct.manufacturer_pn, self.wspace)) == 2
		assert len (vendorProduct.select_by_vendor_pn(self.testListingCT.vendorPN, self.wspace)) == 0
		self.testListingTR.delete(self.wspace)
		assert len (vendorProduct.select_by_manufacturer_pn(self.testProduct.manufacturer_pn, self.wspace)) == 1
		assert len (vendorProduct.select_by_vendor_pn(self.testListingTR.vendorPN, self.wspace)) == 0
		self.testListingDR.delete(self.wspace)
		assert len (vendorProduct.select_by_manufacturer_pn(self.testProduct.manufacturer_pn, self.wspace)) == 0
		assert len (vendorProduct.select_by_vendor_pn(self.testListingDR.vendorPN, self.wspace)) == 0
		
		assert len(Product.select_by_pn(self.testProduct.manufacturer_pn, self.wspace)) == 1
		self.testProduct.delete(self.wspace)
		assert len(Product.select_by_pn(self.testProduct.manufacturer_pn, self.wspace)) == 0
		assert self.testProduct.isInDB(self.wspace) == False
		
		self.testBOM.delete(self.wspace)
		self.wspace.projects = self.wspace.listProjects()
		assert len(self.wspace.projects) == 0
		assert 'dbtests' not in self.wspace.projects
		
		tables = []
		(con, cur) = self.wspace.con_cursor()
		cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
		for row in cur.fetchall():
			tables.append(row[0])
		
		cur.close()
		con.close()
		
		assert 'products' in tables
		assert 'vendorproducts' in tables
		assert 'projects' in tables
		assert 'pricebreaks' in tables
		assert 'dbtests' not in tables
	
	def tearDown(self):
		unittest.TestCase.tearDown(self)
		del self.wspace
		os.remove(os.path.join(os.getcwd(), 'dbtests.sqlite'))

if __name__ == '__main__':
	unittest.main()	