#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QDialog, QVBoxLayout, QPushButton, QMessageBox, QLabel, QUrl, QInputDialog, QDir

from calibre_plugins.calibrebeam.config import prefs
import calibre_plugins.calibrebeam.deps.evernote.edam.type.ttypes as Types
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.gui2 import error_dialog, question_dialog, info_dialog, open_url
import socket

class calibrebeamDialog(QDialog):
    
    def __init__(self, gui, icon, do_user_config):
        # TODO: edit to be per user stamp?
        self.SENT_STAMP = '<p class="calibrebeamStamp">COMMENTS ALREADY SENT TO EVERNOTE</p>'
        self.ANNOTATIONS_PRESENT_STRING = 'class="annotation"'
        self.note_store = None

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
        self.init_buttons()
        self.resize(self.sizeHint())


    def init_buttons(self):
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
        self.login_button.clicked.connect(self.create_new_note_store)
        self.l.addWidget(self.login_button)

        self.config_button = QPushButton(
            'config', self)
        self.config_button.clicked.connect(self.config)
        self.l.addWidget(self.config_button)


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

    def config(self):
        from evernote_connect import ConfigWidget
        ConfigWidget()

    def authorize_plugin(self):
        username, ok_u = QInputDialog.getText(self, 'Input Dialog', 'Enter your Evernote Username:')
        if not ok_u:
            return None, None
        password, ok_p = QInputDialog.getText(self, 'Input Dialog', 'Enter your Evernote password:')
        if not ok_p:
            return None, None
        permission_msg = u'''
        Do you want to allow calibrebeam to:
            \u2022 Create notes, notebooks and tags.
            \u2022 List notebooks and tags.
        '''
        if not question_dialog(self, 'Allow Access', permission_msg):
            return None, None

        return username, password

    def connect_to_evernote(self):
        if self.note_store:
            return self.note_store
        else:
            return self.create_note_store()

    def create_note_store(self):
        try:
            from calibre_plugins.calibrebeam.config import get_username_and_token
            username, auth_token = get_username_and_token()
            return self.create_new_note_store(username, auth_token)
        except socket.gaierror:
            info_dialog(self, 'INTERNET',
                        'connectivity is bad',
                        show=True)

    def get_auth_token(self, password, username):
        try:
            from calibre_plugins.calibrebeam.deps.geeknote.oauth import GeekNoteAuth
            gna = GeekNoteAuth()
            auth_token = gna.getToken(username, password)
            return auth_token
        except socket.gaierror or TypeError:
            info_dialog(self, 'INTERNET',
                        'connectivity is bad',
                        show=True)
            return None

    def create_new_note_store(self, username=None, auth_token=None):
        reset_stored_creds = False
        if not (username and auth_token):
            reset_stored_creds = True
            username, password = self.authorize_plugin()
            if not (username and password):
                return None
            auth_token = self.get_auth_token(password, username)
            if not auth_token:
                # timout or connectivity or something
                return None
            if auth_token == "ERROR":
                # probably typed wrong stuffs
                info_dialog(self, 'EVERNOTE',
                            'Could not login.  Please verify your Evernote username and password and try again.',
                            show=True)
                return None
        from calibre_plugins.calibrebeam.deps.evernote.api.client import EvernoteClient
        client = EvernoteClient(token=auth_token, sandbox=True)
        self.note_store = client.get_note_store()
        # if we successfully made a note store, then we should save this token for next bootup
        if reset_stored_creds:
            from calibre_plugins.calibrebeam.config import save_username_and_token
            save_username_and_token(username, auth_token)
        return self.note_store

    def send_selected_highlights_to_evernote(self):
        from calibre.gui2 import error_dialog, info_dialog
        if not self.connect_to_evernote():
            return
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
        if not self.connect_to_evernote():
            return
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
            if self.send_book_to_evernote_if_nb(book_id, True):
                sent_count = sent_count + 1
        info_dialog(self, 'Updated files',
                'sent %d book highlights to Evernote!'%sent_count,
                show=True)

        
    def send_book_to_evernote(self, book_id):
        return self.send_book_to_evernote_if_nb(book_id, False)


    def send_book_to_evernote_if_nb(self, book_id, uses_send_filters):
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
        self.stamp_annotations_if_nb(book_id)
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
    def stamp_annotations_if_nb(self, book_id):
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
        note = Types.Note()
        note.title = title
        note.content = content
        if prefs['tagsCsv']:
            note.tagNames = prefs['tagsCsv'].split(",")
        if prefs['notebook']:
            nb_guid = self.create_evernote_notebook_if_not_exits()
            if not nb_guid:
                return
            note.notebookGuid = nb_guid
        try:
            created_note = note_store.createNote(note)
        except socket.gaierror:
            info_dialog(self, 'INTERNET',
                        'connectivity is bad',
                        show=True)
            return


    def create_evernote_notebook_if_not_exits(self):
        nb_name = prefs['notebook']
        if not self.connect_to_evernote():
            return
        nb_guid = self.get_notebook_guid_if_exists(nb_name)
        if not nb_guid:
            notebook = Types.Notebook()
            notebook.name = nb_name
            try:
                created_nb = self.note_store.createNotebook(notebook)
            except socket.gaierror:
                info_dialog(self, 'INTERNET',
                            'connectivity is bad',
                            show=True)
                return
            nb_guid = created_nb.guid
            print("Successfully created a new notebook with GUID: " + created_nb.guid)
        return nb_guid


    def get_notebook_guid_if_exists(self, nb_name):
        try:
            for nb in self.note_store.listNotebooks():
                if nb.name.lower() == nb_name.lower(): # TODO: make note of this caviat in docs
                    print(nb_name + " Notebook exists already GUID: " + nb.guid)
                    self.cached_prefs_notebook_guid = nb.guid
                    return nb.guid
        except socket.gaierror:
            info_dialog(self, 'INTERNET',
                        'connectivity is bad',
                        show=True)
            return None

