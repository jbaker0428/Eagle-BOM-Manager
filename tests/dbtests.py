import os
import unittest
from urbm import Workspace

class DatabaseTestCase(unittest.TestCase):
	def setUp(self):
		self.wspace = Workspace('DB Tests', os.path.join(os.getcwd(), 'dbtests.sqlite'))
		self.testPart = bomPart('C1', '1uF', 'C-USC0603', 'C0603', 'CAPACITOR, American symbol', 'C1608X5R1E105K')
		self.testProduct = Product('TDK Corporation', 'C1608X5R1E105K', 'general_B11.pdf', 'CAP CER 1UF 25V 10% X5R 0603', '0603 (1608 Metric)')
		self.pdictCT = dict({10 : 0.09000, 100 : 0.04280, 250 : 0.03600, 500 : 0.03016, 1000 : 0.02475})
		self.pdictTR = dict({4000 : 0.01935, 8000 : 0.01800, 12000 : 0.01710, 280000 : 0.01620, 100000 : 0.01227})
		self.pdictDR = dict({10 : 0.09000, 100 : 0.04280, 250 : 0.03600, 500 : 0.03016, 1000 : 0.02475})
		self.testListingCT = vendorProduct(VENDOR_DK, '445-5146-1-ND', 'C1608X5R1E105K', pdictCT, 566342, 'Cut Tape (CT)', 0, 'Capacitors', 'Ceramic', 'C')
		self.testListingTR = vendorProduct(VENDOR_DK, '445-5146-2-ND', 'C1608X5R1E105K', pdictTR, 552000, 'Tape & Reel (TR)', 0, 'Capacitors', 'Ceramic', 'C')
		self.testListingDR = vendorProduct(VENDOR_DK, '445-5146-6-ND', 'C1608X5R1E105K', pdictDR, 566342, 'Digi-Reel', 7, 'Capacitors', 'Ceramic', 'C')
		self.testProduct.vendorProds[self.testListingCT.key()] = self.testListingCT
		self.testProduct.vendorProds[self.testListingTR.key()] = self.testListingTR
		self.testProduct.vendorProds[self.testListingDR.key()] = self.testListingDR

if __name__ == '__main__':
	from urbm_product import *
	from urbm_bompart import bomPart
	from urbm_bom import BOM
	unittest.main()	