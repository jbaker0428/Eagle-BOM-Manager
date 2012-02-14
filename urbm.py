import csv
import pygtk
pygtk.require('2.0')
import gtk
import y_serial_v060 as y_serial
import shutil
import os
import types
from urbm_product import Product
from urbm_bompart import bomPart
from urbm_bom import BOM

urbmDB = y_serial.Main(os.path.join(os.getcwd(), "urbm.sqlite"))
urbmDB.createtable('products')

def getProductDBSize():
	dict = urbmDB.selectdic("?", 'products')

active_bom = BOM("test1", urbmDB, os.path.join(os.getcwd(), "test.csv"))

'''GUI class'''
class URBM:
	def delete_event(self, widget, event, data=None):
		print "delete event occurred"
		return False
		
	def destroy(self, widget, data=None):
		gtk.main_quit()

	# -------- CALLBACK METHODS --------
	def readInputCallback(self, widget, data=None):
		active_bom.readFromFile()
		#Read back last entry
		urbmDB.view(1, active_bom.name)
		if self.bomGroupName.get_active():
			self.drawBomByName()
		elif self.bomGroupValue.get_active():
			self.drawBomByValue()
		elif self.bomGroupPN.get_active():
			self.drawBomByPN()
		self.window.show_all()
	
	def readDBCallback(self, widget, data=None):
		print "Read DB callback"
		active_bom.readFromDB()
		if self.bomGroupName.get_active():
			self.drawBomByName()
		elif self.bomGroupValue.get_active():
			self.drawBomByValue()
		elif self.bomGroupPN.get_active():
			self.drawBomByPN()
		self.window.show_all()
	
	def bomRadioCallback(self, widget, data=None):
		# Set class fields for currently selected item
		self.curBomRow = int(data) 	# Convert str to int
		self.selectedBomPart = urbmDB.select(self.bomContentLabels[self.curBomRow][0].get_text()[1:], active_bom.name)
		# Grab the vendor part number for the selected item from the label text
		selectedPN = self.bomContentLabels[self.curBomRow][5].get_text()
		print "selectedPN is: %s" % selectedPN
		if selectedPN != "none": # Look up part in DB
			# Set class field for currently selected product
			print "Querying with selectedPN: %s" % selectedPN
			self.selectedProduct.vendor_pn = selectedPN
			
			self.selectedProduct.selectOrScrape()
			self.setPartInfoLabels(self.selectedProduct)
			self.setPartPriceLabels(self.selectedProduct)
		else:
			self.destroyPartPriceLabels()
			self.clearPartInfoLabels()
	
	def bomGroupCallback(self, widget, data=None):
		#print "%s was toggled %s" % (data, ("OFF", "ON")[widget.get_active()])
		
		# Figure out which button is now selected
		if widget.get_active():
			if 'name' in data:
				self.drawBomByName()
				
			elif 'value' in data:
				self.drawBomByValue()
					
			elif 'product' in data:
				self.drawBomByPN()
					
			self.window.show_all()
	
	def bomSetProductCallback(self, widget, data=None):
		# Open a text input prompt window
		setProductDialog = gtk.Dialog("Set part number", self.window, 
						gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, 
						gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		self.setProductEntry = gtk.Entry()
		self.productEntryText = ""
		
		setProductDialogHBox1 = gtk.HBox()
		setProductDialogHBox2 = gtk.HBox()
		setProductVendorLabel = gtk.Label("Vendor: ")
		setProductVendorPNLabel = gtk.Label("Vendor Part Number: ")
		setProductVendorCombo = gtk.combo_box_new_text()
		
		setProductVendorCombo.append_text(Product.VENDOR_DK)
		setProductVendorCombo.append_text(Product.VENDOR_ME)
		setProductVendorCombo.append_text(Product.VENDOR_SFE)
		setProductVendorLabel.set_alignment(0.5, 0.5)
		setProductVendorPNLabel.set_alignment(0.4, 0.5)
		
		self.setProductEntry.show()
		setProductVendorCombo.show() 
		setProductDialogHBox1.pack_start(setProductVendorLabel, True, True, 0)
		setProductDialogHBox1.pack_start(setProductVendorCombo, True, True, 0)
		setProductDialogHBox2.pack_start(setProductVendorPNLabel, True, True, 0)
		setProductDialogHBox2.pack_start(self.setProductEntry, gtk.RESPONSE_ACCEPT)
		setProductDialog.vbox.pack_start(setProductDialogHBox1, True, True, 0)
		setProductDialog.vbox.pack_start(setProductDialogHBox2, True, True, 0)
		setProductDialogHBox1.show()
		setProductDialogHBox2.show()
		setProductVendorLabel.show()
		setProductVendorPNLabel.show()
		setProductDialog.run()
		setProductDialog.hide()
		
		# If the product text entry field is left blank, set the product to "none"
		if type(self.setProductEntry.get_text()) is types.NoneType or len(self.setProductEntry.get_text()) == 0:
			self.productEntryText = "none"
		else:
			self.productEntryText = self.setProductEntry.get_text()
		
		# Set selectedBomPart
		print "Setting selectedBomPart.product to: %s" % self.productEntryText
		self.selectedBomPart.product = self.productEntryText
		print "selectedBomPart's product field: %s" % self.selectedBomPart.product
		self.selectedBomPart.writeToDB()
		active_bom.updateParts(self.selectedBomPart)
		
		self.bomContentLabels[self.curBomRow][5].set_label(self.productEntryText)
		self.bomContentLabels[self.curBomRow][5].show()
		print "Part Number label text: %s" % self.bomContentLabels[self.curBomRow][5].get_text()
		
		# Make sure the user selected a vendor
		# If not, default to Digikey
		if type(setProductVendorCombo.get_active_text()) is types.NoneType:
			print "NoneType caught"
			self.selectedProduct.vendor = Product.VENDOR_DK
		else:	
			self.selectedProduct.vendor = setProductVendorCombo.get_active_text()
		self.selectedProduct.vendor_pn = self.productEntryText
		self.selectedProduct.selectOrScrape()
		if self.selectedProduct.vendor_pn == "none":
			self.clearPartInfoLabels()
			self.destroyPartPriceLabels()
		else:
			self.setPartInfoLabels(self.selectedProduct)
			self.setPartPriceLabels(self.selectedProduct)
		 
	# -------- HELPER METHODS --------
	def bomTableHeaders(self):
		self.bomTable.attach(self.bomColLabel1, 0, 1, 0, 1)
		self.bomTable.attach(self.bomColLabel2, 1, 2, 0, 1)
		self.bomTable.attach(self.bomColLabel3, 2, 3, 0, 1)
		self.bomTable.attach(self.bomColLabel4, 3, 4, 0, 1)
		self.bomTable.attach(self.bomColLabel5, 4, 5, 0, 1)
		self.bomTable.attach(self.bomColLabel6, 5, 6, 0, 1)
		self.bomTable.attach(self.bomColLabel7, 6, 7, 0, 1)
	
	''' Create an array of strings to set bomContentLabels texts to'''
	def setBomLabelTextsName(self):
		bomLabelTexts = []
		for p in active_bom.parts:
			# temp is a bomPart object from the DB
			temp = urbmDB.select(p[0], active_bom.name)
			self.bomLabelTexts.append((part.name, part.value, part.device, part.package, part.description, part.product))
			
		return bomLabelTexts
	
	def populateBomRow(self, labelRow, stringsTuple, quantity=""):
		for i in range(6):
			labelRow[i].set_label(stringTuple[i])
		labelRow[6].set_label(quantity)
		return labelRow
		
	def createBomLabels(self, numRows, labelTexts=None):
		rows = []
		if labelTexts is None:
			for x in range(numRows):
				row = []
				for i in range(7):
					row.append(gtk.Label(None))
				rows.append(row)
		else:
			for x in range(numRows):
				row = []
				for i in range(7):
					row.append(gtk.Label(labelTexts[x][i]))
				rows.append(row)
		return rows
	
	def destroyBomLabels(self):
		for x in self.bomContentLabels:
			for y in x:
				y.destroy()
	
	def createBomRadios(self, numRows):
		radios = []
		for x in range(numRows):
			radios.append(gtk.RadioButton(self.bomRadioGroup))
			radios[x].connect("toggled", self.bomRadioCallback, str(x))
		return radios
	
	def attachBomRadios(self):
		r = 0
		for radio in self.bomRadios:
			self.bomTable.attach(radio,  0, 7, r+1, r+2)
			r += 1
	
	def destroyBomRadios(self):
		for r in self.bomRadios:
			r.destroy()
	
	''' @param row considers index 0 to be the first row of content after headers'''
	def populateBomRow(self, part, row, quantity=""):
		self.bomContentLabels[row][0].set_label("\t" + part.name)
		self.bomContentLabels[row][1].set_label(part.value)
		self.bomContentLabels[row][2].set_label(part.device)
		self.bomContentLabels[row][3].set_label(part.package)
		self.bomContentLabels[row][4].set_label(part.description)
		self.bomContentLabels[row][5].set_label(part.product)
		self.bomContentLabels[row][6].set_label(str(quantity))
	
	''' @param row considers index 0 to be the first row of content after headers'''	
	def attachBomRow(self, row):
		i = 0
		for label in self.bomContentLabels[row]:
			self.bomTable.attach(label,  i, i+1, row+1, row+2)
			i += 1
	
	def drawBomByName(self):
		active_bom.sortByName()
		old = len(self.bomContentLabels)
		self.destroyBomLabels()
		self.destroyBomRadios()
		del self.bomRadios[0:old]
		del self.bomContentLabels[0:old]
		self.bomTable.resize(len(active_bom.parts)+1, 8)
		self.bomRadios = self.createBomRadios(len(active_bom.parts))
		self.attachBomRadios()
		self.bomContentLabels = self.createBomLabels(len(active_bom.parts))
		rowNum = 0
		for p in active_bom.parts:
			# temp is a bomPart object from the DB
			temp = urbmDB.select(p[0], active_bom.name)
			self.populateBomRow(temp, rowNum)
			self.attachBomRow(rowNum)
			rowNum += 1
	
	def drawBomByValue(self):
		active_bom.sortByVal()
		active_bom.setValCounts()
		tableLen = 1 + len(active_bom.valCounts.keys())
		old = len(self.bomContentLabels)
		self.destroyBomLabels()
		self.destroyBomRadios()
		del self.bomRadios[0:old]
		del self.bomContentLabels[0:old]
		self.bomTable.resize(tableLen, 8)
		self.bomRadios = self.createBomRadios(len(active_bom.valCounts.keys()))
		self.attachBomRadios()
		self.bomContentLabels = self.createBomLabels(len(active_bom.valCounts.keys()))
		
		rowNum = 0
		# Will sort by value as well (kept for future reference)
		#vals = sorted(active_bom.valCounts.keys())
		#for val in vals: 
		for val in active_bom.valCounts.keys():
			groupName = "\t"	# Clear groupName and prepend a tab
			group = urbmDB.selectdic("#val=" + val, active_bom.name)
			for part in group.values():
				groupName += part[2].name + ", "
			
			# Replace trailing comma with tab
			groupName = groupName[0:-2]
			self.populateBomRow(group[group.keys()[0]][2], rowNum, active_bom.valCounts[val])
			self.bomContentLabels[rowNum][0].set_label(groupName)
			self.attachBomRow(rowNum)
			rowNum += 1
	
	def drawBomByPN(self):
		active_bom.sortByProd()
		active_bom.setProdCounts()
		tableLen = 1 + len(active_bom.prodCounts.keys())
		old = len(self.bomContentLabels)
		self.destroyBomLabels()
		self.destroyBomRadios()
		del self.bomRadios[0:old]
		del self.bomContentLabels[0:old]
		self.bomTable.resize(tableLen, 8)
		self.bomRadios = self.createBomRadios(len(active_bom.prodCounts.keys()))
		self.attachBomRadios()
		self.bomContentLabels = self.createBomLabels(len(active_bom.prodCounts.keys()))
		rowNum = 0
		print "prodCounts.keys(): ", active_bom.prodCounts.keys()
		for prod in active_bom.prodCounts.keys():
			groupName = "\t"	# Clear groupName and prepend a tab
			print "Querying with prod =", prod, " of length ", len(prod)
			# Catch empty product string
			if prod == ' ' or len(prod) == 0: 
				print "Caught empty product"
				group = urbmDB.selectdic("#prod=none", active_bom.name)
			else:
				group = urbmDB.selectdic("#prod=" + prod, active_bom.name)
			print "Group: \n", group
			for part in group.values():	# TODO: Ensure this data is what we expect
				groupName += part[2].name + ", "
			
			# Replace trailing comma with tab
			groupName = groupName[0:-2]
			self.populateBomRow(group[group.keys()[0]][2], rowNum, active_bom.prodCounts[prod])
			self.bomContentLabels[rowNum][0].set_label(groupName)
			self.attachBomRow(rowNum)
			rowNum += 1
			
	def setPartInfoLabels(self, prod):
		self.partInfoVendorLabel2.set_text(prod.vendor)
		self.partInfoVendorPNLabel2.set_text(prod.vendor_pn)
		self.partInfoInventoryLabel2.set_text(str(prod.inventory))
		self.partInfoManufacturerLabel2.set_text(prod.manufacturer)
		self.partInfoManufacturerPNLabel2.set_text(prod.mfg_pn)
		self.partInfoDescriptionLabel2.set_text(prod.description)
		self.partInfoDatasheetLabel2.set_text(prod.datasheet)
		self.partInfoCategoryLabel2.set_text(prod.category)
		self.partInfoFamilyLabel2.set_text(prod.family)
		self.partInfoSeriesLabel2.set_text(prod.series)
		self.partInfoPackageLabel2.set_text(prod.package)

	def clearPartInfoLabels(self):
		self.partInfoVendorLabel2.set_text("\t")
		self.partInfoVendorPNLabel2.set_text("\t")
		self.partInfoInventoryLabel2.set_text("\t")
		self.partInfoManufacturerLabel2.set_text("\t")
		self.partInfoManufacturerPNLabel2.set_text("\t")
		self.partInfoDescriptionLabel2.set_text("\t")
		self.partInfoDatasheetLabel2.set_text("\t")
		self.partInfoCategoryLabel2.set_text("\t")
		self.partInfoFamilyLabel2.set_text("\t")
		self.partInfoSeriesLabel2.set_text("\t")
		self.partInfoPackageLabel2.set_text("\t")
	
	def destroyPartPriceLabels(self):
		for r in self.priceBreakLabels:
			r.destroy()
			
		for r in self.unitPriceLabels:
			r.destroy()
			
		for r in self.extPriceLabels:
			r.destroy()
		
	def setPartPriceLabels(self, prod):
		n = len(prod.prices)
		print "n =", n
		k = sorted(prod.prices.keys())
		print "prod.prices = \n", prod.prices
		print "sorted(prod.prices.keys()) = \n", k
		self.partInfoPricingTable.resize(n+1, 3)
		self.destroyPartPriceLabels()
		
		self.priceBreakLabels.append(gtk.Label("Price Break"))
		self.unitPriceLabels.append(gtk.Label("Unit Price"))
		self.extPriceLabels.append(gtk.Label("Extended Price"))
		
		self.partInfoPricingTable.attach(self.priceBreakLabels[0],  0, 1, 0, 1)
		self.partInfoPricingTable.attach(self.unitPriceLabels[0],  1, 2, 0, 1)
		self.partInfoPricingTable.attach(self.extPriceLabels[0],  2, 3, 0, 1)
		
		# self.partInfoPricingTable.attach(self.priceBreakLabels[0],  i, i+1, row+1, row+2)
		rowNum = 1
		for i in range(n):
			#k[i] is a key of prod.prices()
			self.priceBreakLabels.append(gtk.Label(str(k[i])))
			self.priceBreakLabels[rowNum].set_alignment(0.5, 0.5)
			self.unitPriceLabels.append(gtk.Label(str(prod.prices[k[i]])))
			self.unitPriceLabels[rowNum].set_alignment(1.0, 0.5)
			self.extPriceLabels.append(gtk.Label(str( k[i] *  prod.prices[k[i]])))
			self.extPriceLabels[rowNum].set_alignment(1.0, 0.5)
			
			self.partInfoPricingTable.attach(self.priceBreakLabels[rowNum],  0, 1, rowNum, rowNum+1)
			self.partInfoPricingTable.attach(self.unitPriceLabels[rowNum],  1, 2, rowNum, rowNum+1)
			self.partInfoPricingTable.attach(self.extPriceLabels[rowNum],  2, 3, rowNum, rowNum+1)
			rowNum += 1
			
		self.window.show_all()
		
	def __init__(self):
		# -------- DECLARATIONS --------
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.mainBox = gtk.VBox(False, 0)
		self.menuBar = gtk.MenuBar()
		self.notebook = gtk.Notebook()
		self.bomTabLabel = gtk.Label("BOM Editor")
		self.dbTabLabel = gtk.Label("Product Database")
		
		self.bomTabBox = gtk.VBox(False, 0) # First tab in notebook
		self.bomToolbar = gtk.Toolbar()
		self.bomReadInputButton = gtk.ToolButton(None, "Read CSV")
		self.bomReadDBButton = gtk.ToolButton(None, "Read DB")
		self.bomSetProductButton = gtk.ToolButton(None, "Set Product")
		self.bomHPane = gtk.HPaned()	
		self.bomVPane = gtk.VPaned()	# Goes in right side of bomHPane
		
		self.bomFrame = gtk.Frame("BOM") # Goes in left side of bomHPane
		self.bomTableBox = gtk.VBox(False, 0) # Holds bomScrollWin and bomRadioBox
		self.bomScrollWin = gtk.ScrolledWindow() # Holds bomTable
		self.bomTable = gtk.Table(1, 8, False) 
		
		# first table row will be column labels
		self.bomColLabel1 = gtk.Label("Part")
		self.bomColLabel2 = gtk.Label("Value")
		self.bomColLabel3 = gtk.Label("Device")
		self.bomColLabel4 = gtk.Label("Package")
		self.bomColLabel5 = gtk.Label("Description")
		self.bomColLabel6 = gtk.Label("Part Number")
		self.bomColLabel7 = gtk.Label("Quantity")
		self.bomContentLabels = []
		self.bomRadioGroup = gtk.RadioButton(None)
		self.bomRadios = self.createBomRadios(0)
		
		self.bomRadioBox = gtk.HBox(False, 0)
		self.bomRadioLabel = gtk.Label("Group by:")
		self.bomGroupName = gtk.RadioButton(None, "Name")
		self.bomGroupValue = gtk.RadioButton(self.bomGroupName, "Value")
		self.bomGroupPN = gtk.RadioButton(self.bomGroupName, "Part Number")
		
		self.selectedProduct = Product(Product.VENDOR_DK, "init", urbmDB)
		self.selectedBomPart = bomPart("init", "init", "init", "init", active_bom)
		
		self.partInfoFrame = gtk.Frame("Part information") # Goes in top half of bomVPane
		self.partInfoRowBox = gtk.VBox(False, 20) # Fill with HBoxes 
		
		self.partInfoInfoTable = gtk.Table(11, 2, False) # Vendor, PNs, inventory, etc
		self.partInfoVendorLabel1 = gtk.Label("Vendor: ")
		self.partInfoVendorLabel2 = gtk.Label(None)
		self.partInfoVendorPNLabel1 = gtk.Label("Vendor Part Number: ")
		self.partInfoVendorPNLabel2 = gtk.Label(None)
		self.partInfoInventoryLabel1 = gtk.Label("Inventory: ")
		self.partInfoInventoryLabel2 = gtk.Label(None)
		self.partInfoManufacturerLabel1 = gtk.Label("Manufacturer: ")
		self.partInfoManufacturerLabel2 = gtk.Label(None)
		self.partInfoManufacturerPNLabel1 = gtk.Label("Manufacturer Part Number: ")
		self.partInfoManufacturerPNLabel2 = gtk.Label(None)
		self.partInfoDescriptionLabel1 = gtk.Label("Description: ")
		self.partInfoDescriptionLabel2 = gtk.Label(None)
		self.partInfoDatasheetLabel1 = gtk.Label("Datasheet filename: ")
		self.partInfoDatasheetLabel2 = gtk.Label(None)
		self.partInfoCategoryLabel1 = gtk.Label("Category: ")
		self.partInfoCategoryLabel2 = gtk.Label(None)
		self.partInfoFamilyLabel1 = gtk.Label("Family: ")
		self.partInfoFamilyLabel2 = gtk.Label(None)
		self.partInfoSeriesLabel1 = gtk.Label("Series: ")
		self.partInfoSeriesLabel2 = gtk.Label(None)
		self.partInfoPackageLabel1 = gtk.Label("Package/case: ")
		self.partInfoPackageLabel2 = gtk.Label(None)
		
		self.partInfoPricingTable = gtk.Table(8, 3 , False) # Price breaks
		self.priceBreakLabels = []
		#for i in range(10):
		#	self.priceBreakLabels.append(gtk.Label(None))
		
		self.unitPriceLabels = []
		#for i in range(10):
		#	self.unitPriceLabels.append(gtk.Label(None))
		
		self.extPriceLabels = []
		#for i in range(10):
		#	self.extPriceLabels.append(gtk.Label(None))
		
		self.partInfoButtonBox = gtk.HBox(False, 0)

		self.scrapeButton = gtk.Button("Scrape", stock=gtk.STOCK_REFRESH)
		self.partDatasheetButton = gtk.Button("Datasheet", stock=gtk.STOCK_PROPERTIES)
		
		self.pricingFrame = gtk.Frame("Project pricing") # Goes in bottom half of bomVPane
		self.orderSizeScaleAdj = gtk.Adjustment(1, 1, 10000, 1, 10, 200)
		self.orderSizeScale = gtk.HScale(self.orderSizeScaleAdj)
		self.orderSizeText = gtk.Entry(10000)
		
		self.dbBox = gtk.VBox(False, 0) # Second tab in notebook
		self.dbToolbar = gtk.Toolbar()
		self.dbFrame = gtk.Frame("Product database") 
		self.dbScrollWin = gtk.ScrolledWindow()
		self.dbTable = gtk.Table(50, 6, False)
		self.dbVendorLabel = gtk.Label("Vendor")
		self.dbVendorPNLabel = gtk.Label("Vendor Part Number")
		self.dbInventoryLabel = gtk.Label("Inventory")
		self.dbManufacturerLabel = gtk.Label("Manufacturer")
		self.dbManufacturerPNLabel = gtk.Label("Manufacturer Part Number")
		self.dbDescriptionLabel = gtk.Label("Description")
		self.dbDatasheetLabel = gtk.Label("Datasheet filename")
		self.dbCategoryLabel = gtk.Label("Category")
		self.dbFamilyLabel = gtk.Label("Family")
		self.dbSeriesLabel = gtk.Label("Series")
		self.dbPackageLabel = gtk.Label("Package/case")
		
		# -------- CONFIGURATION --------
		self.window.set_title("Unified Robotics BOM Manager") 
		# TODO: Add project name to window title on file open
		self.window.connect("delete_event", self.delete_event)
		self.window.connect("destroy", self.destroy)
		
		self.notebook.set_tab_pos(gtk.POS_TOP)
		self.notebook.append_page(self.bomTabBox, self.bomTabLabel)
		self.notebook.append_page(self.dbBox, self.dbTabLabel)
		self.notebook.set_show_tabs(True)
		
		self.bomReadInputButton.connect("clicked", self.readInputCallback, "read")
		self.bomReadDBButton.connect("clicked", self.readDBCallback, "read")
		self.bomSetProductButton.connect("clicked", self.bomSetProductCallback, "setPN")
		self.bomScrollWin.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		
		self.dbScrollWin.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		
		self.bomGroupName.connect("toggled", self.bomGroupCallback, "name")
		self.bomGroupValue.connect("toggled", self.bomGroupCallback, "value")
		self.bomGroupPN.connect("toggled", self.bomGroupCallback, "product")
		
		self.partInfoVendorLabel1.set_alignment(0.0, 0.5)
		self.partInfoVendorLabel2.set_alignment(1.0, 0.5)
		self.partInfoVendorPNLabel1.set_alignment(0.0, 0.5)
		self.partInfoVendorPNLabel2.set_alignment(1.0, 0.5)
		self.partInfoInventoryLabel1.set_alignment(0.0, 0.5)
		self.partInfoInventoryLabel2.set_alignment(1.0, 0.5)
		self.partInfoManufacturerLabel1.set_alignment(0.0, 0.5)
		self.partInfoManufacturerLabel2.set_alignment(1.0, 0.5)
		self.partInfoManufacturerPNLabel1.set_alignment(0.0, 0.5)
		self.partInfoManufacturerPNLabel2.set_alignment(1.0, 0.5)
		self.partInfoDescriptionLabel1.set_alignment(0.0, 0.5)
		self.partInfoDescriptionLabel2.set_alignment(1.0, 0.5)
		self.partInfoDatasheetLabel1.set_alignment(0.0, 0.5)
		self.partInfoDatasheetLabel2.set_alignment(1.0, 0.5)
		self.partInfoCategoryLabel1.set_alignment(0.0, 0.5)
		self.partInfoCategoryLabel2.set_alignment(1.0, 0.5)
		self.partInfoFamilyLabel1.set_alignment(0.0, 0.5)
		self.partInfoFamilyLabel2.set_alignment(1.0, 0.5)
		self.partInfoSeriesLabel1.set_alignment(0.0, 0.5)
		self.partInfoSeriesLabel2.set_alignment(1.0, 0.5)
		self.partInfoPackageLabel1.set_alignment(0.0, 0.5)
		self.partInfoPackageLabel2.set_alignment(1.0, 0.5)
		
		# -------- PACKING AND ADDING --------
		self.mainBox.pack_start(self.menuBar)
		self.mainBox.pack_start(self.notebook)
		self.window.add(self.mainBox)
		
		self.bomTabBox.pack_start(self.bomToolbar)
		self.bomToolbar.insert(self.bomReadInputButton, 0)
		self.bomToolbar.insert(self.bomReadDBButton, 1)
		self.bomToolbar.insert(self.bomSetProductButton, 2)
		#self.bomTabBox.pack_start(self.bomReadInputButton)
		
		# TODO : Add toolbar elements
		
		self.bomTabBox.pack_start(self.bomHPane)
		self.bomHPane.pack1(self.bomFrame, True, True)
		self.bomHPane.add2(self.bomVPane)
		self.bomVPane.add1(self.partInfoFrame)
		self.bomVPane.add2(self.pricingFrame)
		
		# BOM Frame elements
		self.bomFrame.add(self.bomTableBox)
		
		self.bomTableBox.pack_start(self.bomScrollWin, True, True, 0)
		self.bomScrollWin.add_with_viewport(self.bomTable)
		self.bomTableBox.pack_end(self.bomRadioBox, False, False, 0)

		self.bomTable.set_col_spacings(10)
		self.bomTableHeaders()
		self.attachBomRadios()
		# The following commented lines are kept (for now) as a reference for
		# how to display the BOM in the table
		#self.testRadio1 = gtk.RadioButton(None)
		#self.aLabel1 = gtk.Label("R1")
		#self.aLabel2 = gtk.Label("10k")
		#self.testRadio2 = gtk.RadioButton(self.testRadio1)
		#self.bLabel1 = gtk.Label("C1")
		#self.bLabel2 = gtk.Label("10 uF")
		#self.bomTable.attach(self.testRadio1, 0, 7, 1, 2)
		#self.bomTable.attach(self.aLabel1, 0, 1, 1, 2)
		#self.bomTable.attach(self.aLabel2, 1, 2, 1, 2)
		#self.bomTable.attach(self.testRadio2, 0, 7, 2, 3)
		#self.bomTable.attach(self.bLabel1, 0, 1, 2, 3)
		#self.bomTable.attach(self.bLabel2, 1, 2, 2, 3)
		
		self.bomRadioBox.pack_start(self.bomRadioLabel)
		self.bomRadioBox.pack_start(self.bomGroupName)
		self.bomRadioBox.pack_start(self.bomGroupValue)
		self.bomRadioBox.pack_start(self.bomGroupPN)
		
		# Part info frame elements
		self.partInfoFrame.add(self.partInfoRowBox)
		self.partInfoRowBox.pack_start(self.partInfoInfoTable)
		self.partInfoInfoTable.attach(self.partInfoVendorLabel1, 0, 1, 0, 1)
		self.partInfoInfoTable.attach(self.partInfoVendorPNLabel1, 0, 1, 1, 2)
		self.partInfoInfoTable.attach(self.partInfoInventoryLabel1, 0, 1, 2, 3)
		self.partInfoInfoTable.attach(self.partInfoManufacturerLabel1, 0, 1, 3, 4)
		self.partInfoInfoTable.attach(self.partInfoManufacturerPNLabel1, 0, 1, 4, 5)
		self.partInfoInfoTable.attach(self.partInfoDescriptionLabel1, 0, 1, 5, 6)
		self.partInfoInfoTable.attach(self.partInfoDatasheetLabel1, 0, 1, 6, 7)
		self.partInfoInfoTable.attach(self.partInfoCategoryLabel1, 0, 1, 7, 8)
		self.partInfoInfoTable.attach(self.partInfoFamilyLabel1, 0, 1, 8, 9)
		self.partInfoInfoTable.attach(self.partInfoSeriesLabel1, 0, 1, 9, 10)
		self.partInfoInfoTable.attach(self.partInfoPackageLabel1, 0, 1, 10, 11)
		
		self.partInfoInfoTable.attach(self.partInfoVendorLabel2, 1, 2, 0, 1)
		self.partInfoInfoTable.attach(self.partInfoVendorPNLabel2, 1, 2, 1, 2)
		self.partInfoInfoTable.attach(self.partInfoInventoryLabel2, 1, 2, 2, 3)
		self.partInfoInfoTable.attach(self.partInfoManufacturerLabel2, 1, 2, 3, 4)
		self.partInfoInfoTable.attach(self.partInfoManufacturerPNLabel2, 1, 2, 4, 5)
		self.partInfoInfoTable.attach(self.partInfoDescriptionLabel2, 1, 2, 5, 6)
		self.partInfoInfoTable.attach(self.partInfoDatasheetLabel2, 1, 2, 6, 7)
		self.partInfoInfoTable.attach(self.partInfoCategoryLabel2, 1, 2, 7, 8)
		self.partInfoInfoTable.attach(self.partInfoFamilyLabel2, 1, 2, 8, 9)
		self.partInfoInfoTable.attach(self.partInfoSeriesLabel2, 1, 2, 9, 10)
		self.partInfoInfoTable.attach(self.partInfoPackageLabel2, 1, 2, 10, 11)
		
		for i in range(len(self.priceBreakLabels)):
			self.partInfoPricingTable.attach(self.priceBreakLabels[i], 0, 1, i, i+1)
			self.priceBreakLabels[i].set_alignment(0.5, 0.5)
			
		for i in range(len(self.unitPriceLabels)):
			self.partInfoPricingTable.attach(self.unitPriceLabels[i], 1, 2, i, i+1)
			self.unitPriceLabels[i].set_alignment(1.0, 0.5)
			
		for i in range(len(self.extPriceLabels)):
			self.partInfoPricingTable.attach(self.extPriceLabels[i], 2, 3, i, i+1)
			self.extPriceLabels[i].set_alignment(1.0, 0.5)
			
		self.partInfoRowBox.pack_start(self.partInfoPricingTable)
		self.partInfoRowBox.pack_start(self.partInfoButtonBox)
		
		self.dbBox.pack_start(self.dbToolbar)
		self.dbBox.pack_start(self.dbFrame)
		self.dbFrame.add(self.dbScrollWin)
		self.dbScrollWin.add_with_viewport(self.dbTable)
		self.dbTable.attach(self.dbVendorLabel, 0, 1, 0, 1)
		self.dbTable.attach(self.dbVendorPNLabel, 1, 2, 0, 1)
		self.dbTable.attach(self.dbInventoryLabel, 2, 3, 0, 1)
		self.dbTable.attach(self.dbManufacturerLabel, 3, 4, 0, 1)
		self.dbTable.attach(self.dbManufacturerPNLabel, 4, 5, 0, 1)
		self.dbTable.attach(self.dbDescriptionLabel, 5, 6, 0, 1)
		self.dbTable.attach(self.dbDatasheetLabel, 6, 7, 0, 1)
		self.dbTable.attach(self.dbCategoryLabel, 7, 8, 0, 1)
		self.dbTable.attach(self.dbFamilyLabel, 8, 9, 0, 1)
		self.dbTable.attach(self.dbSeriesLabel, 9, 10, 0, 1)
		self.dbTable.attach(self.dbPackageLabel, 10, 11, 0, 1)
		self.dbTable.set_col_spacings(10)
		
		# Show everything
		self.mainBox.show_all()
		self.window.show()
def main():
	gtk.main()
	
if __name__ == "__main__":
	URBM()
	main()
