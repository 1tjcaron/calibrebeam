#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, QHBoxLayout, QLabel, QLineEdit

from calibre.utils.config import JSONConfig

# This is where all preferences for this plugin will be stored
# Remember that this name (i.e. plugins/everlit) is also
# in a global namespace, so make it as unique as possible.
# You should always prefix your config file name with plugins/,
# so as to ensure you dont accidentally clobber a calibre config file
prefs = JSONConfig('plugins/everlit')

# Set defaults
prefs.defaults['hello_world_msg'] = 'Hello, World!'
prefs.defaults['notebook'] = 'bks'
prefs.defaults['tagsCsv'] = 'Calibre'

class ConfigWidget(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.l = QHBoxLayout()
        self.setLayout(self.l)

        self.label = QLabel('Hello world &message:')
        self.l.addWidget(self.label)

        self.msg = QLineEdit(self)
        self.msg.setText(prefs['hello_world_msg'])
        self.l.addWidget(self.msg)
        self.label.setBuddy(self.msg)
        
        self.notebookLabel = QLabel('Notebook')
        self.l.addWidget(self.notebookLabel)

        self.notebookMsg = QLineEdit(self)
        self.notebookMsg.setText(prefs['notebook'])
        self.l.addWidget(self.notebookMsg)
        self.notebooklabel.setBuddy(self.notebookMsg)
        
        self.tagsCsvLabel = QLabel('Tags CSV (ie calibre,mykindle)')
        self.l.addWidget(self.tagsCsvLabel)

        self.tagsCsvMsg = QLineEdit(self)
        self.tagsCsvMsg.setText(prefs['tagsCsv'])
        self.l.addWidget(self.tagsCsvMsg)
        self.tagsCsvLabel.setBuddy(self.tagsCsvMsg)

    def save_settings(self):
        prefs['hello_world_msg'] = unicode(self.msg.text())
        prefs['notebook'] = unicode(self.notebookMsg.text())
        prefs['tagsCsv'] = unicode(self.tagsCsvMsg.text())

