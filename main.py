#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import urlparse, traceback
from PyQt5.Qt import QDialog, QVBoxLayout, QPushButton, QMessageBox, QLabel, QUrl

from calibre import prints
from calibre.constants import DEBUG
from calibre_plugins.calibrebeam.config import prefs
import calibre_plugins.calibrebeam.deps.evernote.edam.userstore.constants as UserStoreConstants
import calibre_plugins.calibrebeam.deps.evernote.edam.type.ttypes as Types
import calibre_plugins.calibrebeam.deps.oauth2 as oauth
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.constants import iswindows   
from calibre.gui2 import error_dialog, question_dialog, info_dialog, open_url     
import calibre_plugins.calibrebeam.config as cfg

URL = 'https://sandbox.evernote.com'
#URL = 'http://www.goodreads.com'
#URL_HTTPS = 'https://www.goodreads.com'
STORE_USERS = 'Users'
KEY_USER_ID = 'userId'
KEY_USER_TOKEN = 'userToken'
KEY_USER_SECRET = 'userSecret'

class calibrebeamDialog(QDialog):
    
    def __init__(self, gui, icon, do_user_config):
#TODO: edit to be per user stamp?
        self.SENT_STAMP = '<p class="calibrebeamStamp">COMMENTS ALREADY SENT TO EVERNOTE</p>'
        self.ANNOTATIONS_PRESENT_STRING = 'class="annotation"'
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
        
        self.devkey_token = "1tjcaron-3617"
        self.devkey_secret = "5f3e4368a027d923"

        self.setWindowTitle('Calibrebeam Evernote Sync')
        self.setWindowIcon(icon)
        self.initButtons()
        self.resize(self.sizeHint())
    
    def initButtons(self):
        self.about_button = QPushButton('About', self)
        self.about_button.clicked.connect(self.about)
        self.l.addWidget(self.about_button)

        self.sync_highlighted_button = QPushButton(
            'Beam Highlighted', self)
        self.sync_highlighted_button.clicked.connect(self.send_selected_highlights_to_evernote)
        self.l.addWidget(self.sync_highlighted_button)

        self.send_new_button = QPushButton(
            'Beam All Unsent Annotations', self)
        self.send_new_button.clicked.connect(self.send_only_new_highlights_to_evernote)
        self.l.addWidget(self.send_new_button)
        
        self.login_button = QPushButton(
            'login', self)
        self.login_button.clicked.connect(self.authorize_plugin)
        self.l.addWidget(self.login_button)

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
        QMessageBox.about(self, 'About calibrebeam',
                text.decode('utf-8'))
 
    def authorize_plugin(self):
        from calibre_plugins.calibrebeam.deps.evernote.api.client import EvernoteClient
        import calibre_plugins.calibrebeam.deps.evernote.edam.userstore.constants as UserStoreConstants
        import calibre_plugins.calibrebeam.deps.evernote.edam.type.ttypes as Types
        
        client = EvernoteClient(consumer_key=self.devkey_token,consumer_secret=self.devkey_secret, sandbox=True)
        self.client = client
        req_token = client.get_request_token(URL)
        authorize_link = client.get_authorize_url(req_token)
        open_url(QUrl(authorize_link))

        # Display dialog waiting for the user to confirm they have authorized in web browser
        if not question_dialog(self, 'Confirm Authorization', '<p>'+
                'Have you clicked \'Allow access\' for this plugin on the evernote website?'):
            return
        
    ##OAUTH OUT
        
    def connect_to_evernote(self):
        #from calibre.ebooks.metadata.meta import set_metadata
        #####
        from calibre_plugins.calibrebeam.deps.evernote.api.client import EvernoteClient
        import calibre_plugins.calibrebeam.deps.evernote.edam.userstore.constants as UserStoreConstants
        import calibre_plugins.calibrebeam.deps.evernote.edam.type.ttypes as Types
        from calibre_plugins.calibrebeam.deps.geeknote.oauth import GeekNoteAuth
        GNA = GeekNoteAuth()
        #TODO: should not hardcode these.....
        username = "1tjcaron"
        password = ""
        auth_token = GNA.getToken(username, password)
        if auth_token == "ERROR":
            return "ERROR"
        client = EvernoteClient(token=auth_token, sandbox=True)
        self.note_store = client.get_note_store()
        
        
    def send_selected_highlights_to_evernote(self):
        from calibre.gui2 import error_dialog, info_dialog
        self.connect_to_evernote()
        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Cannot beam highlights to Evernote',
                             'No books selected', show=True)
        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        for book_id in ids:
            self.send_book_to_evernote(book_id)
        info_dialog(self, 'Updated files',
                'beamed %d book highlights to Evernote!'%len(ids),
                show=True)
        
    def send_only_new_highlights_to_evernote(self):
        from calibre.gui2 import error_dialog, info_dialog
        self.connect_to_evernote()
        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Cannot beam highlights to Evernote',
                             'No books selected', show=True)
        # Map the rows to book ids
        #ids = list(map(self.gui.library_view.model().id, rows))
        ids = self.db.new_api.all_book_ids()
        sent_count = 0
        for book_id in ids:
            if self.send_book_to_evernote_ifNb(book_id, True):
                sent_count = sent_count + 1
        info_dialog(self, 'Updated files',
                'sent %d book highlights to Evernote!'%sent_count,
                show=True)
        #from calibre.gui2 import error_dialog, info_dialog
        
    def send_book_to_evernote(self, book_id):
        return self.send_book_to_evernote_ifNb(book_id, False)

    def send_book_to_evernote_ifNb(self, book_id, uses_send_filters):
                # Get the current metadata for this book from the db
        metadata = self.db.get_metadata(book_id, index_is_id=True,
                    get_cover=True, cover_as_data=True)
        
        if uses_send_filters:
            annotations_raw = self.get_annotations_raw_from_metadata(metadata)
            annotations_raw = '' if annotations_raw == None else annotations_raw
            if self.SENT_STAMP in annotations_raw:
                return False
            if self.ANNOTATIONS_PRESENT_STRING not in annotations_raw:
                return False
    
        noteName = self.make_evernote_name(metadata)
        myAnnotations = self.make_evernote_content(metadata)
        self.create_note(noteName, myAnnotations, self.note_store)
        self.stamp_annotations_ifNb(book_id)
        return True
    
    def get_annotations_raw(self, book_id):
        metadata = self.db.get_metadata(book_id, index_is_id=True,
            get_cover=True, cover_as_data=True)
        return self.get_annotations_raw_from_metadata(metadata)
    
    def get_annotations_raw_from_metadata(self, metadata):
        return metadata.get('comments')
    
    def set_annotations_raw(self, book_id, annotations):
        self.db.set_comment(book_id, annotations)
        self.db.commit()
    
    #stamp annotations if need be
    def stamp_annotations_ifNb(self, book_id):
        annotes = self.get_annotations_raw(book_id) 
        annotes = '' if annotes == None else annotes 
        commentStamp = self.SENT_STAMP
        if commentStamp not in annotes:
            self.set_annotations_raw(book_id, commentStamp + annotes)
    
    
    def config(self):
        self.do_user_config(parent=self)
        # Apply the changes
        self.label.setText(prefs['hello_world_msg'])
           
    def make_evernote_name(self, metadata):
        return metadata.get('title')

    def make_evernote_content(self, metadata):
        annotations = self.get_annotations_raw_from_metadata(metadata)
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
        
