#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QWidget, QVBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from calibre.utils.config import JSONConfig

# This is where all preferences for this plugin will be stored
# Remember that this name (i.e. plugins/calibrebeam) is also
# in a global namespace, so make it as unique as possible.
# You should always prefix your config file name with plugins/,
# so as to ensure you dont accidentally clobber a calibre config file
prefs = JSONConfig('plugins/calibrebeam2')

# Set defaults
# prefs.defaults['hello_world_msg'] = 'beam highlights and annotations to evernote!'
prefs.defaults['notebook'] = ""
prefs.defaults['tagsCsv'] = ""
prefs.defaults['oauth_token'] = ""
prefs.defaults['oauth_username'] = ""


def save_username_and_token(username, token):
    prefs['oauth_username'] = username
    prefs['oauth_token'] = token


def get_username_and_token():
    return prefs['oauth_username'], prefs['oauth_token']


class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.about_button = QPushButton('Help', self)
        self.about_button.clicked.connect(self.about)
        self.l.addWidget(self.about_button)

        self.notebookLabel = QLabel('evernote Notebook')
        self.l.addWidget(self.notebookLabel)

        self.notebookMsg = QLineEdit(self)
        self.notebookMsg.setText(prefs['notebook'])
        self.l.addWidget(self.notebookMsg)
        self.notebookLabel.setBuddy(self.notebookMsg)
        
        self.tagsCsvLabel = QLabel('evernote Tags CSV (ie calibre,mykindle)')
        self.l.addWidget(self.tagsCsvLabel)

        self.tagsCsvMsg = QLineEdit(self)
        self.tagsCsvMsg.setText(prefs['tagsCsv'])
        self.l.addWidget(self.tagsCsvMsg)
        self.tagsCsvLabel.setBuddy(self.tagsCsvMsg)

    def save_settings(self):
        prefs['notebook'] = unicode(self.notebookMsg.text())
        prefs['tagsCsv'] = unicode(self.tagsCsvMsg.text())

    def about(self):
        text = get_resources('about.txt')
        QMessageBox.about(self, 'About calibrebeam',
                text.decode('utf-8'))
