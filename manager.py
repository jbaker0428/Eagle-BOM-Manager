import csv
import pygtk
pygtk.require('2.0')
import gtk
import shutil
import os
import sqlite3
import types
import gobject

class Workspace:
	''' Each Workspace has its own persistent database file. '''
	db0 = os.path.join(os.getcwd(), 'workspace.sqlite')
	
	def __init__(self, name='Workspace', db=db0):
		self.name = name
		self.db = db
		self.projects = []
	
	def con_cursor(self):
		''' Connect to the DB, enable foreign keys, set autocommit mode,  
		and return a (connection, cursor) pair. '''
		con = sqlite3.connect(self.db)
		con.isolation_level = None
		con.execute('PRAGMA foreign_keys = ON')
		cur = con.cursor()
		return (con, cur)
		
	def list_projects(self):
		''' Returns a list of BOM project tables in the DB. '''
		projects = []
		try:
			(con, cur) = self.con_cursor()
			cur.execute('SELECT name FROM projects ORDER BY name')
			for row in cur.fetchall():
				projects.append(row[0])
			
		finally:
			cur.close()
			con.close()
			return projects
	
	def create_tables(self):
		''' Create the workspace-wide database tables. '''		
		try:
			(con, cur) = self.con_cursor()
			cur.execute('CREATE TABLE IF NOT EXISTS projects(name TEXT PRIMARY KEY, description TEXT, infile TEXT)')
			
			cur.execute('''CREATE TABLE IF NOT EXISTS products
			(manufacturer TEXT, 
			manufacturer_pn TEXT PRIMARY KEY, 
			datasheet TEXT, 
			description TEXT, 
			package TEXT)''')
			cur.execute("INSERT OR REPLACE INTO products VALUES ('NULL','NULL','NULL','NULL','NULL')")
			
			cur.execute('''CREATE TABLE IF NOT EXISTS listings
			(vendor TEXT, 
			vendor_pn TEXT PRIMARY KEY, 
			manufacturer_pn TEXT REFERENCES products(manufacturer_pn), 
			inventory INTEGER, 
			packaging TEXT,
			reelfee FLOAT, 
			category TEXT,
			family TEXT,
			series TEXT)''')
			
			cur.execute('''CREATE TABLE IF NOT EXISTS pricebreaks
			(id INTEGER PRIMARY KEY,
			pn TEXT REFERENCES listings(vendor_pn), 
			qty INTEGER,
			unit DOUBLE)''')
						
		finally:
			cur.close()
			con.close()

wspace = Workspace()
wspace.create_tables()
wspace.projects = wspace.list_projects()

#active_project_name = 'test1'
input_file = os.path.join(os.getcwd(), "test.csv")	# TODO: Test dummy

#active_bom = BOM("test1", 'Test BOM 1', wspace, os.path.join(os.getcwd(), "test.csv"))


class Manager(gobject.GObject):
	'''Main GUI class'''
	def delete_event(self, widget, event, data=None):
		print "delete event occurred"
		return False
		
	def destroy(self, widget, data=None):
		gtk.main_quit()

	# -------- CALLBACK METHODS --------
	''' Callback for the input file Open dialog in the New Project dialog. '''
	def new_project_input_file_callback(self, widget, data=None):
		self.input_file_dialog.run()
		self.input_file_dialog.hide()
		self.new_project_input_file_entry.set_text(self.input_file_dialog.get_filename())
	
	'''Callback for the New Project button. '''
	def project_new_callback(self, widget, data=None):
		response = self.new_project_dialog.run()
		self.new_project_dialog.hide()
		new_name = self.new_project_name_entry.get_text()
		curProjects = wspace.list_projects()
		if new_name in curProjects:
			print 'Error: Name in use!'
			self.project_name_taken_dialog.run()
			self.project_name_taken_dialog.hide()
		elif response == gtk.RESPONSE_ACCEPT: 
			# Create project
			print 'Creating new project'
			new = BOM.new_project(new_name, self.new_project_description_entry.get_text(), self.new_project_input_file_entry.get_text(), wspace)
			self.project_store_populate()
		self.new_project_name_entry.set_text('')
		self.new_project_description_entry.set_text('')
		#self.new_project_workspace_entry.set_text('')
		self.new_project_input_file_entry.set_text('')
		
	def project_open_callback(self, widget, data=None):
		(model, row_iter) = self.project_tree_view.get_selection().get_selected()
		self.active_bom = BOM.read_from_db(model.get(row_iter,0)[0], wspace)[0]
		self.active_project_name = model.get(row_iter,0)[0]
		self.active_bom.parts = self.active_bom.read_parts_list_from_db(wspace)
		input_file = model.get(row_iter,3)[0]
		print self.active_bom, type(self.active_bom)
		#print 'Project name: ', self.active_project_name
		#print 'Project CSV: ', input_file
		if self.bom_group_name.get_active():
			self.bom_store_populate_by_name()
		elif self.bom_group_value.get_active():
			self.bom_store_populate_by_value()
		elif self.bom_group_product.get_active():
			self.bom_store_populate_by_product()
			
		self.bom_tree_view.columns_autosize()
		# TODO: Uncomment this when spin is working
		#self.order_size_spin_callback(self.run_size_spin)
		self.window.show_all()
		
	'''Callback for the "Read CSV" button on the BOM tab.'''
	def read_input_callback(self, widget, data=None):
		self.active_bom.read_from_file(wspace)
		if self.bom_group_name.get_active():
			self.bom_store_populate_by_name()
		elif self.bom_group_value.get_active():
			self.bom_store_populate_by_value()
		elif self.bom_group_product.get_active():
			self.bom_store_populate_by_product()
		self.window.show_all()
	
	'''Callback for the "Read DB" button on the BOM tab.'''
	def bom_read_db_callback(self, widget, data=None):
		#print "BOM Read DB callback"
		#print 'Parts list = ', self.active_bom.parts
		if self.bom_group_name.get_active():
			self.bom_store_populate_by_name()
		elif self.bom_group_value.get_active():
			self.bom_store_populate_by_value()
		elif self.bom_group_product.get_active():
			self.bom_store_populate_by_product()
		self.window.show_all()
	
	'''Callback method triggered when a BOM line item is selected.'''
	def bom_selection_callback(self, widget, data=None):
		# Set class fields for currently selected item
		(model, row_iter) = self.bom_tree_view.get_selection().get_selected()
		#print 'row_iter is: ', row_iter, '\n'
		#print 'model.get(row_iter,0)[0] is: ', model.get(row_iter,0)[0]
		self.selected_bom_part = self.active_bom.select_parts_by_name(model.get(row_iter,0)[0], wspace)[0]
		# Grab the vendor part number for the selected item from the label text
		selected_product = model.get(row_iter,5)[0]
		print "selected_product is: %s" % selected_product
		if selected_product != 'NULL': # Look up part in DB
			self.part_info_datasheet_button.set_sensitive(True)
			self.part_info_scrape_button.set_sensitive(True)
			# Set class field for currently selected product
			print "Querying with selected_product: %s" % selected_product
			self.bom_selected_product.manufacturer_pn = selected_product
			
			self.bom_selected_product.select_or_scrape(wspace)
			self.bom_selected_product.fetch_listings(wspace)
			#self.bom_selected_product.show()
			self.set_part_info_labels(self.bom_selected_product)
			self.set_part_info_listing_combo(self.bom_selected_product)
			self.destroy_part_price_labels()
			#print 'self.bom_selected_product.listings: \n', self.bom_selected_product.listings
			if type(self.part_info_listing_combo.get_active_text()) is not types.NoneType and self.part_info_listing_combo.get_active_text() != '':
				self.set_part_price_labels(self.bom_selected_product.listings[self.part_info_listing_combo.get_active_text()])
		else:
			self.part_info_datasheet_button.set_sensitive(False)
			self.part_info_scrape_button.set_sensitive(False)
			self.set_part_info_listing_combo()
			self.destroy_part_price_labels()
			self.clear_part_info_labels()
	
	'''Callback method activated by the BOM grouping radio buttons.
	Redraws the BOM TreeView with the approporiate goruping for the selected radio.'''
	def bom_group_callback(self, widget, data=None):
		#print "%s was toggled %s" % (data, ("OFF", "ON")[widget.get_active()])
		
		# Figure out which button is now selected
		if widget.get_active():
			if 'name' in data:
				self.bom_store_populate_by_name()
				
			elif 'value' in data:
				self.bom_store_populate_by_value()
					
			elif 'product' in data:
				self.bom_store_populate_by_product()
					
			self.window.show_all()
	
	'''Callback method activated by clicking a BOM column header.
	Sorts the BOM TreeView by the values in the clicked column.'''
	def bom_sort_callback(self, widget):
		print widget.get_sort_order()
		widget.set_sort_column_id(0)
		# TODO: On sorting by a different column, the indicator does not go away
		# This may be because with the current test set, the other columns are still technically sorted
	
	'''Callback method for the "Edit Part" button in the BOM tab.
	Opens a dialog window with form fields for each BOM Part object field.'''
	def bom_edit_part_callback(self, widget, data=None):
		# Open a text input prompt window
		edit_part_dialog = gtk.Dialog("Edit part", self.window, 
						gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, 
						gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		
		# -------- DECLARATIONS --------
		# Field labels
		edit_part_name_label = gtk.Label("Name: ")
		edit_part_value_label = gtk.Label("Value: ")
		edit_part_device_label = gtk.Label("Device: ")
		edit_part_package_label = gtk.Label("Package: ")
		edit_part_description_label = gtk.Label("Description: ")
		edit_part_manufacturer_label = gtk.Label("Manufacturer: ")
		edit_part_manufacturer_pn_label = gtk.Label("Manufacturer Part Number: ")
		
		# Field entry elements
		self.edit_part_name_entry = gtk.Entry()
		self.edit_part_value_entry = gtk.Entry()
		self.edit_part_device_entry = gtk.Entry()
		self.edit_part_package_entry = gtk.Entry()
		self.edit_part_description_entry = gtk.Entry()
		self.edit_part_product_entry = gtk.Entry()
		
		# Return values
		self.product_entry_text = ""
		
		# HBoxes
		edit_part_dialog_name_hbox = gtk.HBox()
		edit_part_dialog_value_hbox = gtk.HBox()
		edit_part_dialog_device_hbox = gtk.HBox()
		edit_part_dialog_package_hbox = gtk.HBox()
		edit_part_dialog_description_hbox = gtk.HBox()
		edit_part_dialog_manufacturer_hbox = gtk.HBox()
		edit_part_dialog_manufacturer_pn_hbox = gtk.HBox()
		
		# -------- CONFIGURATION --------
		# Label alignment
		edit_part_name_label.set_alignment(0.0, 0.5)
		edit_part_value_label.set_alignment(0.0, 0.5)
		edit_part_device_label.set_alignment(0.0, 0.5)
		edit_part_package_label.set_alignment(0.0, 0.5)
		edit_part_description_label.set_alignment(0.0, 0.5)
		edit_part_manufacturer_label.set_alignment(0.0, 0.5)
		edit_part_manufacturer_pn_label.set_alignment(0.0, 0.5)
		
		# Set default text of entry fields to current part values
		self.edit_part_name_entry.set_text(self.selected_bom_part.name)
		self.edit_part_value_entry.set_text(self.selected_bom_part.value)
		self.edit_part_device_entry.set_text(self.selected_bom_part.device)
		self.edit_part_package_entry.set_text(self.selected_bom_part.package)
		self.edit_part_description_entry.set_text(self.selected_bom_part.description)
		self.edit_part_product_entry.set_text(self.selected_bom_part.product)
		
		# Pack labels/entry fields into HBoxes
		edit_part_dialog_name_hbox.pack_start(edit_part_name_label, False, True, 0)
		edit_part_dialog_name_hbox.pack_end(self.edit_part_name_entry, False, True, 0)
		
		edit_part_dialog_value_hbox.pack_start(edit_part_value_label, False, True, 0)
		edit_part_dialog_value_hbox.pack_end(self.edit_part_value_entry, False, True, 0)
		
		edit_part_dialog_device_hbox.pack_start(edit_part_device_label, False, True, 0)
		edit_part_dialog_device_hbox.pack_end(self.edit_part_device_entry, False, True, 0)
		
		edit_part_dialog_package_hbox.pack_start(edit_part_package_label, False, True, 0)
		edit_part_dialog_package_hbox.pack_end(self.edit_part_package_entry, False, True, 0)
		
		edit_part_dialog_description_hbox.pack_start(edit_part_description_label, False, True, 0)
		edit_part_dialog_description_hbox.pack_end(self.edit_part_description_entry, False, True, 0)
		
		edit_part_dialog_manufacturer_pn_hbox.pack_start(edit_part_manufacturer_pn_label, True, True, 0)
		edit_part_dialog_manufacturer_pn_hbox.pack_end(self.edit_part_product_entry, gtk.RESPONSE_ACCEPT)
		
		# Pack HBoxes into vbox
		edit_part_dialog.vbox.set_spacing(1)
		edit_part_dialog.vbox.pack_start(edit_part_dialog_name_hbox, True, True, 0)
		edit_part_dialog.vbox.pack_start(edit_part_dialog_value_hbox, True, True, 0)
		edit_part_dialog.vbox.pack_start(edit_part_dialog_device_hbox, True, True, 0)
		edit_part_dialog.vbox.pack_start(edit_part_dialog_package_hbox, True, True, 0)
		edit_part_dialog.vbox.pack_start(edit_part_dialog_description_hbox, True, True, 0)
		edit_part_dialog.vbox.pack_start(edit_part_dialog_manufacturer_pn_hbox, True, True, 0)
		
		# Show everything
		edit_part_dialog.vbox.show_all()
		response = edit_part_dialog.run()
		edit_part_dialog.hide()
		
		if response == gtk.RESPONSE_ACCEPT:
			# If the product text entry field is left blank, set the product to 'NULL'
			if type(self.edit_part_product_entry.get_text()) is types.NoneType or len(self.edit_part_product_entry.get_text()) == 0:
				self.product_entry_text = 'NULL'
			else:
				self.product_entry_text = self.edit_part_product_entry.get_text()
			
			# Set selected_bom_part
			# TODO: If grouping by value or PN, what to do? Grey out the name field?
			# It should write the rest to ALL of the parts in the row
			self.selected_bom_part.name = self.edit_part_name_entry.get_text()
			self.selected_bom_part.value = self.edit_part_value_entry.get_text()
			self.selected_bom_part.device = self.edit_part_device_entry.get_text()
			self.selected_bom_part.package = self.edit_part_package_entry.get_text()
			self.selected_bom_part.description = self.edit_part_description_entry.get_text()
			print "Setting selected_bom_part.product to: %s" % self.edit_part_product_entry.get_text()
			self.selected_bom_part.product = self.product_entry_text
			print "selected_bom_part's product field: %s" % self.selected_bom_part.product
			
			# We need to check the products table for this Product, creating an entry
			# for it if necessary, before updating selected_bom_part in the DB.
			self.bom_selected_product.manufacturer_pn = self.product_entry_text
			self.bom_selected_product.select_or_scrape(wspace)
			
			self.selected_bom_part.update(self.active_bom.name, wspace)
			self.active_bom.update_parts_list(self.selected_bom_part)
			
			if self.bom_group_name.get_active():
				self.bom_store_populate_by_name()
			elif self.bom_group_value.get_active():
				self.bom_store_populate_by_value()
			elif self.bom_group_product.get_active():
				self.bom_store_populate_by_product()
					
			self.set_part_info_listing_combo(self.bom_selected_product)
			if self.bom_selected_product.manufacturer_pn == 'NULL':
				self.clear_part_info_labels()
			else:
				self.set_part_info_labels(self.bom_selected_product)
	
	def part_info_scrape_button_callback(self, widget):
		''' Part info frame "Refresh" button callback. '''
		self.bom_selected_product.scrape(wspace)
		if self.bom_group_name.get_active():
			self.bom_store_populate_by_name()
		elif self.bom_group_value.get_active():
			self.bom_store_populate_by_value()
		elif self.bom_group_product.get_active():
			self.bom_store_populate_by_product()
		self.window.show_all()
	
	def part_info_listing_combo_callback(self, widget, data=None):
		self.destroy_part_price_labels()
		if type(self.part_info_listing_combo.get_active_text()) is not types.NoneType and self.part_info_listing_combo.get_active_text() != '':
			self.set_part_price_labels(self.bom_selected_product.listings[self.part_info_listing_combo.get_active_text()])
			self.part_info_inventory_content_label.set_text(str(self.bom_selected_product.listings[self.part_info_listing_combo.get_active_text()].inventory))
	
	def order_size_spin_callback(self, widget):
		''' Update the per-unit and total order prices when the order size
		spin button is changed. '''
		qty = self.run_size_spin.get_value_as_int()
		(unit_price, total_cost) = self.active_bom.get_cost(wspace, qty)
		self.run_unit_price_content_label.set_text('$'+str(unit_price))
		self.run_total_cost_content_label.set_text('$'+str(total_cost))
	
	''' Clear self.db_product_store and repopulate it. '''
	def db_store_populate(self):
		self.db_product_store.clear()
		prods = Product.select_all(wspace)
		for p in prods:
			iter = self.db_product_store.append([p.manufacturer, p.manufacturer_pn, p.description, p.datasheet, p.package])
		self.db_tree_view.columns_autosize()
	
	'''Callback for the "Read DB" button on the product DB tab.'''
	def db_read_database_callback(self, widget, data=None):
		print "Read DB callback"
		self.db_store_populate()
	
	'''Callback method triggered when a product DB item is selected.'''
	def db_selection_callback(self, widget, data=None):
		# Set class fields for currently selected item
		(model, row_iter) = self.db_tree_view.get_selection().get_selected()
		self.db_selected_product = Product.select_by_pn(model.get(row_iter,1)[0], wspace)[0]
	
	'''Callback method activated by clicking a DB column header.
	Sorts the DB TreeView by the values in the clicked column.'''
	def db_sort_callback(self, widget):
		widget.set_sort_column_id(0)
	 
	# -------- HELPER METHODS --------
	def project_store_populate(self):
		self.project_store.clear()
		# Columns: Name, Description, Database, Input File
		projects_list = wspace.list_projects()
		#print 'projects_list: ', projects_list
		for p in projects_list:
			if type(p) is types.NoneType:
				print 'NoneType caught in projects_list'
			elif p != 'dummy':
				#print 'p = ', p
				bom = BOM.read_from_db(p, wspace)[0]
				print 'Returned BOM: ', bom, type(bom)
				iter = self.project_store.append([bom.name, bom.description, wspace.name, bom.input])
		self.project_tree_view.columns_autosize()
	
	def bom_store_populate_by_name(self):
		''' Clear self.bom_store and repopulate it, grouped by name. '''
		self.bom_store.clear()
		for p in self.active_bom.parts:
			temp = self.active_bom.select_parts_by_name(p[0], wspace)[0]
			iter = self.bom_store.append([temp.name, temp.value, temp.device, temp.package, temp.description, temp.product, 1])
		
		self.bom_tree_view.columns_autosize()
	
	def bom_store_populate_by_value(self):
		''' Clear self.bom_store and repopulate it, grouped by value. '''
		self.bom_store.clear()
		self.active_bom.sort_by_val()
		self.active_bom.set_val_counts(wspace)
		
		for val in self.active_bom.val_counts.keys():
			group_name = "\t"	# Clear group_name and prepend a tab
			# TODO: Does this split up parts of the same value but different package?
			# If not, the "part number" column will be bad
			group = self.active_bom.select_parts_by_value(val, wspace)
			for part in group:
				group_name += part.name + ", "
			
			# Replace trailing comma with tab
			group_name = group_name[0:-2]
			temp = group[0]	# Part object
			iter = self.bom_store.append([group_name, temp.value, temp.device, temp.package, temp.description, temp.product, self.active_bom.val_counts[val]])
		
		self.bom_tree_view.columns_autosize()
	
	def bom_store_populate_by_product(self):
		''' Clear self.bom_store and repopulate it, grouped by part number. '''	
		self.bom_store.clear()
		self.active_bom.sort_by_prod()
		self.active_bom.set_prod_counts(wspace)
		
		for prod in self.active_bom.prod_counts.keys():
			group_name = "\t"	# Clear group_name and prepend a tab
			print "Querying with prod =", prod, " of length ", len(prod)
			# Catch empty product string
			if prod == ' ' or len(prod) == 0 or prod == 'none' or prod == 'NULL': 
				print "Caught empty product"
				group = self.active_bom.select_parts_by_product('NULL', wspace)
			else:
				group = self.active_bom.select_parts_by_product(prod, wspace)
			print "Group: \n", group
			for part in group:	# TODO: Ensure this data is what we expect
				group_name += part.name + ", "
			
			# Replace trailing comma with tab
			group_name = group_name[0:-2]
			
			temp = group[0]	# Part object
			iter = self.bom_store.append([group_name, temp.value, temp.device, temp.package, temp.description, temp.product, self.active_bom.prod_counts[prod]])
		
		self.bom_tree_view.columns_autosize()
	
	def set_part_info_labels(self, prod):
		'''Set the Part Information pane fields based on the fields of a given 
		product object.'''	
		self.part_info_manufacturer_content_label.set_text(prod.manufacturer)
		self.part_info_manufacturer_pn_content_label.set_text(prod.manufacturer_pn)
		self.part_info_description_content_label.set_text(prod.description)
		self.part_info_datasheet_content_label.set_text(prod.datasheet)
		self.part_info_package_content_label.set_text(prod.package)

	def clear_part_info_labels(self):
		'''Clears the Part Information pane fields, setting the text of each Label
		object to a tab character.'''
		self.part_info_manufacturer_content_label.set_text("\t")
		self.part_info_manufacturer_pn_content_label.set_text("\t")
		self.part_info_description_content_label.set_text("\t")
		self.part_info_datasheet_content_label.set_text("\t")
		self.part_info_package_content_label.set_text("\t")
	
	def set_part_info_listing_combo(self, prod=None):
		''' Populates self.part_info_listing_combo with listings
		for the selected Product. '''
		print 'Setting Listing combo...'
		self.part_info_listing_combo.get_model().clear()
		
		if type(prod) is not types.NoneType and prod.manufacturer_pn != 'NULL':
			for listing in prod.listings.keys():
				#print 'Listing: ', type(listing), listing
				title = listing
				#print 'Appending combo title: ', title
				self.part_info_listing_combo.append_text(title)
		
		# TODO: Set default active to user-selected listing
		# If the user has not chosen one, that defaults to prod.best_listing
		self.part_info_listing_combo.set_active(0)
		self.part_info_vbox.show_all()
	
	def destroy_part_price_labels(self):
		for r in self.price_break_labels:
			r.destroy()
			
		for r in self.unit_price_labels:
			r.destroy()
			
		for r in self.ext_price_labels:
			r.destroy()
			
		del self.price_break_labels[:]
		del self.unit_price_labels[:]
		del self.ext_price_labels[:]
		
	def set_part_price_labels(self, listing):
		''' Given a listing, sets the pricing table labels. '''
		n = len(listing.prices)
		#print "n =", n
		price_keys = sorted(listing.prices.keys())
		#print "listing.prices = \n", listing.prices
		#print "sorted(listing.prices.keys()) = \n", price_keys
		self.part_info_pricing_table.resize(n+1, 3)
		self.destroy_part_price_labels()
		
		self.price_break_labels.append(gtk.Label("Price Break"))
		self.unit_price_labels.append(gtk.Label("Unit Price"))
		self.ext_price_labels.append(gtk.Label("Extended Price"))
		
		self.part_info_pricing_table.attach(self.price_break_labels[0],  0, 1, 0, 1)
		self.part_info_pricing_table.attach(self.unit_price_labels[0],  1, 2, 0, 1)
		self.part_info_pricing_table.attach(self.ext_price_labels[0],  2, 3, 0, 1)
		
		row_num = 1
		for i in range(n):
			#price_keys[i] is a key of listing.prices()
			self.price_break_labels.append(gtk.Label(str(price_keys[i]) + '   '))
			self.price_break_labels[row_num].set_alignment(0.5, 0.5)
			self.unit_price_labels.append(gtk.Label(str(listing.prices[price_keys[i]]) + '   '))
			self.unit_price_labels[row_num].set_alignment(1.0, 0.5)
			self.ext_price_labels.append(gtk.Label(str( price_keys[i] *  listing.prices[price_keys[i]]) + '   '))
			self.ext_price_labels[row_num].set_alignment(1.0, 0.5)
			
			self.part_info_pricing_table.attach(self.price_break_labels[row_num],  0, 1, row_num, row_num+1)
			self.part_info_pricing_table.attach(self.unit_price_labels[row_num],  1, 2, row_num, row_num+1)
			self.part_info_pricing_table.attach(self.ext_price_labels[row_num],  2, 3, row_num, row_num+1)
			row_num += 1
			
		self.part_info_frame.show_all()
		
	def __init__(self):
		# -------- DECLARATIONS --------
		self.active_bom = BOM('dummy', 'Active BOM Declaration', input_file)
		self.active_project_name = 'dummy'
		
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.main_box = gtk.VBox(False, 0)
		self.menu_bar = gtk.MenuBar()
		self.notebook = gtk.Notebook()
		self.project_tab_label = gtk.Label("Projects")
		self.bom_tab_label = gtk.Label("BOM Editor")
		self.db_tab_label = gtk.Label("Product Database")
		
		# --- Projects tab ---
		self.project_box = gtk.VBox(False, 0) # First tab in notebook
		self.project_toolbar = gtk.Toolbar()
		self.project_new_button = gtk.ToolButton(None, "New Project")
		self.project_open_button = gtk.ToolButton(None, "Open Project")
		self.project_edit_button = gtk.ToolButton(None, "Edit Project")
		self.project_delete_button = gtk.ToolButton(None, "Delete Project")
		self.project_frame = gtk.Frame("Projects") 
		self.project_scroll_win = gtk.ScrolledWindow()
		
		# New Project menu
		self.new_project_dialog = gtk.Dialog('New Project', self.window, 
										gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, 
										(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		
		self.new_project_name_hbox = gtk.HBox()
		self.new_project_description_hbox = gtk.HBox()
		#self.new_project_workspace_hbox = gtk.HBox()
		self.new_project_input_file_hbox = gtk.HBox()
		
		self.new_project_name_label = gtk.Label("Name: ")
		self.new_project_description_label = gtk.Label("Description: ")
		#self.new_project_workspace_label = gtk.Label("Workspace: ")
		self.new_project_input_file_label = gtk.Label("Input file: ")
		
		self.new_project_name_entry = gtk.Entry()
		self.new_project_description_entry = gtk.Entry()
		# TODO: Add a database file Entry/FileDialog when adding multiple DB file support
		self.new_project_input_file_button = gtk.Button('Browse', gtk.STOCK_OPEN)
		self.new_project_input_file_entry = gtk.Entry()
		self.input_file_dialog = gtk.FileChooserDialog('Select Input File', 
													self.new_project_dialog, gtk.FILE_CHOOSER_ACTION_OPEN, 
													(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		
		self.project_name_taken_dialog = gtk.MessageDialog(self.new_project_dialog, 
												gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, 
												gtk.BUTTONS_OK, 'Error: Project name in use. \nPlease select a different name.')
		
		# Projects list
		# Columns: Name, Description, Workspace, Input File
		self.project_store = gtk.ListStore(str, str, str, str)
		self.project_name_cell = gtk.CellRendererText()
		self.project_name_column = gtk.TreeViewColumn('Name', self.project_name_cell)
		self.project_description_cell = gtk.CellRendererText()
		self.project_description_column = gtk.TreeViewColumn('Description', self.project_description_cell)
		self.project_workspace_cell = gtk.CellRendererText()
		self.project_workspace_column = gtk.TreeViewColumn('Workspace', self.project_workspace_cell)
		self.project_input_file_cell = gtk.CellRendererText()
		self.project_input_file_column = gtk.TreeViewColumn('Input File', self.project_input_file_cell)
		self.project_tree_view = gtk.TreeView() # Associate with self.project_store later, not yet!
		
		# --- BOM tab ---
		self.bom_tab_vbox = gtk.VBox(False, 0) # Second tab in notebook
		self.bom_toolbar = gtk.Toolbar()
		self.bom_read_input_button = gtk.ToolButton(None, "Read CSV")
		self.bom_read_db_button = gtk.ToolButton(None, "Read DB")
		self.bom_edit_part_button = gtk.ToolButton(None, "Edit Part")
		self.bom_hpane = gtk.HPaned()	
		self.bom_vpane = gtk.VPaned()	# Goes in right side of bom_hpane
		
		self.bom_frame = gtk.Frame("BOM") # Goes in left side of bom_hpane
		self.bom_scroll_box = gtk.VBox(False, 0) # Holds bom_scroll_win and bom_radio_hbox
		self.bom_scroll_win = gtk.ScrolledWindow() # Holds bomTable
		
		# Columns: Name, Value, Device, Package, Description, MFG PN, Quantity
		self.bom_store = gtk.ListStore(str, str, str, str, str, str, int)
									
		self.bom_name_cell = gtk.CellRendererText()
		self.bom_name_column = gtk.TreeViewColumn('Name', self.bom_name_cell)
		self.bom_value_cell = gtk.CellRendererText()
		self.bom_value_column = gtk.TreeViewColumn('Value', self.bom_value_cell)
		self.bom_device_cell = gtk.CellRendererText()
		self.bom_device_column = gtk.TreeViewColumn('Device', self.bom_device_cell)
		self.bom_package_cell = gtk.CellRendererText()
		self.bom_package_column = gtk.TreeViewColumn('Package', self.bom_package_cell)
		self.bom_description_cell = gtk.CellRendererText()
		self.bom_description_column = gtk.TreeViewColumn('Description', self.bom_description_cell)
		self.bom_product_cell = gtk.CellRendererText()
		self.bom_product_column = gtk.TreeViewColumn('Manufacturer Part Number', self.bom_product_cell)
		self.bom_quantity_cell = gtk.CellRendererText()
		self.bom_quantity_column = gtk.TreeViewColumn('Quantity', self.bom_quantity_cell)
		
		self.bom_tree_view = gtk.TreeView()
		
		self.bom_radio_hbox = gtk.HBox(False, 0)
		self.bom_radio_label = gtk.Label("Group by:")
		self.bom_group_name = gtk.RadioButton(None, "Name")
		self.bom_group_value = gtk.RadioButton(self.bom_group_name, "Value")
		self.bom_group_product = gtk.RadioButton(self.bom_group_name, "Part Number")
		
		self.bom_selected_product = Product("init", "init", wspace)
		self.selected_bom_part = Part("init", "init", "init", "init", self.active_bom)
		
		self.part_info_frame = gtk.Frame("Part information") # Goes in top half of bom_vpane
		self.part_info_vbox = gtk.VBox(False, 5) # Fill with HBoxes 
		
		self.part_info_product_table = gtk.Table(5, 2, False) # Product info
		self.part_info_manufacturer_label = gtk.Label("Manufacturer: ")
		self.part_info_manufacturer_content_label = gtk.Label(None)
		self.part_info_manufacturer_pn_label = gtk.Label("Manufacturer Part Number: ")
		self.part_info_manufacturer_pn_content_label = gtk.Label(None)
		self.part_info_description_label = gtk.Label("Description: ")
		self.part_info_description_content_label = gtk.Label(None)
		self.part_info_datasheet_label = gtk.Label("Datasheet filename: ")
		self.part_info_datasheet_content_label = gtk.Label(None)
		self.part_info_package_label = gtk.Label("Package/case: ")
		self.part_info_package_content_label = gtk.Label(None)
		
		self.part_info_pricing_table = gtk.Table(8, 3 , False) # Price breaks
		self.price_break_labels = []
		
		self.unit_price_labels = []
		
		self.ext_price_labels = []
		
		self.part_info_button_hbox = gtk.HBox(False, 5)

		self.part_info_scrape_button = gtk.Button("Scrape")
		self.part_info_datasheet_button = gtk.Button("Datasheet")
		
		self.part_info_listing_label = gtk.Label("Product source: ")
		self.part_info_listing_combo = gtk.combo_box_new_text()
		
		self.part_info_inventory_hbox = gtk.HBox(False, 5)
		self.part_info_inventory_label = gtk.Label("Inventory: ")
		self.part_info_inventory_content_label = gtk.Label(None)
		
		self.pricing_frame = gtk.Frame("Project pricing") # Goes in bottom half of bom_vpane
		self.pricing_vbox = gtk.VBox(False, 5)
		self.run_size_pin_label = gtk.Label("Run size: ")
		#self.run_size_hbox = gtk.HBox(False, 5)
		self.run_size_adjustment = gtk.Adjustment(1, 1, 99999, 1, 10, 0.0)
		self.run_size_spin = gtk.SpinButton(self.run_size_adjustment, 0.5, 0)
		self.run_unit_price_hbox = gtk.HBox(False, 5)
		self.run_unit_price_label= gtk.Label("Per-kit BOM cost: ")
		self.run_unit_price_content_label= gtk.Label("\t")
		self.run_total_price_hbox = gtk.HBox(False, 5)
		self.run_total_cost_label= gtk.Label("Total run cost: ")
		self.run_total_cost_content_label= gtk.Label("\t")
		
		# --- Product DB tab ---
		self.db_vbox = gtk.VBox(False, 0) # Third tab in notebook
		self.db_toolbar = gtk.Toolbar()
		self.db_read_database_button = gtk.ToolButton(None, "Read DB")
		self.db_frame = gtk.Frame("Product database") 
		self.db_scroll_win = gtk.ScrolledWindow()
		
		#self.db_product_store = gtk.ListStore(str, str, int, str, str, str, str, str, str, str, str)
		self.db_product_store = gtk.ListStore(str, str, str, str, str)
									
		#self.dbVendorCell = gtk.CellRendererText()
		#self.dbVendorColumn = gtk.TreeViewColumn('Vendor', self.dbVendorCell)
		#self.dbvendor_pnCell = gtk.CellRendererText()
		#self.dbvendor_pnColumn = gtk.TreeViewColumn('Vendor PN', self.dbvendor_pnCell)
		#self.dbInventoryCell = gtk.CellRendererText()
		#self.dbInventoryColumn = gtk.TreeViewColumn('Inventory', self.dbInventoryCell)
		self.db_manufacturer_cell = gtk.CellRendererText()
		self.db_manufacturer_column = gtk.TreeViewColumn('Manufacturer', self.db_manufacturer_cell)
		self.db_manufacturer_pn_cell = gtk.CellRendererText()
		self.db_manufacturer_pn_column = gtk.TreeViewColumn('Manufacturer PN', self.db_manufacturer_pn_cell)
		self.db_description_cell = gtk.CellRendererText()
		self.db_description_column = gtk.TreeViewColumn('Description', self.db_description_cell)
		self.db_datasheet_cell = gtk.CellRendererText()
		self.db_datasheet_column = gtk.TreeViewColumn('Datasheet filename', self.db_datasheet_cell)
		#self.dbCategoryCell = gtk.CellRendererText()
		#self.dbCategoryColumn = gtk.TreeViewColumn('Category', self.dbCategoryCell)
		#self.dbFamilyCell = gtk.CellRendererText()
		#self.dbFamilyColumn = gtk.TreeViewColumn('Family', self.dbFamilyCell)
		#self.dbSeriesCell = gtk.CellRendererText()
		#self.dbSeriesColumn = gtk.TreeViewColumn('Series', self.dbSeriesCell)
		self.db_package_cell = gtk.CellRendererText()
		self.db_package_column = gtk.TreeViewColumn('Package/case', self.db_package_cell)
		
		self.db_tree_view = gtk.TreeView()
		
		# -------- CONFIGURATION --------
		self.window.set_title("Eagle BOM Manager") 
		# TODO: Add project name to window title on file open
		self.window.connect("delete_event", self.delete_event)
		self.window.connect("destroy", self.destroy)
		
		self.notebook.set_tab_pos(gtk.POS_TOP)
		self.notebook.append_page(self.project_box, self.project_tab_label)
		self.notebook.append_page(self.bom_tab_vbox, self.bom_tab_label)
		self.notebook.append_page(self.db_vbox, self.db_tab_label)
		self.notebook.set_show_tabs(True)
		
		# ---- Project selection tab ----
		self.project_new_button.connect("clicked", self.project_new_callback)
		self.new_project_input_file_button.connect("clicked", self.new_project_input_file_callback)
		
		self.project_open_button.connect("clicked", self.project_open_callback)
		
		self.new_project_name_label.set_alignment(0.0, 0.5)
		self.new_project_description_label.set_alignment(0.0, 0.5)
		#self.new_projectWorkspaceLabel.set_alignment(0.0, 0.5)
		self.new_project_input_file_label.set_alignment(0.0, 0.5)
		
		self.project_scroll_win.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		#self.project_tree_view.set_fixed_height_mode(True)
		self.project_tree_view.set_reorderable(True)
		self.project_tree_view.set_headers_clickable(True)
		
		self.project_name_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.project_description_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.project_workspace_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.project_input_file_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		
		self.project_name_column.set_resizable(True)
		self.project_description_column.set_resizable(True)
		self.project_workspace_column.set_resizable(True)
		self.project_input_file_column.set_resizable(True)
		
		self.project_name_column.set_attributes(self.project_name_cell, text=0)
		self.project_description_column.set_attributes(self.project_description_cell, text=1)
		self.project_workspace_column.set_attributes(self.project_workspace_cell, text=2)
		self.project_input_file_column.set_attributes(self.project_input_file_cell, text=3)
		
		self.project_tree_view.append_column(self.project_name_column)
		self.project_tree_view.append_column(self.project_description_column)
		self.project_tree_view.append_column(self.project_workspace_column)
		self.project_tree_view.append_column(self.project_input_file_column)
		self.project_store_populate()
		self.project_tree_view.set_model(self.project_store)
		
		# ---- BOM tab ----
		
		self.bom_name_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bom_value_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bom_device_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bom_package_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bom_description_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bom_product_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.bom_quantity_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		
		self.bom_name_column.set_resizable(True)
		self.bom_value_column.set_resizable(True)
		self.bom_device_column.set_resizable(True)
		self.bom_package_column.set_resizable(True)
		self.bom_description_column.set_resizable(True)
		self.bom_product_column.set_resizable(True)
		self.bom_quantity_column.set_resizable(True)
		
		self.bom_name_column.set_clickable(True)
		self.bom_value_column.set_clickable(True)
		self.bom_device_column.set_clickable(True)
		self.bom_package_column.set_clickable(True)
		self.bom_description_column.set_clickable(True)
		self.bom_product_column.set_clickable(True)
		self.bom_quantity_column.set_clickable(True)
		
		#self.bom_name_column.set_sort_indicator(True)
		#self.bom_value_column.set_sort_indicator(True)
		#self.bom_device_column.set_sort_indicator(True)
		#self.bom_package_column.set_sort_indicator(True)
		#self.bom_description_column.set_sort_indicator(True)
		#self.bom_product_column.set_sort_indicator(True)
		#self.bom_quantity_column.set_sort_indicator(True)
		
		self.bom_name_column.set_attributes(self.bom_name_cell, text=0)
		self.bom_value_column.set_attributes(self.bom_value_cell, text=1)
		self.bom_device_column.set_attributes(self.bom_device_cell, text=2)
		self.bom_package_column.set_attributes(self.bom_package_cell, text=3)
		self.bom_description_column.set_attributes(self.bom_description_cell, text=4)
		self.bom_product_column.set_attributes(self.bom_product_cell, text=5)
		self.bom_quantity_column.set_attributes(self.bom_quantity_cell, text=6)
		
		self.bom_name_column.connect("clicked", self.bom_sort_callback)
		self.bom_value_column.connect("clicked", self.bom_sort_callback)
		self.bom_device_column.connect("clicked", self.bom_sort_callback)
		self.bom_package_column.connect("clicked", self.bom_sort_callback)
		self.bom_description_column.connect("clicked", self.bom_sort_callback)
		self.bom_product_column.connect("clicked", self.bom_sort_callback)
		self.bom_quantity_column.connect("clicked", self.bom_sort_callback)
		
		self.bom_tree_view.set_reorderable(True)
		self.bom_tree_view.set_enable_search(True)
		self.bom_tree_view.set_headers_clickable(True)
		self.bom_tree_view.set_headers_visible(True)
		
		self.bom_tree_view.append_column(self.bom_name_column)
		self.bom_tree_view.append_column(self.bom_value_column)
		self.bom_tree_view.append_column(self.bom_device_column)
		self.bom_tree_view.append_column(self.bom_package_column)
		self.bom_tree_view.append_column(self.bom_description_column)
		self.bom_tree_view.append_column(self.bom_product_column)
		self.bom_tree_view.append_column(self.bom_quantity_column)
		#self.project_store_populate()
		
		self.bom_tree_view.connect("cursor-changed", self.bom_selection_callback)
		self.bom_tree_view.set_model(self.bom_store)
		
		self.bom_read_input_button.connect("clicked", self.read_input_callback, "read")
		self.bom_read_db_button.connect("clicked", self.bom_read_db_callback, "read")
		self.bom_edit_part_button.connect("clicked", self.bom_edit_part_callback, "setPN")
		
		self.bom_scroll_win.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		
		# TODO: Fiddle with bom_table sizing to make it force the window larger to fit
		
		self.bom_group_name.connect("toggled", self.bom_group_callback, "name")
		self.bom_group_value.connect("toggled", self.bom_group_callback, "value")
		self.bom_group_product.connect("toggled", self.bom_group_callback, "product")
		
		# --- Part Info frame ---
		self.part_info_inventory_label.set_alignment(0.0, 0.5)
		self.part_info_inventory_content_label.set_alignment(0.0, 0.5)
		self.part_info_manufacturer_label.set_alignment(0.0, 0.5)
		self.part_info_manufacturer_content_label.set_alignment(0.0, 0.5)
		self.part_info_manufacturer_pn_label.set_alignment(0.0, 0.5)
		self.part_info_manufacturer_pn_content_label.set_alignment(0.0, 0.5)
		self.part_info_description_label.set_alignment(0.0, 0.5)
		self.part_info_description_content_label.set_alignment(0.0, 0.5)
		self.part_info_datasheet_label.set_alignment(0.0, 0.5)
		self.part_info_datasheet_content_label.set_alignment(0.0, 0.5)
		self.part_info_package_label.set_alignment(0.0, 0.5)
		self.part_info_package_content_label.set_alignment(0.0, 0.5)
		self.part_info_scrape_button.connect("clicked", self.part_info_scrape_button_callback)
		self.part_info_listing_label.set_alignment(0.0, 0.5)
		self.part_info_listing_combo.connect("changed", self.part_info_listing_combo_callback)
		
		# --- Pricing frame ---
		self.run_size_pin_label.set_alignment(0.0, 0.5)
		self.run_unit_price_label.set_alignment(0.0, 0.5)
		self.run_unit_price_content_label.set_alignment(0.0, 0.5)
		self.run_total_cost_label.set_alignment(0.0, 0.5)
		self.run_total_cost_content_label.set_alignment(0.0, 0.5)
		self.run_size_spin.set_numeric(True)
		self.run_size_spin.set_update_policy(gtk.UPDATE_IF_VALID)
		self.run_size_spin.connect("value-changed", self.order_size_spin_callback)
		#self.order_size_scale.set_draw_value(False)
		#self.order_size_scale.set_digits(0)
		
		# ---- Product DB tab ----
		
		self.db_scroll_win.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		self.db_read_database_button.connect("clicked", self.db_read_database_callback, "read")
		
		#self.dbVendorColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbvendor_pnColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbInventoryColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.db_manufacturer_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.db_manufacturer_pn_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.db_description_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.db_datasheet_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbCategoryColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbFamilyColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		#self.dbSeriesColumn.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		self.db_package_column.set_sizing(gtk.TREE_VIEW_COLUMN_GROW_ONLY)
		
		#self.dbVendorColumn.set_resizable(True)
		#self.dbvendor_pnColumn.set_resizable(True)
		#self.dbInventoryColumn.set_resizable(True)
		self.db_manufacturer_column.set_resizable(True)
		self.db_manufacturer_pn_column.set_resizable(True)
		self.db_description_column.set_resizable(True)
		self.db_datasheet_column.set_resizable(True)
		#self.dbCategoryColumn.set_resizable(True)
		#self.dbFamilyColumn.set_resizable(True)
		#self.dbSeriesColumn.set_resizable(True)
		self.db_package_column.set_resizable(True)
		
		#self.dbVendorColumn.set_clickable(True)
		#self.dbvendor_pnColumn.set_clickable(True)
		#self.dbInventoryColumn.set_clickable(True)
		self.db_manufacturer_column.set_clickable(True)
		self.db_manufacturer_pn_column.set_clickable(True)
		self.db_description_column.set_clickable(True)
		self.db_datasheet_column.set_clickable(True)
		#self.dbCategoryColumn.set_clickable(True)
		#self.dbFamilyColumn.set_clickable(True)
		#self.dbSeriesColumn.set_clickable(True)
		self.db_package_column.set_clickable(True)
		
		#self.dbVendorColumn.set_attributes(self.dbVendorCell, text=0)
		#self.dbvendor_pnColumn.set_attributes(self.dbvendor_pnCell, text=1)
		#self.dbInventoryColumn.set_attributes(self.dbInventoryCell, text=2)
		self.db_manufacturer_column.set_attributes(self.db_manufacturer_cell, text=0)
		self.db_manufacturer_pn_column.set_attributes(self.db_manufacturer_pn_cell, text=1)
		self.db_description_column.set_attributes(self.db_description_cell, text=2)
		self.db_datasheet_column.set_attributes(self.db_datasheet_cell, text=3)
		#self.dbCategoryColumn.set_attributes(self.dbCategoryCell, text=7)
		#self.dbFamilyColumn.set_attributes(self.dbFamilyCell, text=8)
		#self.dbSeriesColumn.set_attributes(self.dbSeriesCell, text=9)
		self.db_package_column.set_attributes(self.db_package_cell, text=4)
		
		#self.dbVendorColumn.connect("clicked", self.db_sort_callback)
		#self.dbvendor_pnColumn.connect("clicked", self.db_sort_callback)
		#self.dbInventoryColumn.connect("clicked", self.db_sort_callback)
		self.db_manufacturer_column.connect("clicked", self.db_sort_callback)
		self.db_manufacturer_pn_column.connect("clicked", self.db_sort_callback)
		self.db_description_column.connect("clicked", self.db_sort_callback)
		self.db_datasheet_column.connect("clicked", self.db_sort_callback)
		#self.dbCategoryColumn.connect("clicked", self.db_sort_callback)
		#self.dbFamilyColumn.connect("clicked", self.db_sort_callback)
		#self.dbSeriesColumn.connect("clicked", self.db_sort_callback)
		self.db_package_column.connect("clicked", self.db_sort_callback)
		
		self.db_tree_view.set_reorderable(True)
		self.db_tree_view.set_enable_search(True)
		self.db_tree_view.set_headers_clickable(True)
		self.db_tree_view.set_headers_visible(True)
		
		#self.db_tree_view.append_column(self.dbVendorColumn)
		#self.db_tree_view.append_column(self.dbvendor_pnColumn)
		#self.db_tree_view.append_column(self.dbInventoryColumn)
		self.db_tree_view.append_column(self.db_manufacturer_column)
		self.db_tree_view.append_column(self.db_manufacturer_pn_column)
		self.db_tree_view.append_column(self.db_description_column)
		self.db_tree_view.append_column(self.db_datasheet_column)
		#self.db_tree_view.append_column(self.dbCategoryColumn)
		#self.db_tree_view.append_column(self.dbFamilyColumn)
		#self.db_tree_view.append_column(self.dbSeriesColumn)
		self.db_tree_view.append_column(self.db_package_column)
		self.db_store_populate()
		
		self.db_tree_view.connect("cursor-changed", self.db_selection_callback)
		self.db_tree_view.set_model(self.db_product_store)
		
		# -------- PACKING AND ADDING --------
		self.main_box.pack_start(self.menu_bar, False)
		self.main_box.pack_start(self.notebook)
		self.window.add(self.main_box)
		
		# Project selection tab
		self.project_box.pack_start(self.project_toolbar, False)
		self.project_toolbar.insert(self.project_new_button, 0)
		self.project_toolbar.insert(self.project_open_button, 1)
		self.project_toolbar.insert(self.project_edit_button, 2)
		self.project_toolbar.insert(self.project_delete_button, 3)
		
		self.project_box.pack_start(self.project_frame)
		self.project_frame.add(self.project_scroll_win)
		self.project_scroll_win.add(self.project_tree_view)
		
		self.new_project_name_hbox.pack_start(self.new_project_name_label, False, True, 0)
		self.new_project_name_hbox.pack_end(self.new_project_name_entry, False, True, 0)
		
		self.new_project_description_hbox.pack_start(self.new_project_description_label, False, True, 0)
		self.new_project_description_hbox.pack_end(self.new_project_description_entry, False, True, 0)
		
		#self.new_project_workspace_hbox.pack_start(self.new_project_workspace_label, False, True, 0)
		#self.new_project_workspace_hbox.pack_end(self.new_project_workspace_entry, False, True, 0)
		
		self.new_project_input_file_hbox.pack_start(self.new_project_input_file_label, False, True, 0)
		self.new_project_input_file_hbox.pack_start(self.new_project_input_file_entry, False, True, 0)
		self.new_project_input_file_hbox.pack_end(self.new_project_input_file_button, False, True, 0)
		
		self.new_project_dialog.vbox.set_spacing(1)
		self.new_project_dialog.vbox.pack_start(self.new_project_name_hbox, True, True, 0)
		self.new_project_dialog.vbox.pack_start(self.new_project_description_hbox, True, True, 0)
		#self.new_project_dialog.vbox.pack_start(self.new_project_workspace_hbox, True, True, 0)
		self.new_project_dialog.vbox.pack_start(self.new_project_input_file_hbox, True, True, 0)
		
		self.new_project_dialog.vbox.show_all()
		
		# BOM tab elements
		
		self.bom_tab_vbox.pack_start(self.bom_toolbar, False)
		self.bom_toolbar.insert(self.bom_read_input_button, 0)
		self.bom_toolbar.insert(self.bom_read_db_button, 1)
		self.bom_toolbar.insert(self.bom_edit_part_button, 2)
		
		# TODO : Add toolbar elements
		
		self.bom_tab_vbox.pack_start(self.bom_hpane)
		self.bom_hpane.pack1(self.bom_frame, True, True)
		self.bom_hpane.add2(self.bom_vpane)
		self.bom_vpane.add1(self.part_info_frame)
		self.bom_vpane.add2(self.pricing_frame)
		
		# BOM Frame elements
		self.bom_frame.add(self.bom_scroll_box)
		
		self.bom_scroll_box.pack_start(self.bom_scroll_win, True, True, 0)
		self.bom_scroll_win.add(self.bom_tree_view)
		self.bom_scroll_box.pack_end(self.bom_radio_hbox, False, False, 0)

		self.bom_radio_hbox.pack_start(self.bom_radio_label)
		self.bom_radio_hbox.pack_start(self.bom_group_name)
		self.bom_radio_hbox.pack_start(self.bom_group_value)
		self.bom_radio_hbox.pack_start(self.bom_group_product)
		
		# Part info frame elements
		self.part_info_frame.add(self.part_info_vbox)
		self.part_info_vbox.pack_start(self.part_info_product_table, True, True, 5)
		#self.part_info_product_table.attach(self.partInfoVendorLabel1, 0, 1, 0, 1)
		#self.part_info_product_table.attach(self.partInfovendor_pnLabel1, 0, 1, 1, 2)
		#self.part_info_product_table.attach(self.part_info_inventory_label, 0, 1, 2, 3)
		self.part_info_product_table.attach(self.part_info_manufacturer_label, 0, 1, 0, 1)
		self.part_info_product_table.attach(self.part_info_manufacturer_pn_label, 0, 1, 1, 2)
		self.part_info_product_table.attach(self.part_info_description_label, 0, 1, 2, 3)
		self.part_info_product_table.attach(self.part_info_datasheet_label, 0, 1, 3, 4)
		#self.part_info_product_table.attach(self.partInfoCategoryLabel1, 0, 1, 7, 8)
		#self.part_info_product_table.attach(self.partInfoFamilyLabel1, 0, 1, 8, 9)
		#self.part_info_product_table.attach(self.partInfoSeriesLabel1, 0, 1, 9, 10)
		self.part_info_product_table.attach(self.part_info_package_label, 0, 1, 4, 5)
		
		#self.part_info_product_table.attach(self.partInfoVendorLabel2, 1, 2, 0, 1)
		#self.part_info_product_table.attach(self.partInfovendor_pnLabel2, 1, 2, 1, 2)
		#self.part_info_product_table.attach(self.part_info_inventory_content_label, 1, 2, 2, 3)
		self.part_info_product_table.attach(self.part_info_manufacturer_content_label, 1, 2, 0, 1)
		self.part_info_product_table.attach(self.part_info_manufacturer_pn_content_label, 1, 2, 1, 2)
		self.part_info_product_table.attach(self.part_info_description_content_label, 1, 2, 2, 3)
		self.part_info_product_table.attach(self.part_info_datasheet_content_label, 1, 2, 3, 4)
		#self.part_info_product_table.attach(self.partInfoCategoryLabel2, 1, 2, 7, 8)
		#self.part_info_product_table.attach(self.partInfoFamilyLabel2, 1, 2, 8, 9)
		#self.part_info_product_table.attach(self.partInfoSeriesLabel2, 1, 2, 9, 10)
		self.part_info_product_table.attach(self.part_info_package_content_label, 1, 2, 4, 5)
		
		self.part_info_vbox.pack_start(self.part_info_button_hbox, True, True, 5)
		self.part_info_button_hbox.pack_start(self.part_info_scrape_button, True, True, 5)
		self.part_info_button_hbox.pack_start(self.part_info_datasheet_button, True, True, 5)
		self.part_info_vbox.pack_start(self.part_info_listing_label, False, False, 0)
		self.part_info_vbox.pack_start(self.part_info_listing_combo, False, False, 0)
		self.part_info_inventory_hbox.pack_start(self.part_info_inventory_label, False, False, 0)
		self.part_info_inventory_hbox.pack_start(self.part_info_inventory_content_label, False, False, 0)
		self.part_info_vbox.pack_start(self.part_info_inventory_hbox, False, False, 0)
		self.part_info_vbox.pack_start(self.part_info_pricing_table, True, True, 5)
		
		# Pricing frame elements
		self.pricing_frame.add(self.pricing_vbox)
		self.pricing_vbox.pack_start(self.run_size_pin_label, False, False, 0)
		#self.pricing_vbox.pack_start(self.run_size_hbox, False, False, 0)
		#self.run_size_hbox.pack_start(self.run_size_spin, False, False, 0)
		self.pricing_vbox.pack_start(self.run_size_spin, False, False, 0)
		self.pricing_vbox.pack_start(self.run_unit_price_hbox, False, False, 0)
		self.run_unit_price_hbox.pack_start(self.run_unit_price_label, False, False, 0)
		self.run_unit_price_hbox.pack_start(self.run_unit_price_content_label, False, False, 0)
		self.pricing_vbox.pack_start(self.run_total_price_hbox, False, False, 0)
		self.run_total_price_hbox.pack_start(self.run_total_cost_label, False, False, 0)
		self.run_total_price_hbox.pack_start(self.run_total_cost_content_label, False, False, 0)
		
		# Product database tab elements
		self.db_vbox.pack_start(self.db_toolbar, False)
		self.db_toolbar.insert(self.db_read_database_button, 0)
		self.db_vbox.pack_start(self.db_frame)
		self.db_frame.add(self.db_scroll_win)
		self.db_scroll_win.add(self.db_tree_view)
		
		self.db_read_database_callback(None)
		# Show everything
		self.main_box.show_all()
		self.window.show()

def main():
	gtk.main()
	
if __name__ == "__main__":
	from product import *
	from part import Part
	from bom import BOM
	Manager()
	main()
