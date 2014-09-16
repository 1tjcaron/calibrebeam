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
        self.SENT_STAMP = '<p class="everlitStamp">THIS WAS ALREADY SENT TO EVERNOTE</p>'
        QDialog.__init__(self, gui)
        self.gui = gui
        self.do_user_config = do_user_config
        self.cached_prefs_notebook_guid = None

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

        self.sync_highlighted_button = QPushButton(
            'Send Highlighted', self)
        self.sync_highlighted_button.clicked.connect(self.send_selected_highlights_to_evernote)
        self.l.addWidget(self.sync_highlighted_button)

        self.send_new_button = QPushButton(
            'Send New', self)
        self.send_new_button.clicked.connect(self.send_only_new_highlights_to_evernote)
        self.l.addWidget(self.send_new_button)

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
        QMessageBox.about(self, 'About EVERLIT',
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
        #from calibre.ebooks.metadata.meta import set_metadata
        #####
        from calibre_plugins.everlit.deps.evernote.api.client import EvernoteClient
        import calibre_plugins.everlit.deps.evernote.edam.userstore.constants as UserStoreConstants
        import calibre_plugins.everlit.deps.evernote.edam.type.ttypes as Types
        
        auth_token = "S=s1:U=8e1d5:E=14cb7e8430d:C=1456037170f:P=1cd:A=en-devtoken:V=2:H=71043307034f4095ecf279d9094b3985"
        self.client = EvernoteClient(token=auth_token, sandbox=True)
        self.note_store = self.client.get_note_store()
        
    def send_selected_highlights_to_evernote(self):
        from calibre.gui2 import error_dialog, info_dialog
        self.connect_to_evernote()
        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Cannot send books to Evernote',
                             'No books selected', show=True)
        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        for book_id in ids:
            self.send_book_to_evernote(book_id)
        info_dialog(self, 'Updated files',
                'sent %d book highlights to Evernote!'%len(ids),
                show=True)
        
    def send_only_new_highlights_to_evernote(self):
        from calibre.gui2 import error_dialog, info_dialog
        self.connect_to_evernote()
        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Cannot send books to Evernote',
                             'No books selected', show=True)
        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        sent_count = 0
        for book_id in ids:
            if self.send_book_to_evernote_ifNb(book_id, True):
                sent_count = sent_count + 1
        info_dialog(self, 'Updated files',
                'sent %d book highlights to Evernote!'%sent_count,
                show=True)
        #from calibre.gui2 import error_dialog, info_dialog
        #info_dialog(self, "TODO", "THIS SHOULD SEND SOME HIGHLIGHTS", show=True)
        
    def send_book_to_evernote(self, book_id):
        return self.send_book_to_evernote_ifNb(book_id, False)

        
    #TODO: fix and refactor: make_evernote_content() will not return the html tags, silly!!!!
    def send_book_to_evernote_ifNb(self, book_id, dont_send_if_already_sent):
                # Get the current metadata for this book from the db
        mi = self.db.get_metadata(book_id, index_is_id=True,
                    get_cover=True, cover_as_data=True)
        myAnnotations = self.make_evernote_content(mi)
        
        if dont_send_if_already_sent and self.SENT_STAMP in myAnnotations:
            return False
    
        noteName = self.make_evernote_name(mi)
        self.create_note(noteName, myAnnotations, self.note_store)
        self.stamp_comments_ifNb(book_id)
        return True
    
    #stamp comments if need be
    def stamp_comments_ifNb(self, book_id):
        comments = self.db.comments(book_id, index_is_id=True) 
        comments = '' if comments == None else comments 
        commentStamp = self.SENT_STAMP
        if commentStamp not in comments:
            self.db.set_comment(book_id, commentStamp + comments)
            self.db.commit()
    
    
    def config(self):
        self.do_user_config(parent=self)
        # Apply the changes
        self.label.setText(prefs['hello_world_msg'])
           
    def make_evernote_name(self, metadata):
        return metadata.get('title')

    def make_evernote_content(self, metadata):
        annotations = metadata.get('comments')
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
        if prefs['tagsCsv']:
            note.tagNames = prefs['tagsCsv'].split(",")
        if prefs['notebook']:
            note.notebookGuid = self.create_evernote_notebook_if_not_exits()
        created_note = note_store.createNote(note)
        #print("Successfully created a new note with GUID: " + created_note.guid)
        
    def create_evernote_notebook_if_not_exits(self):
        nb_name = prefs['notebook']
        self.connect_to_evernote()
        nb_guid = self.get_notebook_guid_if_exists(nb_name)
        if nb_guid == None:
            notebook = Types.Notebook()
            notebook.name = nb_name
            created_nb = self.note_store.createNotebook(notebook)
            nb_guid = created_nb.guid
            self.cached_prefs_notebook_guid = nb_guid
            print("Successfully created a new notebook with GUID: " + created_nb.guid)
        return nb_guid

    def get_notebook_guid_if_exists(self, nb_name):
        if self.cached_prefs_notebook_guid != None:
            return self.cached_prefs_notebook_guid
        for nb in self.note_store.listNotebooks():
            if nb.name.lower() == nb_name.lower(): #TODO: make note of this caviat in docs
                print(nb_name + " Notebook exists already GUID: " + nb.guid)
                self.cached_prefs_notebook_guid = nb.guid
                return nb.guid
        return None
        