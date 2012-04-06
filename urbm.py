import csv
import pygtk
pygtk.require('2.0')
import gtk
import y_serial_v060 as y_serial
import shutil
import os
import sqlite3
import types
from urbm_product import Product
from urbm_bompart import bomPart
from urbm_bom import BOM
import gobject

urbmDB = y_serial.Main(os.path.join(os.getcwd(), "urbm.sqlite"))
urbmDB.createtable('products')
#activeProjectName = 'test1'
inputFile = os.path.join(os.getcwd(), "test.csv")	# TODO: Test dummy

#active_bom = BOM("test1", 'Test BOM 1', urbmDB, os.path.join(os.getcwd(), "test.csv"))

def getProductDBSize():
	dict = urbmDB.selectdic("?", 'products')

''' Returns a list of BOM project tables in the DB. '''
def listProjects():
	conn = sqlite3.connect("urbm.sqlite")
	cur = conn.cursor()
	projects = []
	a = "SELECT name FROM sqlite_master"
	b = "WHERE type='table' AND name IS NOT 'products' OR 'dummy'"
	c = "ORDER BY name"
	sql = ' '.join( [a, b, c] )
	cur.execute(sql)
	answer = cur.fetchall()
	cur.close()
	conn.close()
	for p in answer:
		projects.append(p[0])
	return projects


class URBM(gobject.GObject):
	'''Main GUI class'''
	def delete_event(self, widget, event, data=None):
		print "delete event occurred"
		return False
		
	def destroy(self, widget, data=None):
		gtk.main_quit()

	# -------- CALLBACK METHODS --------
	''' Callback for the input file Open dialog in the New Project dialog. '''
	def newProjectInputFileCallback(self, widget, data=None):
		self.inputFileDialog.run()
		self.inputFileDialog.hide()
		self.newProjectInputFileEntry.set_text(self.inputFileDialog.get_filename())
	
	'''Callback for the New Project button. '''
	def projectNewCallback(self, widget, data=None):
		response = self.newProjectDialog.run()
		self.newProjectDialog.hide()
		newName = self.newProjectNameEntry.get_text()
		curProjects = listProjects()
		if newName in curProjects:
			print 'Error: Name in use!'
			self.projectNameTakenDialog.run()
			self.projectNameTakenDialog.hide()
		elif response == gtk.RESPONSE_ACCEPT: 
			# Create project
			print 'Creating new project'
			new = BOM(newName, self.newProjectDescriptionEntry.get_text(), urbmDB, self.newProjectInputFileEntry.get_text())
			new.writeToDB()
			self.projectStorePopulate()
		self.newProjectNameEntry.set_text('')
		self.newProjectDescriptionEntry.set_text('')
		#self.newProjectDatabaseFileEntry.set_text('')
		self.newProjectInputFileEntry.set_text('')
		
	def projectOpenCallback(self, widget, data=None):
		(model, rowIter) = self.projectTreeView.get_selection().get_selected()
		self.active_bom = BOM.readFromDB(urbmDB, model.get(rowIter,0)[0])
		self.activeProjectName = model.get(rowIter,0)[0]
		inputFile = model.get(rowIter,3)[0]
		print self.active_bom, type(self.active_bom)
		print 'Project name: ', self.activeProjectName
		print 'Project CSV: ', inputFile
		if self.bomGroupName.get_active():
			self.bomStorePopulateByName()
		elif self.bomGroupValue.get_active():
			self.bomStorePopulateByVal()
		elif self.bomGroupPN.get_active():
			self.bomStorePopulateByPN()
			
		self.bomTreeView.columns_autosize()
		self.window.show_all()
		
	'''Callback for the "Read CSV" button on the BOM tab.'''
	def readInputCallback(self, widget, data=None):
		self.active_bom.readFromFile()
		#Read back last entry
		urbmDB.view(1, self.active_bom.name)
		if self.bomGroupName.get_active():
			self.bomStorePopulateByName()
		elif self.bomGroupValue.get_active():
			self.bomStorePopulateByValue()
		elif self.bomGroupPN.get_active():
			self.bomStorePopulateByPN()
		self.window.show_all()
	
	'''Callback for the "Read DB" button on the BOM tab.'''
	def bomReadDBCallback(self, widget, data=None):
		print "Read DB callback"
		print 'Project name: ', self.activeProjectName
		self.active_bom = BOM.readFromDB(urbmDB, self.activeProjectName)
		if self.bomGroupName.get_active():
			self.bomStorePopulateByName()
		elif self.bomGroupValue.get_active():
			self.bomStorePopulateByVal()
		elif self.bomGroupPN.get_active():
			self.bomStorePopulateByPN()
		self.window.show_all()
	
	'''Callback method triggered when a BOM line item is selected.'''
	def bomSelectionCallback(self, widget, data=None):
		# Set class fields for currently selected item
		(model, rowIter) = self.bomTreeView.get_selection().get_selected()
		#print 'rowIter is: ', rowIter, '\n'
		#print 'model.get(rowIter,0)[0] is: ', model.get(rowIter,0)[0]
		self.selectedBomPart = urbmDB.select(model.get(rowIter,0)[0], self.active_bom.name)
		# Grab the vendor part number for the selected item from the label text
		selectedPN = model.get(rowIter,5)[0]
		print "selectedPN is: %s" % selectedPN
		if selectedPN != "none": # Look up part in DB
			# Set class field for currently selected product
			print "Querying with selectedPN: %s" % selectedPN
			self.bomSelectedProduct.manufacturer_pn = selectedPN
			
			self.bomSelectedProduct.selectOrScrape()
			#self.bomSelectedProduct.show()
			self.setPartInfoLabels(self.bomSelectedProduct)
			self.setPartInfoListingCombo(self.bomSelectedProduct)
			self.destroyPartPriceLabels()
			print 'self.bomSelectedProduct.vendorProds: \n', self.bomSelectedProduct.vendorProds
			if type(self.partInfoListingCombo.get_active_text()) is not types.NoneType and self.partInfoListingCombo.get_active_text() != '':
				self.setPartPriceLabels(self.bomSelectedProduct.vendorProds[self.partInfoListingCombo.get_active_text()])
		else:
			self.setPartInfoListingCombo()
			self.destroyPartPriceLabels()
			self.clearPartInfoLabels()
	
	'''Callback method activated by the BOM grouping radio buttons.
	Redraws the BOM TreeView with the approporiate goruping for the selected radio.'''
	def bomGroupCallback(self, widget, data=None):
		#print "%s was toggled %s" % (data, ("OFF", "ON")[widget.get_active()])
		
		# Figure out which button is now selected
		if widget.get_active():
			if 'name' in data:
				self.bomStorePopulateByName()
				
			elif 'value' in data:
				self.bomStorePopulateByVal()
					
			elif 'product' in data:
				self.bomStorePopulateByPN()
					
			self.window.show_all()
	
	'''Callback method activated by clicking a BOM column header.
	Sorts the BOM TreeView by the values in the clicked column.'''
	def bomSortCallback(self, widget):
		print widget.get_sort_order()
		widget.set_sort_column_id(0)
		# TODO: On sorting by a different column, the indicator does not go away
		# This may be because with the current test set, the other columns are still technically sorted
	
	'''Callback method for the "Edit Part" button in the BOM tab.
	Opens a dialog window with form fields for each BOM Part object field.'''
	def bomEditPartCallback(self, widget, data=None):
		# Open a text input prompt window
		editPartDialog = gtk.Dialog("Edit part", self.window, 
						gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, 
						gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		
		# -------- DECLARATIONS --------
		# Field labels
		editPartNameLabel = gtk.Label("Name: ")
		editPartValueLabel = gtk.Label("Value: ")
		editPartDeviceLabel = gtk.Label("Device: ")
		editPartPackageLabel = gtk.Label("Package: ")
		editPartDescriptionLabel = gtk.Label("Description: ")
		editPartManufacturerLabel = gtk.Label("Manufacturer: ")
		editPartManufacturerPNLabel = gtk.Label("Manufacturer Part Number: ")
		
		# Field entry elements
		self.editPartNameEntry = gtk.Entry()
		self.editPartValueEntry = gtk.Entry()
		self.editPartDeviceEntry = gtk.Entry()
		self.editPartPackageEntry = gtk.Entry()
		self.editPartDescriptionEntry = gtk.Entry()
		self.editPartProductEntry = gtk.Entry()
		
		#editPartVendorCombo = gtk.combo_box_new_text()
		#editPartVendorCombo.append_text(Product.VENDOR_DK)
		#editPartVendorCombo.append_text(Product.VENDOR_FAR)
		#editPartVendorCombo.append_text(Product.VENDOR_FUE)
		#editPartVendorCombo.append_text(Product.VENDOR_JAM)
		#editPartVendorCombo.append_text(Product.VENDOR_ME)
		#editPartVendorCombo.append_text(Product.VENDOR_NEW)
		#editPartVendorCombo.append_text(Product.VENDOR_SFE)
		
		# Return values
		self.productEntryText = ""
		
		# HBoxes
		editPartDialogNameHBox = gtk.HBox()
		editPartDialogValueHBox = gtk.HBox()
		editPartDialogDeviceHBox = gtk.HBox()
		editPartDialogPackageHBox = gtk.HBox()
		editPartDialogDescriptionHBox = gtk.HBox()
		editPartDialogManufacturerHBox = gtk.HBox()
		editPartDialogManufacturerPNHBox = gtk.HBox()
		
		# -------- CONFIGURATION --------
		# Label alignment
		editPartNameLabel.set_alignment(0.0, 0.5)
		editPartValueLabel.set_alignment(0.0, 0.5)
		editPartDeviceLabel.set_alignment(0.0, 0.5)
		editPartPackageLabel.set_alignment(0.0, 0.5)
		editPartDescriptionLabel.set_alignment(0.0, 0.5)
		editPartManufacturerLabel.set_alignment(0.0, 0.5)
		editPartManufacturerPNLabel.set_alignment(0.0, 0.5)
		
		# Set default text of entry fields to current part values
		self.editPartNameEntry.set_text(self.selectedBomPart.name)
		self.editPartValueEntry.set_text(self.selectedBomPart.value)
		self.editPartDeviceEntry.set_text(self.selectedBomPart.device)
		self.editPartPackageEntry.set_text(self.selectedBomPart.package)
		self.editPartDescriptionEntry.set_text(self.selectedBomPart.description)
		self.editPartProductEntry.set_text(self.selectedBomPart.product)
		
		# Pack labels/entry fields into HBoxes
		editPartDialogNameHBox.pack_start(editPartNameLabel, False, True, 0)
		editPartDialogNameHBox.pack_end(self.editPartNameEntry, False, True, 0)
		
		editPartDialogValueHBox.pack_start(editPartValueLabel, False, True, 0)
		editPartDialogValueHBox.pack_end(self.editPartValueEntry, False, True, 0)
		
		editPartDialogDeviceHBox.pack_start(editPartDeviceLabel, False, True, 0)
		editPartDialogDeviceHBox.pack_end(self.editPartDeviceEntry, False, True, 0)
		
		editPartDialogPackageHBox.pack_start(editPartPackageLabel, False, True, 0)
		editPartDialogPackageHBox.pack_end(self.editPartPackageEntry, False, True, 0)
		
		editPartDialogDescriptionHBox.pack_start(editPartDescriptionLabel, False, True, 0)
		editPartDialogDescriptionHBox.pack_end(self.editPartDescriptionEntry, False, True, 0)
		
		#editPartDialogManufacturerHBox.pack_start(editPartManufacturerLabel, True, True, 0)
		#editPartDialogManufacturerHBox.pack_end(editPartVendorCombo, True, True, 0)
		
		editPartDialogManufacturerPNHBox.pack_start(editPartManufacturerPNLabel, True, True, 0)
		editPartDialogManufacturerPNHBox.pack_end(self.editPartProductEntry, gtk.RESPONSE_ACCEPT)
		
		# Pack HBoxes into vbox
		editPartDialog.vbox.set_spacing(1)
		editPartDialog.vbox.pack_start(editPartDialogNameHBox, True, True, 0)
		editPartDialog.vbox.pack_start(editPartDialogValueHBox, True, True, 0)
		editPartDialog.vbox.pack_start(editPartDialogDeviceHBox, True, True, 0)
		editPartDialog.vbox.pack_start(editPartDialogPackageHBox, True, True, 0)
		editPartDialog.vbox.pack_start(editPartDialogDescriptionHBox, True, True, 0)
		#editPartDialog.vbox.pack_start(editPartDialogManufacturerHBox, True, True, 0)
		editPartDialog.vbox.pack_start(editPartDialogManufacturerPNHBox, True, True, 0)
		
		# Show everything
		editPartDialog.vbox.show_all()
		response = editPartDialog.run()
		editPartDialog.hide()
		
		if response == gtk.RESPONSE_ACCEPT:
			# If the product text entry field is left blank, set the product to "none"
			if type(self.editPartProductEntry.get_text()) is types.NoneType or len(self.editPartProductEntry.get_text()) == 0:
				self.productEntryText = "none"
			else:
				self.productEntryText = self.editPartProductEntry.get_text()
			
			# Set selectedBomPart
			# TODO: If grouping by value or PN, what to do? Grey out the name field?
			# It should write the rest to ALL of the parts in the row
			self.selectedBomPart.name = self.editPartNameEntry.get_text()
			self.selectedBomPart.value = self.editPartValueEntry.get_text()
			self.selectedBomPart.device = self.editPartDeviceEntry.get_text()
			self.selectedBomPart.package = self.editPartPackageEntry.get_text()
			self.selectedBomPart.description = self.editPartDescriptionEntry.get_text()
			print "Setting selectedBomPart.product to: %s" % self.editPartProductEntry.get_text()
			self.selectedBomPart.product = self.productEntryText
			print "selectedBomPart's product field: %s" % self.selectedBomPart.product
			
			# Make sure the user selected a vendor
			# If not, default to Digikey for now
			# TODO: If a product was previously set, default to the current vendor
			# TODO: Can this be a "required field" that will prevent the OK button 
			# from working (greyed out) if a part number is also entered?
			#if type(editPartVendorCombo.get_active_text()) is types.NoneType:
			#	print "NoneType caught"
			#	self.bomSelectedProduct.vendor = Product.VENDOR_DK
			#else:	
			#	self.bomSelectedProduct.vendor = editPartVendorCombo.get_active_text()
			
			self.selectedBomPart.writeToDB()
			self.active_bom.updateParts(self.selectedBomPart)
			
			if self.bomGroupName.get_active():
				self.bomStorePopulateByName()
			elif self.bomGroupValue.get_active():
				self.bomStorePopulateByVal()
			elif self.bomGroupPN.get_active():
				self.bomStorePopulateByPN()
					
			self.bomSelectedProduct.manufacturer_pn = self.productEntryText
			self.bomSelectedProduct.selectOrScrape()
			# TODO: The following commented out lines need to be redone
			# for the new Product model
			if self.bomSelectedProduct.manufacturer_pn == "none":
				pass
				#self.clearPartInfoLabels()
				#self.destroyPartPriceLabels()
			else:
				pass
				#self.setPartInfoLabels(self.bomSelectedProduct)
				#self.setPartPriceLabels(self.bomSelectedProduct)
	
	def partInfoScrapeButtonCallback(self, widget):
		''' Part info frame "Refresh" button callback. '''
		self.bomSelectedProduct.scrape()
	
	def partInfoListingComboCallback(self, widget, data=None):
		self.destroyPartPriceLabels()
		if type(self.partInfoListingCombo.get_active_text()) is not types.NoneType and self.partInfoListingCombo.get_active_text() != '':
			self.setPartPriceLabels(self.bomSelectedProduct.vendorProds[self.partInfoListingCombo.get_active_text()])
	
	''' Clear self.dbProductStore and repopulate it. '''
	def dbStorePopulate(self):
		self.dbProductStore.clear()
		#prodsDict = urbmDB.selectdic("*", "products")
		prodsDict = urbmDB.selectdic("#prod", "products")
		
		for p in prodsDict.values():
			# p[2] is a Product object from the DB
			iter = self.dbProductStore.append([p[2].manufacturer, p[2].manufacturer_pn, p[2].description, p[2].datasheet, p[2].package])
			#iter = self.dbProductStore.append([p[2].vendor, p[2].vendor_pn, p[2].inventory, p[2].manufacturer, p[2].manufacturer_pn, p[2].description, p[2].datasheet, p[2].category, p[2].family, p[2].series, p[2].package])
		self.dbTreeView.columns_autosize()
	
	'''Callback for the "Read DB" button on the product DB tab.'''
	def dbReadDBCallback(self, widget, data=None):
		print "Read DB callback"
		self.dbStorePopulate()
	
	'''Callback method triggered when a product DB item is selected.'''
	def dbSelectionCallback(self, widget, data=None):
		# Set class fields for currently selected item
		(model, rowIter) = self.dbTreeView.get_selection().get_selected()
		self.dbSelectedProduct = urbmDB.select(model.get(rowIter,0)[0], "products")
	
	'''Callback method activated by clicking a DB column header.
	Sorts the DB TreeView by the values in the clicked column.'''
	def dbSortCallback(self, widget):
		widget.set_sort_column_id(0)
	 
	# -------- HELPER METHODS --------
	def projectStorePopulate(self):
		self.projectStore.clear()
		# Columns: Name, Description, Database, Input File
		projectsList = listProjects()
		#print 'projectsList: ', projectsList
		for p in projectsList:
			if type(p) is types.NoneType:
				print 'NoneType caught in projectsList'
			elif p != 'dummy':
				bom = BOM.readFromDB(urbmDB, p)
				iter = self.projectStore.append([bom.name, bom.description, urbmDB.db, bom.input])
		self.projectTreeView.columns_autosize()
	
	def bomStorePopulateByName(self):
		''' Clear self.bomStore and repopulate it, grouped by name. '''
		self.bomStore.clear()
		for p in self.active_bom.parts:
			temp = urbmDB.select(p[0], self.active_bom.name)
			iter = self.bomStore.append([temp.name, temp.value, temp.device, temp.package, temp.description, temp.product, 1])
		
		self.bomTreeView.columns_autosize()
	
	def bomStorePopulateByVal(self):
		''' Clear self.bomStore and repopulate it, grouped by value. '''
		self.bomStore.clear()
		self.active_bom.sortByVal()
		self.active_bom.setValCounts()
		
		for val in self.active_bom.valCounts.keys():
			groupName = "\t"	# Clear groupName and prepend a tab
			# TODO: Does this split up parts of the same value but different package?
			# If not, the "part number" column will be bad
			group = urbmDB.selectdic("#val=" + val, self.active_bom.name)
			for part in group.values():
				groupName += part[2].name + ", "
			
			# Replace trailing comma with tab
			groupName = groupName[0:-2]
			temp = group[group.keys()[0]][2]	# Part object
			iter = self.bomStore.append([groupName, temp.value, temp.device, temp.package, temp.description, temp.product, self.active_bom.valCounts[val]])
		
		self.bomTreeView.columns_autosize()
	
	def bomStorePopulateByPN(self):
		''' Clear self.bomStore and repopulate it, grouped by part number. '''	
		self.bomStore.clear()
		self.active_bom.sortByProd()
		self.active_bom.setProdCounts()
		
		for prod in self.active_bom.prodCounts.keys():
			groupName = "\t"	# Clear groupName and prepend a tab
			print "Querying with prod =", prod, " of length ", len(prod)
			# Catch empty product string
			if prod == ' ' or len(prod) == 0: 
				print "Caught empty product"
				group = urbmDB.selectdic("#prod=none", self.active_bom.name)
			else:
				group = urbmDB.selectdic("#prod=" + prod, self.active_bom.name)
			print "Group: \n", group
			for part in group.values():	# TODO: Ensure this data is what we expect
				groupName += part[2].name + ", "
			
			# Replace trailing comma with tab
			groupName = groupName[0:-2]
			
			temp = group[group.keys()[0]][2]	# Part object
			iter = self.bomStore.append([groupName, temp.value, temp.device, temp.package, temp.description, temp.product, self.active_bom.prodCounts[prod]])
		
		self.bomTreeView.columns_autosize()
	
	def setPartInfoLabels(self, prod):
		'''Set the Part Information pane fields based on the fields of a given 
		product object.'''	
		#self.partInfoVendorLabel2.set_text(prod.vendor)
		#self.partInfoVendorPNLabel2.set_text(prod.vendor_pn)
		#self.partInfoInventoryLabel2.set_text(str(prod.inventory))
		self.partInfoManufacturerLabel2.set_text(prod.manufacturer)
		self.partInfoManufacturerPNLabel2.set_text(prod.manufacturer_pn)
		self.partInfoDescriptionLabel2.set_text(prod.description)
		self.partInfoDatasheetLabel2.set_text(prod.datasheet)
		#self.partInfoCategoryLabel2.set_text(prod.category)
		#self.partInfoFamilyLabel2.set_text(prod.family)
		#self.partInfoSeriesLabel2.set_text(prod.series)
		self.partInfoPackageLabel2.set_text(prod.package)

	def clearPartInfoLabels(self):
		'''Clears the Part Information pane fields, setting the text of each Label
		object to a tab character.'''
		#self.partInfoVendorLabel2.set_text("\t")
		#self.partInfoVendorPNLabel2.set_text("\t")
		#self.partInfoInventoryLabel2.set_text("\t")
		self.partInfoManufacturerLabel2.set_text("\t")
		self.partInfoManufacturerPNLabel2.set_text("\t")
		self.partInfoDescriptionLabel2.set_text("\t")
		self.partInfoDatasheetLabel2.set_text("\t")
		#self.partInfoCategoryLabel2.set_text("\t")
		#self.partInfoFamilyLabel2.set_text("\t")
		#self.partInfoSeriesLabel2.set_text("\t")
		self.partInfoPackageLabel2.set_text("\t")
	
	def setPartInfoListingCombo(self, prod=None):
		''' Populates self.partInfoListingCombo with vendorProduct listings
		for the selected Product. '''
		print 'Setting Listing combo...'
		self.partInfoListingCombo.get_model().clear()
		
		if type(prod) is not types.NoneType and prod.manufacturer_pn != "none":
			for listing in prod.vendorProds.values():
				#print 'Listing: ', type(listing), listing
				title = listing.vendor + ': ' + listing.vendorPN# + ' (' + listing.packaging + ')'
				#print 'Appending combo title: ', title
				self.partInfoListingCombo.append_text(title)
		
		# TODO: Set default active to user-selected listing
		# If the user has not chosen one, that defaults to prod.bestListing
		self.partInfoListingCombo.set_active(0)
		self.partInfoRowBox.show_all()
	
	def destroyPartPriceLabels(self):
		for r in self.priceBreakLabels:
			r.destroy()
			
		for r in self.unitPriceLabels:
			r.destroy()
			
		for r in self.extPriceLabels:
			r.destroy()
			
		del self.priceBreakLabels[:]
		del self.unitPriceLabels[:]
		del self.extPriceLabels[:]
		
	def setPartPriceLabels(self, vprod):
		''' Given a vendorProduct listing, sets the pricing table labels. '''
		n = len(vprod.prices)
		#print "n =", n
		priceKeys = sorted(vprod.prices.keys())
		#print "vprod.prices = \n", vprod.prices
		#print "sorted(vprod.prices.keys()) = \n", priceKeys
		self.partInfoPricingTable.resize(n+1, 3)
		self.destroyPartPriceLabels()
		
		self.priceBreakLabels.append(gtk.Label("Price Break"))
		self.unitPriceLabels.append(gtk.Label("Unit Price"))
		self.extPriceLabels.append(gtk.Label("Extended Price"))
		
		self.partInfoPricingTable.attach(self.priceBreakLabels[0],  0, 1, 0, 1)
		self.partInfoPricingTable.attach(self.unitPriceLabels[0],  1, 2, 0, 1)
		self.partInfoPricingTable.attach(self.extPriceLabels[0],  2, 3, 0, 1)
		
		rowNum = 1
		for i in range(n):
			#priceKeys[i] is a key of vprod.prices()
			self.priceBreakLabels.append(gtk.Label(str(priceKeys[i]) + '   '))
			self.priceBreakLabels[rowNum].set_alignment(0.5, 0.5)
			self.unitPriceLabels.append(gtk.Label(str(vprod.prices[priceKeys[i]]) + '   '))
			self.unitPriceLabels[rowNum].set_alignment(1.0, 0.5)
			self.extPriceLabels.append(gtk.Label(str( priceKeys[i] *  vprod.prices[priceKeys[i]]) + '   '))
			self.extPriceLabels[rowNum].set_alignment(1.0, 0.5)
			
			self.partInfoPricingTable.attach(self.priceBreakLabels[rowNum],  0, 1, rowNum, rowNum+1)
			self.partInfoPricingTable.attach(self.unitPriceLabels[rowNum],  1, 2, rowNum, rowNum+1)
			self.partInfoPricingTable.attach(self.extPriceLabels[rowNum],  2, 3, rowNum, rowNum+1)
			rowNum += 1
			
		self.partInfoFrame.show_all()
		
	def __init__(self):
		# -------- DECLARATIONS --------
		self.active_bom = BOM('dummy', 'Active BOM Declaration', urbmDB, inputFile)
		self.activeProjectName = 'dummy'
		
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.mainBox = gtk.VBox(False, 0)
		self.menuBar = gtk.MenuBar()
		self.notebook = gtk.Notebook()
		self.projectTabLabel = gtk.Label("Projects")
		self.bomTabLabel = gtk.Label("BOM Editor")
		self.dbTabLabel = gtk.Label("Product Database")
		
		# --- Projects tab ---
		self.projectBox = gtk.VBox(False, 0) # First tab in notebook
		self.projectToolbar = gtk.Toolbar()
		self.projectNewButton = gtk.ToolButton(None, "New Project")
		self.projectOpenButton = gtk.ToolButton(None, "Open Project")
		self.projectEditButton = gtk.ToolButton(None, "Edit Project")
		self.projectDeleteButton = gtk.ToolButton(None, "Delete Project")
		self.projectFrame = gtk.Frame("Projects") 
		self.projectScrollWin = gtk.ScrolledWindow()
		
		# New Project menu
		self.newProjectDialog = gtk.Dialog('New Project', self.window, 
										gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, 
										(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		
		self.newProjectNameHBox = gtk.HBox()
		self.newProjectDescriptionHBox = gtk.HBox()
		#newProjectDatabaseFileHBox = gtk.HBox()
		self.newProjectInputFileHBox = gtk.HBox()
		
		self.newProjectNameLabel = gtk.Label("Name: ")
		self.newProjectDescriptionLabel = gtk.Label("Description: ")
		#self.newProjectDatabaseFileLabel = gtk.Label("Database file: ")
		self.newProjectInputFileLabel = gtk.Label("Input file: ")
		
		self.newProjectNameEntry = gtk.Entry()
		self.newProjectDescriptionEntry = gtk.Entry()
		# TODO: Add a database file Entry/FileDialog when adding multiple DB file support
		self.newProjectInputFileButton = gtk.Button('Browse', gtk.STOCK_OPEN)
		self.newProjectInputFileEntry = gtk.Entry()
		self.inputFileDialog = gtk.FileChooserDialog('Select Input File', 
													self.newProjectDialog, gtk.FILE_CHOOSER_ACTION_OPEN, 
													(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		
		self.projectNameTakenDialog = gtk.MessageDialog(self.newProjectDialog, 
												gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, 
												gtk.BUTTONS_OK, 'Error: Project name in use. \nPlease select a different name.')
		
		# Projects list
		# Columns: Name, Description, Database, Input File
		self.projectStore = gtk.ListStore(str, str, str, str)
		self.projectNameCell = gtk.CellRendererText()
		self.projectNameColumn = gtk.TreeViewColumn('Name', self.projectNameCell)
		self.projectDescriptionCell = gtk.CellRendererText()
		self.projectDescriptionColumn = gtk.TreeViewColumn('Description', self.projectDescriptionCell)
		self.projectDBFileCell = gtk.CellRendererText()
		self.projectDBFileColumn = gtk.TreeViewColumn('Database File', self.projectDBFileCell)
		self.projectInputFileCell = gtk.CellRendererText()
		self.projectInputFileColumn = gtk.TreeViewColumn('Input File', self.projectInputFileCell)
		self.projectTreeView = gtk.TreeView() # Associate with self.projectStore later, not yet!
		
		# --- BOM tab ---
		self.bomTabBox = gtk.VBox(False, 0) # Second tab in notebook
		self.bomToolbar = gtk.Toolbar()
		self.bomReadInputButton = gtk.ToolButton(None, "Read CSV")
		self.bomReadDBButton = gtk.ToolButton(None, "Read DB")
		self.bomEditPartButton = gtk.ToolButton(None, "Edit Part")
		self.bomHPane = gtk.HPaned()	
		self.bomVPane = gtk.VPaned()	# Goes in right side of bomHPane
		
		self.bomFrame = gtk.Frame("BOM") # Goes in left side of bomHPane
		self.bomScrollBox = gtk.VBox(False, 0) # Holds bomScrollWin and bomRadioBox
		self.bomScrollWin = gtk.ScrolledWindow() # Holds bomTable
		
		# Columns: Name, Value, Device, Package, Description, MFG PN, Quantity
		self.bomStore = gtk.ListStore(str, str, str, str, str, str, int)
									
		self.bomNameCell = gtk.CellRendererText()
		self.bomNameColumn = gtk.TreeViewColumn('Name', self.bomNameCell)
		self.bomValueCell = gtk.CellRendererText()
		self.bomValueColumn = gtk.TreeViewColumn('Value', self.bomValueCell)
		self.bomDeviceCell = gtk.CellRendererText()
		self.bomDeviceColumn = gtk.TreeViewColumn('Device', self.bomDeviceCell)
		self.bomPackageCell = gtk.CellRendererText()
		self.bomPackageColumn = gtk.TreeViewColumn('Package', self.bomPackageCell)
		self.bomDescriptionCell = gtk.CellRendererText()
		self.bomDescriptionColumn = gtk.TreeViewColumn('Description', self.bomDescriptionCell)
		self.bomPNCell = gtk.CellRendererText()
		self.bomPNColumn = gtk.TreeViewColumn('Manufacturer Part Number', self.bomPNCell)
		self.bomQuantityCell = gtk.CellRendererText()
		self.bomQuantityColumn = gtk.TreeViewColumn('Quantity', self.bomQuantityCell)
		
		self.bomTreeView = gtk.TreeView()
		
		self.bomRadioBox = gtk.HBox(False, 0)
		self.bomRadioLabel = gtk.Label("Group by:")
		self.bomGroupName = gtk.RadioButton(None, "Name")
		self.bomGroupValue = gtk.RadioButton(self.bomGroupName, "Value")
		self.bomGroupPN = gtk.RadioButton(self.bomGroupName, "Part Number")
		
		self.bomSelectedProduct = Product("init", "init", urbmDB)
		self.selectedBomPart = bomPart("init", "init", "init", "init", self.active_bom)
		
		self.partInfoFrame = gtk.Frame("Part information") # Goes in top half of bomVPane
		self.partInfoRowBox = gtk.VBox(False, 5) # Fill with HBoxes 
		
		self.partInfoInfoTable = gtk.Table(5, 2, False) # Vendor, PNs, inventory, etc
		#self.partInfoVendorLabel1 = gtk.Label("Vendor: ")
		#self.partInfoVendorLabel2 = gtk.Label(None)
		#self.partInfoVendorPNLabel1 = gtk.Label("Vendor Part Number: ")
		#self.partInfoVendorPNLabel2 = gtk.Label(None)
		#self.partInfoInventoryLabel1 = gtk.Label("Inventory: ")
		#self.partInfoInventoryLabel2 = gtk.Label(None)
		self.partInfoManufacturerLabel1 = gtk.Label("Manufacturer: ")
		self.partInfoManufacturerLabel2 = gtk.Label(None)
		self.partInfoManufacturerPNLabel1 = gtk.Label("Manufacturer Part Number: ")
		self.partInfoManufacturerPNLabel2 = gtk.Label(None)
		self.partInfoDescriptionLabel1 = gtk.Label("Description: ")
		self.partInfoDescriptionLabel2 = gtk.Label(None)
		self.partInfoDatasheetLabel1 = gtk.Label("Datasheet filename: ")
		self.partInfoDatasheetLabel2 = gtk.Label(None)
		#self.partInfoCategoryLabel1 = gtk.Label("Category: ")
		#self.partInfoCategoryLabel2 = gtk.Label(None)
		#self.partInfoFamilyLabel1 = gtk.Label("Family: ")
		#self.partInfoFamilyLabel2 = gtk.Label(None)
		#self.partInfoSeriesLabel1 = gtk.Label("Series: ")
		#self.partInfoSeriesLabel2 = gtk.Label(None)
		self.partInfoPackageLabel1 = gtk.Label("Package/case: ")
		self.partInfoPackageLabel2 = gtk.Label(None)
		
		self.partInfoListingLabel = gtk.Label("Product source: ")
		self.partInfoListingCombo = gtk.combo_box_new_text()
		#self.partInfoListingCombo = gtk.combo_box_text_new_with_entry()
		
		
		self.partInfoPricingTable = gtk.Table(8, 3 , False) # Price breaks
		self.priceBreakLabels = []
		
		self.unitPriceLabels = []
		
		self.extPriceLabels = []
		
		self.partInfoButtonBox = gtk.HBox(False, 5)

		self.partInfoScrapeButton = gtk.Button("Scrape", stock=gtk.STOCK_REFRESH)
		self.partInfoDatasheetButton = gtk.Button("Datasheet", stock=gtk.STOCK_PROPERTIES)
		
		self.pricingFrame = gtk.Frame("Project pricing") # Goes in bottom half of bomVPane
		self.orderSizeScaleAdj = gtk.Adjustment(1, 1, 10000, 1, 10, 200)
		self.orderSizeScale = gtk.HScale(self.orderSizeScaleAdj)
		self.orderSizeText = gtk.Entry(10000)
		
		# --- Product DB tab ---
		self.dbBox = gtk.VBox(False, 0) # Third tab in notebook
		self.dbToolbar = gtk.Toolbar()
		self.dbReadDBButton = gtk.ToolButton(None, "Read DB")
		self.dbFrame = gtk.Frame("Product database") 
		self.dbScrollWin = gtk.ScrolledWindow()
		
		#self.dbProductStore = gtk.ListStore(str, str, int, str, str, str, str, str, str, str, str)
		self.dbProductStore = gtk.ListStore(str, str, str, str, str)
									
		#self.dbVendorCell = gtk.CellRendererText()
		#self.dbVendorColumn = gtk.TreeViewColumn('Vendor', self.dbVendorCell)
		#self.dbVendorPNCell = gtk.CellRendererText()
		#self.dbVendorPNColumn = gtk.TreeViewColumn('Vendor PN', self.dbVendorPNCell)
		#self.dbInventoryCell = gtk.CellRendererText()
		#self.dbInventoryColumn = gtk.TreeViewColumn('Inventory', self.dbInventoryCell)
		self.dbManufacturerCell = gtk.CellRendererText()
		self.dbManufacturerColumn = gtk.TreeViewColumn('Manufacturer', self.dbManufacturerCell)
		self.dbManufacturerPNCell = gtk.CellRendererText()
		self.dbManufacturerPNColumn = gtk.TreeViewColumn('Manufacturer PN', self.dbManufacturerPNCell)
		self.dbDescriptionCell = gtk.CellRendererText()
		self.dbDescriptionColumn = gtk.TreeViewColumn('Description', self.dbDescriptionCell)
		self.dbDatasheetCell = gtk.CellRendererText()
		self.dbDatasheetColumn = gtk.TreeViewColumn('Datasheet filename', self.dbDatasheetCell)
		#self.dbCategoryCell = gtk.CellRendererText()
		#self.dbCategoryColumn = gtk.TreeViewColumn('Category', self.dbCategoryCell)
		#self.dbFamilyCell = gtk.CellRendererText()
		#self.dbFamilyColumn = gtk.TreeViewColumn('Family', self.dbFamilyCell)
		#self.dbSeriesCell = gtk.CellRendererText()
		#self.dbSeriesColumn = gtk.TreeViewColumn('Series', self.dbSeriesCell)
		self.dbPackageCell = gtk.CellRendererText()
		self.dbPackageColumn = gtk.TreeViewColumn('Package/case', self.dbPackageCell)
		
		self.dbTreeView = gtk.TreeView()
		
		# -------- CONFIGURATION --------
		self.window.set_title("Unified Robotics BOM Manager") 
		# TODO: Add project name to window title on file open
		self.window.connect("delete_event", self.delete_event)
		self.window.connect("destroy", self.destroy)
		
		self.notebook.set_tab_pos(gtk.POS_TOP)
		self.notebook.append_page(self.projectBox, self.projectTabLabel)
		self.notebook.append_page(self.bomTabBox, self.bomTabLabel)
		self.notebook.append_page(self.dbBox, self.dbTabLabel)
		self.notebook.set_show_tabs(True)
		
		# Project selection tab
		self.projectNewButton.connect("clicked", self.projectNewCallback)
		self.newProjectInputFileButton.connect("clicked", self.newProjectInputFileCallback)
		
		self.projectOpenButton.connect("clicked", self.projectOpenCallback)
		
		self.newProjectNameLabel.set_alignment(0.0, 0.5)
		self.newProjectDescriptionLabel.set_alignment(0.0, 0.5)
		#self.newProjectDatabaseFileLabel.set_alignment(0.0, 0.5)
		self.newProjectInputFileLabel.set_alignment(0.0, 0.5)
		
		self.projectScrollWin.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		#self.projectTreeView.set_fixed_height_mode(True)
		self.projectTreeView.set_reorderable(True)
		self.projectTreeView.set_headers_clickable(True)
		
		self.projectNameColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.projectDescriptionColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.projectDBFileColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.projectInputFileColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		
		self.projectNameColumn.set_resizable(True)
		self.projectDescriptionColumn.set_resizable(True)
		self.projectDBFileColumn.set_resizable(True)
		self.projectInputFileColumn.set_resizable(True)
		
		self.projectNameColumn.set_attributes(self.projectNameCell, text=0)
		self.projectDescriptionColumn.set_attributes(self.projectDescriptionCell, text=1)
		self.projectDBFileColumn.set_attributes(self.projectDBFileCell, text=2)
		self.projectInputFileColumn.set_attributes(self.projectInputFileCell, text=3)
		
		self.projectTreeView.append_column(self.projectNameColumn)
		self.projectTreeView.append_column(self.projectDescriptionColumn)
		self.projectTreeView.append_column(self.projectDBFileColumn)
		self.projectTreeView.append_column(self.projectInputFileColumn)
		self.projectStorePopulate()
		self.projectTreeView.set_model(self.projectStore)
		
		# BOM tab
		
		self.bomNameColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bomValueColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bomDeviceColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bomPackageColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bomDescriptionColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bomPNColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bomQuantityColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		
		self.bomNameColumn.set_resizable(True)
		self.bomValueColumn.set_resizable(True)
		self.bomDeviceColumn.set_resizable(True)
		self.bomPackageColumn.set_resizable(True)
		self.bomDescriptionColumn.set_resizable(True)
		self.bomPNColumn.set_resizable(True)
		self.bomQuantityColumn.set_resizable(True)
		
		self.bomNameColumn.set_clickable(True)
		self.bomValueColumn.set_clickable(True)
		self.bomDeviceColumn.set_clickable(True)
		self.bomPackageColumn.set_clickable(True)
		self.bomDescriptionColumn.set_clickable(True)
		self.bomPNColumn.set_clickable(True)
		self.bomQuantityColumn.set_clickable(True)
		
		#self.bomNameColumn.set_sort_indicator(True)
		#self.bomValueColumn.set_sort_indicator(True)
		#self.bomDeviceColumn.set_sort_indicator(True)
		#self.bomPackageColumn.set_sort_indicator(True)
		#self.bomDescriptionColumn.set_sort_indicator(True)
		#self.bomPNColumn.set_sort_indicator(True)
		#self.bomQuantityColumn.set_sort_indicator(True)
		
		self.bomNameColumn.set_attributes(self.bomNameCell, text=0)
		self.bomValueColumn.set_attributes(self.bomValueCell, text=1)
		self.bomDeviceColumn.set_attributes(self.bomDeviceCell, text=2)
		self.bomPackageColumn.set_attributes(self.bomPackageCell, text=3)
		self.bomDescriptionColumn.set_attributes(self.bomDescriptionCell, text=4)
		self.bomPNColumn.set_attributes(self.bomPNCell, text=5)
		self.bomQuantityColumn.set_attributes(self.bomQuantityCell, text=6)
		
		self.bomNameColumn.connect("clicked", self.bomSortCallback)
		self.bomValueColumn.connect("clicked", self.bomSortCallback)
		self.bomDeviceColumn.connect("clicked", self.bomSortCallback)
		self.bomPackageColumn.connect("clicked", self.bomSortCallback)
		self.bomDescriptionColumn.connect("clicked", self.bomSortCallback)
		self.bomPNColumn.connect("clicked", self.bomSortCallback)
		self.bomQuantityColumn.connect("clicked", self.bomSortCallback)
		
		self.bomTreeView.set_reorderable(True)
		self.bomTreeView.set_enable_search(True)
		self.bomTreeView.set_headers_clickable(True)
		self.bomTreeView.set_headers_visible(True)
		
		self.bomTreeView.append_column(self.bomNameColumn)
		self.bomTreeView.append_column(self.bomValueColumn)
		self.bomTreeView.append_column(self.bomDeviceColumn)
		self.bomTreeView.append_column(self.bomPackageColumn)
		self.bomTreeView.append_column(self.bomDescriptionColumn)
		self.bomTreeView.append_column(self.bomPNColumn)
		self.bomTreeView.append_column(self.bomQuantityColumn)
		#self.projectStorePopulate()
		
		self.bomTreeView.connect("cursor-changed", self.bomSelectionCallback)
		self.bomTreeView.set_model(self.bomStore)
		
		self.bomReadInputButton.connect("clicked", self.readInputCallback, "read")
		self.bomReadDBButton.connect("clicked", self.bomReadDBCallback, "read")
		self.bomEditPartButton.connect("clicked", self.bomEditPartCallback, "setPN")
		
		self.bomScrollWin.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		
		# TODO: Fiddle with bomTable sizing to make it force the window larger to fit
		
		self.bomGroupName.connect("toggled", self.bomGroupCallback, "name")
		self.bomGroupValue.connect("toggled", self.bomGroupCallback, "value")
		self.bomGroupPN.connect("toggled", self.bomGroupCallback, "product")
		
		#self.partInfoVendorLabel1.set_alignment(0.0, 0.5)
		#self.partInfoVendorLabel2.set_alignment(0.0, 0.5)
		#self.partInfoVendorPNLabel1.set_alignment(0.0, 0.5)
		#self.partInfoVendorPNLabel2.set_alignment(0.0, 0.5)
		#self.partInfoInventoryLabel1.set_alignment(0.0, 0.5)
		#self.partInfoInventoryLabel2.set_alignment(0.0, 0.5)
		self.partInfoManufacturerLabel1.set_alignment(0.0, 0.5)
		self.partInfoManufacturerLabel2.set_alignment(0.0, 0.5)
		self.partInfoManufacturerPNLabel1.set_alignment(0.0, 0.5)
		self.partInfoManufacturerPNLabel2.set_alignment(0.0, 0.5)
		self.partInfoDescriptionLabel1.set_alignment(0.0, 0.5)
		self.partInfoDescriptionLabel2.set_alignment(0.0, 0.5)
		self.partInfoDatasheetLabel1.set_alignment(0.0, 0.5)
		self.partInfoDatasheetLabel2.set_alignment(0.0, 0.5)
		#self.partInfoCategoryLabel1.set_alignment(0.0, 0.5)
		#self.partInfoCategoryLabel2.set_alignment(0.0, 0.5)
		#self.partInfoFamilyLabel1.set_alignment(0.0, 0.5)
		#self.partInfoFamilyLabel2.set_alignment(0.0, 0.5)
		#self.partInfoSeriesLabel1.set_alignment(0.0, 0.5)
		#self.partInfoSeriesLabel2.set_alignment(0.0, 0.5)
		self.partInfoPackageLabel1.set_alignment(0.0, 0.5)
		self.partInfoPackageLabel2.set_alignment(0.0, 0.5)
		self.partInfoScrapeButton.connect("clicked", self.partInfoScrapeButtonCallback)
		self.partInfoListingLabel.set_alignment(0.0, 0.5)
		self.partInfoListingCombo.connect("changed", self.partInfoListingComboCallback)
		
		self.dbScrollWin.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		self.dbReadDBButton.connect("clicked", self.dbReadDBCallback, "read")
		
		#self.dbVendorColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbVendorPNColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbInventoryColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.dbManufacturerColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.dbManufacturerPNColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.dbDescriptionColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.dbDatasheetColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbCategoryColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbFamilyColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbSeriesColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.dbPackageColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		
		#self.dbVendorColumn.set_resizable(True)
		#self.dbVendorPNColumn.set_resizable(True)
		#self.dbInventoryColumn.set_resizable(True)
		self.dbManufacturerColumn.set_resizable(True)
		self.dbManufacturerPNColumn.set_resizable(True)
		self.dbDescriptionColumn.set_resizable(True)
		self.dbDatasheetColumn.set_resizable(True)
		#self.dbCategoryColumn.set_resizable(True)
		#self.dbFamilyColumn.set_resizable(True)
		#self.dbSeriesColumn.set_resizable(True)
		self.dbPackageColumn.set_resizable(True)
		
		#self.dbVendorColumn.set_clickable(True)
		#self.dbVendorPNColumn.set_clickable(True)
		#self.dbInventoryColumn.set_clickable(True)
		self.dbManufacturerColumn.set_clickable(True)
		self.dbManufacturerPNColumn.set_clickable(True)
		self.dbDescriptionColumn.set_clickable(True)
		self.dbDatasheetColumn.set_clickable(True)
		#self.dbCategoryColumn.set_clickable(True)
		#self.dbFamilyColumn.set_clickable(True)
		#self.dbSeriesColumn.set_clickable(True)
		self.dbPackageColumn.set_clickable(True)
		
		#self.dbVendorColumn.set_attributes(self.dbVendorCell, text=0)
		#self.dbVendorPNColumn.set_attributes(self.dbVendorPNCell, text=1)
		#self.dbInventoryColumn.set_attributes(self.dbInventoryCell, text=2)
		self.dbManufacturerColumn.set_attributes(self.dbManufacturerCell, text=0)
		self.dbManufacturerPNColumn.set_attributes(self.dbManufacturerPNCell, text=1)
		self.dbDescriptionColumn.set_attributes(self.dbDescriptionCell, text=2)
		self.dbDatasheetColumn.set_attributes(self.dbDatasheetCell, text=3)
		#self.dbCategoryColumn.set_attributes(self.dbCategoryCell, text=7)
		#self.dbFamilyColumn.set_attributes(self.dbFamilyCell, text=8)
		#self.dbSeriesColumn.set_attributes(self.dbSeriesCell, text=9)
		self.dbPackageColumn.set_attributes(self.dbPackageCell, text=4)
		
		#self.dbVendorColumn.connect("clicked", self.dbSortCallback)
		#self.dbVendorPNColumn.connect("clicked", self.dbSortCallback)
		#self.dbInventoryColumn.connect("clicked", self.dbSortCallback)
		self.dbManufacturerColumn.connect("clicked", self.dbSortCallback)
		self.dbManufacturerPNColumn.connect("clicked", self.dbSortCallback)
		self.dbDescriptionColumn.connect("clicked", self.dbSortCallback)
		self.dbDatasheetColumn.connect("clicked", self.dbSortCallback)
		#self.dbCategoryColumn.connect("clicked", self.dbSortCallback)
		#self.dbFamilyColumn.connect("clicked", self.dbSortCallback)
		#self.dbSeriesColumn.connect("clicked", self.dbSortCallback)
		self.dbPackageColumn.connect("clicked", self.dbSortCallback)
		
		self.dbTreeView.set_reorderable(True)
		self.dbTreeView.set_enable_search(True)
		self.dbTreeView.set_headers_clickable(True)
		self.dbTreeView.set_headers_visible(True)
		
		#self.dbTreeView.append_column(self.dbVendorColumn)
		#self.dbTreeView.append_column(self.dbVendorPNColumn)
		#self.dbTreeView.append_column(self.dbInventoryColumn)
		self.dbTreeView.append_column(self.dbManufacturerColumn)
		self.dbTreeView.append_column(self.dbManufacturerPNColumn)
		self.dbTreeView.append_column(self.dbDescriptionColumn)
		self.dbTreeView.append_column(self.dbDatasheetColumn)
		#self.dbTreeView.append_column(self.dbCategoryColumn)
		#self.dbTreeView.append_column(self.dbFamilyColumn)
		#self.dbTreeView.append_column(self.dbSeriesColumn)
		self.dbTreeView.append_column(self.dbPackageColumn)
		self.dbStorePopulate()
		
		self.dbTreeView.connect("cursor-changed", self.dbSelectionCallback)
		self.dbTreeView.set_model(self.dbProductStore)
		
		# -------- PACKING AND ADDING --------
		self.mainBox.pack_start(self.menuBar)
		self.mainBox.pack_start(self.notebook)
		self.window.add(self.mainBox)
		
		# Project selection tab
		self.projectBox.pack_start(self.projectToolbar)
		self.projectToolbar.insert(self.projectNewButton, 0)
		self.projectToolbar.insert(self.projectOpenButton, 1)
		self.projectToolbar.insert(self.projectEditButton, 2)
		self.projectToolbar.insert(self.projectDeleteButton, 3)
		
		self.projectBox.pack_start(self.projectFrame)
		self.projectFrame.add(self.projectScrollWin)
		self.projectScrollWin.add(self.projectTreeView)
		
		self.newProjectNameHBox.pack_start(self.newProjectNameLabel, False, True, 0)
		self.newProjectNameHBox.pack_end(self.newProjectNameEntry, False, True, 0)
		
		self.newProjectDescriptionHBox.pack_start(self.newProjectDescriptionLabel, False, True, 0)
		self.newProjectDescriptionHBox.pack_end(self.newProjectDescriptionEntry, False, True, 0)
		
		#self.newProjectDatabaseFileHBox.pack_start(self.newProjectDatabaseFileLabel, False, True, 0)
		#self.newProjectDatabaseFileHBox.pack_end(self.newProjectDatabaseFileEntry, False, True, 0)
		
		self.newProjectInputFileHBox.pack_start(self.newProjectInputFileLabel, False, True, 0)
		self.newProjectInputFileHBox.pack_start(self.newProjectInputFileEntry, False, True, 0)
		self.newProjectInputFileHBox.pack_end(self.newProjectInputFileButton, False, True, 0)
		
		self.newProjectDialog.vbox.set_spacing(1)
		self.newProjectDialog.vbox.pack_start(self.newProjectNameHBox, True, True, 0)
		self.newProjectDialog.vbox.pack_start(self.newProjectDescriptionHBox, True, True, 0)
		#self.newProjectDialog.vbox.pack_start(self.newProjectDatabaseFileHBox, True, True, 0)
		self.newProjectDialog.vbox.pack_start(self.newProjectInputFileHBox, True, True, 0)
		
		self.newProjectDialog.vbox.show_all()
		
		# BOM tab elements
		
		self.bomTabBox.pack_start(self.bomToolbar)
		self.bomToolbar.insert(self.bomReadInputButton, 0)
		self.bomToolbar.insert(self.bomReadDBButton, 1)
		self.bomToolbar.insert(self.bomEditPartButton, 2)
		
		# TODO : Add toolbar elements
		
		self.bomTabBox.pack_start(self.bomHPane)
		self.bomHPane.pack1(self.bomFrame, True, True)
		self.bomHPane.add2(self.bomVPane)
		self.bomVPane.add1(self.partInfoFrame)
		self.bomVPane.add2(self.pricingFrame)
		
		# BOM Frame elements
		self.bomFrame.add(self.bomScrollBox)
		
		self.bomScrollBox.pack_start(self.bomScrollWin, True, True, 0)
		self.bomScrollWin.add(self.bomTreeView)
		self.bomScrollBox.pack_end(self.bomRadioBox, False, False, 0)

		self.bomRadioBox.pack_start(self.bomRadioLabel)
		self.bomRadioBox.pack_start(self.bomGroupName)
		self.bomRadioBox.pack_start(self.bomGroupValue)
		self.bomRadioBox.pack_start(self.bomGroupPN)
		
		# Part info frame elements
		self.partInfoFrame.add(self.partInfoRowBox)
		self.partInfoRowBox.pack_start(self.partInfoInfoTable, True, True, 5)
		#self.partInfoInfoTable.attach(self.partInfoVendorLabel1, 0, 1, 0, 1)
		#self.partInfoInfoTable.attach(self.partInfoVendorPNLabel1, 0, 1, 1, 2)
		#self.partInfoInfoTable.attach(self.partInfoInventoryLabel1, 0, 1, 2, 3)
		self.partInfoInfoTable.attach(self.partInfoManufacturerLabel1, 0, 1, 0, 1)
		self.partInfoInfoTable.attach(self.partInfoManufacturerPNLabel1, 0, 1, 1, 2)
		self.partInfoInfoTable.attach(self.partInfoDescriptionLabel1, 0, 1, 2, 3)
		self.partInfoInfoTable.attach(self.partInfoDatasheetLabel1, 0, 1, 3, 4)
		#self.partInfoInfoTable.attach(self.partInfoCategoryLabel1, 0, 1, 7, 8)
		#self.partInfoInfoTable.attach(self.partInfoFamilyLabel1, 0, 1, 8, 9)
		#self.partInfoInfoTable.attach(self.partInfoSeriesLabel1, 0, 1, 9, 10)
		self.partInfoInfoTable.attach(self.partInfoPackageLabel1, 0, 1, 4, 5)
		
		#self.partInfoInfoTable.attach(self.partInfoVendorLabel2, 1, 2, 0, 1)
		#self.partInfoInfoTable.attach(self.partInfoVendorPNLabel2, 1, 2, 1, 2)
		#self.partInfoInfoTable.attach(self.partInfoInventoryLabel2, 1, 2, 2, 3)
		self.partInfoInfoTable.attach(self.partInfoManufacturerLabel2, 1, 2, 0, 1)
		self.partInfoInfoTable.attach(self.partInfoManufacturerPNLabel2, 1, 2, 1, 2)
		self.partInfoInfoTable.attach(self.partInfoDescriptionLabel2, 1, 2, 2, 3)
		self.partInfoInfoTable.attach(self.partInfoDatasheetLabel2, 1, 2, 3, 4)
		#self.partInfoInfoTable.attach(self.partInfoCategoryLabel2, 1, 2, 7, 8)
		#self.partInfoInfoTable.attach(self.partInfoFamilyLabel2, 1, 2, 8, 9)
		#self.partInfoInfoTable.attach(self.partInfoSeriesLabel2, 1, 2, 9, 10)
		self.partInfoInfoTable.attach(self.partInfoPackageLabel2, 1, 2, 4, 5)
		
		self.partInfoRowBox.pack_start(self.partInfoButtonBox, True, True, 5)
		self.partInfoButtonBox.pack_start(self.partInfoScrapeButton, True, True, 5)
		self.partInfoButtonBox.pack_start(self.partInfoDatasheetButton, True, True, 5)
		self.partInfoRowBox.pack_start(self.partInfoListingLabel, False, False, 0)
		self.partInfoRowBox.pack_start(self.partInfoListingCombo, False, False, 0)
		self.partInfoRowBox.pack_start(self.partInfoPricingTable, True, True, 5)
		
		
		self.dbBox.pack_start(self.dbToolbar, False)
		self.dbToolbar.insert(self.dbReadDBButton, 0)
		self.dbBox.pack_start(self.dbFrame)
		self.dbFrame.add(self.dbScrollWin)
		self.dbScrollWin.add(self.dbTreeView)
		
		self.dbReadDBCallback(None)
		# Show everything
		self.mainBox.show_all()
		self.window.show()

def main():
	gtk.main()
	
if __name__ == "__main__":
	URBM()
	main()
