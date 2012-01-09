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
		datasheet = ""
	
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

<tr><th align=right valign=top>Datasheets</th><td>
	<a href="http://www.tdk.co.jp/tefe02/e4941_fk.pdf" target="_blank">FK Series General Use</a><br />
</td></tr>

<table id=pricing frame=void rules=all border=1 cellspacing=0 cellpadding=1>
<tr><th>Price Break</th><th>Unit Price</th><th>Extended Price
</th></tr>
<tr><td align=center >1</td><td align=right >1.25000</td><td align=right >1.25</td></tr>
<tr><td align=center >10</td><td align=right >0.99000</td><td align=right >9.90</td></tr>
<tr><td align=center >100</td><td align=right >0.74250</td><td align=right >74.25</td></tr>
<tr><td align=center >250</td><td align=right >0.66000</td><td align=right >165.00</td></tr>
<tr><td align=center >500</td><td align=right >0.56100</td><td align=right >280.50</td></tr>
<tr><td align=center >1,000</td><td align=right >0.49500</td><td align=right >495.00</td></tr>
<tr><td align=center >5,000</td><td align=right >0.44550</td><td align=right >2,227.50</td></tr>
<tr><td align=center >10,000</td><td align=right >0.42900</td><td align=right >4,290.00</td></tr>
<tr><td align=center >25,000</td><td align=right >0.41250</td><td align=right >10,312.50</td></tr>
</table>

#call sorted(prices.keys(), reverse=True) on prices.keys() to evaluate the price breaks in order
