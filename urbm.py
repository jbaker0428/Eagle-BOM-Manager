import urllib2
import csv
from BeautifulSoup import BeautifulSoup

def enum(*sequential, **named):
	enums = dict(zip(sequential, range(len(sequential))), **named)
	return type('Enum', (), enums)


class Product:
	vendors = enum('DK', 'ME', 'SFE')
	def __init__(self, vendor, pn)
		self.vendor = vendors.vendor
		self.pn = pn
		self.prices = {}


#call sorted(prices.keys(), reverse=True) on prices.keys() to evaluate the price breaks in order