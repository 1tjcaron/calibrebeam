#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

if False:
    # This is here to keep my python error checker from complaining about
    # the builtin functions that will be defined by the plugin loading system
    # You do not need this code in your plugins
    get_icons = get_resources = None

from PyQt4.Qt import QDialog, QVBoxLayout, QPushButton, QMessageBox, QLabel

from calibre_plugins.everlit.config import prefs
import calibre_plugins.everlit.deps.evernote.edam.userstore.constants as UserStoreConstants
import calibre_plugins.everlit.deps.evernote.edam.type.ttypes as Types
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.constants import iswindows        

class EverlitDialog(QDialog):

    def __init__(self, gui, icon, do_user_config):
        QDialog.__init__(self, gui)
        self.gui = gui
        self.do_user_config = do_user_config

        # The current database shown in the GUI
        # db is an instance of the class LibraryDatabase2 from database.py
        # This class has many, many methods that allow you to do a lot of
        # things.
        self.db = gui.current_db

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.label = QLabel(prefs['hello_world_msg'])
        self.l.addWidget(self.label)

        self.setWindowTitle('everlit Evernote Sync')
        self.setWindowIcon(icon)
        self.initButtons()
        self.resize(self.sizeHint())
    
    def initButtons(self):
        self.about_button = QPushButton('About', self)
        self.about_button.clicked.connect(self.about)
        self.l.addWidget(self.about_button)

        self.marked_button = QPushButton(
            'Show sf books demo', self)
        self.marked_button.clicked.connect(self.marked)
        self.l.addWidget(self.marked_button)

        self.meta_button = QPushButton(
            'Sync', self)
        self.meta_button.clicked.connect(self.send_to_evernote)
        self.l.addWidget(self.meta_button)
        
        self.show_tags = QPushButton('Show All Tags', self)
        self.show_tags.clicked.connect(self.get_evernote_taglist)
        self.l.addWidget(self.show_tags)
        
        self.create_evernote_tag_bt = QPushButton('Create Calibre Tag', self)
        self.create_evernote_tag_bt.clicked.connect(self.create_evernote_notebook)
        self.l.addWidget(self.create_evernote_tag_bt)

    def about(self):
        # Get the about text from a file inside the plugin zip file
        # The get_resources function is a builtin function defined for all your
        # plugin code. It loads files from the plugin zip file. It returns
        # the bytes from the specified file.
        #
        # Note that if you are loading more than one file, for performance, you
        # should pass a list of names to get_resources. In this case,
        # get_resources will return a dictionary mapping names to bytes. Names that
        # are not found in the zip file will not be in the returned dictionary.
        text = get_resources('about.txt')
        QMessageBox.about(self, 'About the Interface Plugin Demo',
                text.decode('utf-8'))

    def marked(self):
        ''' Show books with only one format '''
        fmt_idx = self.db.FIELD_MAP['formats']
        matched_ids = set()
        for record in self.db.data.iterall():
            # Iterate over all records
            fmts = record[fmt_idx]
            # fmts is either None or a comma separated list of formats
            if fmts and ',' not in fmts:
                matched_ids.add(record[0])
        # Mark the records with the matching ids
        self.db.set_marked_ids(matched_ids)

        # Tell the GUI to search for all marked records
        self.gui.search.setEditText('marked:true')
        self.gui.search.do_search()

    def connect_to_evernote(self):
        '''
        Set the metadata in the files in the selected book's record to
        match the current metadata in the database.
        '''
        #from calibre.ebooks.metadata.meta import set_metadata
        #####
        from calibre_plugins.everlit.deps.evernote.api.client import EvernoteClient
        import calibre_plugins.everlit.deps.evernote.edam.userstore.constants as UserStoreConstants
        import calibre_plugins.everlit.deps.evernote.edam.type.ttypes as Types
        
        auth_token = "S=s1:U=8e1d5:E=14cb7e8430d:C=1456037170f:P=1cd:A=en-devtoken:V=2:H=71043307034f4095ecf279d9094b3985"
        self.client = EvernoteClient(token=auth_token, sandbox=True)
        self.note_store = self.client.get_note_store()
        
    def send_to_evernote(self):
        from calibre.gui2 import error_dialog, info_dialog
        self.connect_to_evernote()
        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Cannot update metadata',
                             'No books selected', show=True)
        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        for book_id in ids:
            # Get the current metadata for this book from the db
            mi = self.db.get_metadata(book_id, index_is_id=True,
                    get_cover=True, cover_as_data=True)
            myAnnotations = self.make_evernote_content(mi)
            noteName = self.make_evernote_name(mi)
            self.create_note(noteName, myAnnotations, self.note_store)

        info_dialog(self, 'Updated files',
                'Updated the metadata in the files of %d book(s)'%len(ids),
                show=True)
        
    def get_evernote_taglist(self):
        self.connect_to_evernote()
        print(self.note_store.listTags())

    def config(self):
        self.do_user_config(parent=self)
        # Apply the changes
        self.label.setText(prefs['hello_world_msg'])
           
    def make_evernote_name(self, metadata):
        return metadata.get('title')

    def make_evernote_content(self, metadata):
        annotations = metadata.get('#mm_annotations')
        soup = BeautifulSoup(annotations)
        plainAnnotations = '<div>' + '</div>\n<div> '.join(soup.findAll(text=True)) + '</div>'    
        myAnnotations = plainAnnotations.encode('ascii', errors='ignore').encode('utf-8')        
        content = '<?xml version="1.0" encoding="UTF-8"?>'
        content += '<!DOCTYPE en-note SYSTEM ' \
            '"http://xml.evernote.com/pub/enml2.dtd">'
        content += '<en-note>'
        content += myAnnotations
        content += '</en-note>'
        return content
           
    def create_note(self, title, content, note_store): 
        # To create a new note, simply create a new Note object and fill in
        # attributes such as the note's title.
        note = Types.Note()
        note.title = title
        note.content = content
        note.tagNames = ['yo', 'calibre']
        created_note = note_store.createNote(note)
        print("Successfully created a new note with GUID: " + created_note.guid)
        
    #TODO: convert this into createNoteOrGetExistingGuid, return guid
    def create_evernote_notebook(self):
        self.connect_to_evernote()
        notebook = Types.Notebook()
        notebook.name = "Books"
        created_tag = self.note_store.createNotebook(notebook)
        print("Successfully created a new notebook with GUID: " + created_tag.guid)
