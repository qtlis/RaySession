import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMenu, QInputDialog,
        QBoxLayout, QListWidgetItem, QFrame, QDialog, QDialogButtonBox,
        QFileDialog, QMessageBox, QCompleter, QAction, QToolButton,
        QAbstractItemView, QLabel, QLineEdit)
from PyQt5.QtGui import QIcon, QCursor, QPalette, QPixmap, QFontDatabase
from PyQt5.QtCore import (QTimer, QProcess, pyqtSignal, pyqtSlot, QObject,
                          QSize, Qt, QSettings, qDebug, QLocale, QTranslator)

from gui_tools import (RS, RayIcon, CommandLineArgs, _translate,
                       serverStatusString, isDarkTheme)
import add_application_dialog
import child_dialogs
import snapshots_dialog
from gui_server_thread import GUIServerThread
from gui_client import TrashedClient

import ray
import list_widget_clients

import ui_raysession
import ui_client_slot


class MainWindow(QMainWindow):
    def __init__(self, session):
        QMainWindow.__init__(self)
        self.ui = ui_raysession.Ui_MainWindow()
        self.ui.setupUi(self)

        self._session = session
        self._signaler = self._session._signaler
        self._daemon_manager = self._session._daemon_manager

        self.mouse_is_inside = False
        self.terminate_request = False

        # timer for keep focus while client opening
        self.timer_raisewin = QTimer()
        self.timer_raisewin.setInterval(50)
        self.timer_raisewin.timeout.connect(self.raiseWindow)

        # timer for flashing effect of 'open' status
        self.timer_flicker_open = QTimer()
        self.timer_flicker_open.setInterval(400)
        self.timer_flicker_open.timeout.connect(self.flashOpen)
        self.flash_open_list = []
        self.flash_open_bool = False
        
        # timer for too long snapshots, display snapshot progress dialog
        self.timer_snapshot = QTimer()
        self.timer_snapshot.setSingleShot(True)
        self.timer_snapshot.setInterval(2000)
        self.timer_snapshot.timeout.connect(self.showSnapshotProgressDialog)
        

        self.server_copying = False

        self.keep_focus = RS.settings.value('keepfocus', True, type=bool)
        self.ui.actionKeepFocus.setChecked(self.keep_focus)
        if RS.settings.value('MainWindow/geometry'):
            self.restoreGeometry(RS.settings.value('MainWindow/geometry'))
        if RS.settings.value('MainWindow/WindowState'):
            self.restoreState(RS.settings.value('MainWindow/WindowState'))
        self.ui.actionShowMenuBar.activate(RS.settings.value(
            'MainWindow/ShowMenuBar', False, type=bool))

        # set default action for tools buttons
        self.ui.closeButton.setDefaultAction(self.ui.actionCloseSession)
        self.ui.toolButtonSaveSession.setDefaultAction(
            self.ui.actionSaveSession)
        self.ui.toolButtonAbortSession.setDefaultAction(
            self.ui.actionAbortSession)
        self.ui.toolButtonDuplicateSession.setDefaultAction(
            self.ui.actionDuplicateSession)
        self.ui.toolButtonSaveTemplateSession.setDefaultAction(
            self.ui.actionSaveTemplateSession)
        self.ui.toolButtonFileManager.setDefaultAction(
            self.ui.actionOpenSessionFolder)
        self.ui.toolButtonAddApplication.setDefaultAction(
            self.ui.actionAddApplication)
        self.ui.toolButtonAddExecutable.setDefaultAction(
            self.ui.actionAddExecutable)
        self.ui.toolButtonSnapshots.setDefaultAction(
            self.ui.actionReturnToAPreviousState)

        # connect actions
        self.ui.actionNewSession.triggered.connect(self.createNewSession)
        self.ui.actionOpenSession.triggered.connect(self.openSession)
        self.ui.actionQuit.triggered.connect(self.quitApp)
        self.ui.actionSaveSession.triggered.connect(self.saveSession)
        self.ui.actionCloseSession.triggered.connect(self.closeSession)
        self.ui.actionAbortSession.triggered.connect(self.abortSession)
        self.ui.actionRenameSession.triggered.connect(
            self.renameSessionAction)
        self.ui.actionDuplicateSession.triggered.connect(
            self.duplicateSession)
        self.ui.actionSaveTemplateSession.triggered.connect(
            self.saveTemplateSession)
        self.ui.actionReturnToAPreviousState.triggered.connect(
            self.returnToAPreviousState)
        self.ui.actionOpenSessionFolder.triggered.connect(
            self.openFileManager)
        self.ui.actionAddApplication.triggered.connect(self.addApplication)
        self.ui.actionAddExecutable.triggered.connect(self.addExecutable)
        self.ui.actionKeepFocus.toggled.connect(self.toggleKeepFocus)
        self.ui.actionSaveAllFromSavedClient.triggered.connect(
            self.saveAllFromClientToggled)
        self.ui.actionBookmarkSessionFolder.triggered.connect(
            self.bookmarkSessionFolderToggled)
        self.ui.actionDesktopsMemory.triggered.connect(
            self.desktopsMemoryToggled)
        self.ui.actionAutoSnapshot.triggered.connect(
            self.autoSnapshotToggled)
        self.ui.actionAboutRaySession.triggered.connect(self.aboutRaySession)
        self.ui.actionAboutQt.triggered.connect(QApplication.aboutQt)
        self.ui.actionDonate.triggered.connect(self.donate)

        self.ui.lineEditServerStatus.statusPressed.connect(
            self.statusBarPressed)
        self.ui.stackedWidgetSessionName.name_changed.connect(
            self.renameSessionConditionnaly)
        
        # set control menu
        self.controlMenu = QMenu()
        self.controlMenu.addAction(self.ui.actionShowMenuBar)
        self.controlMenu.addAction(self.ui.actionToggleShowMessages)
        self.controlMenu.addSeparator()
        self.controlMenu.addAction(self.ui.actionKeepFocus)
        self.controlMenu.addSeparator()
        self.controlMenu.addAction(self.ui.actionSaveAllFromSavedClient)
        self.controlMenu.addAction(self.ui.actionBookmarkSessionFolder)
        self.controlMenu.addAction(self.ui.actionAutoSnapshot)
        self.controlMenu.addAction(self.ui.actionDesktopsMemory)

        self.controlToolButton = self.ui.toolBar.widgetForAction(
            self.ui.actionControlMenu)
        self.controlToolButton.setPopupMode(QToolButton.InstantPopup)
        self.controlToolButton.setMenu(self.controlMenu)

        self.ui.toolButtonControl2.setPopupMode(QToolButton.InstantPopup)
        self.ui.toolButtonControl2.setMenu(self.controlMenu)
        
        # set favorites menu
        self.favorites_menu = QMenu(_translate('menu', 'Favorites'))
        self.favorites_menu.setIcon(QIcon(':scalable/breeze/star-yellow'))
        self.ui.toolButtonFavorites.setPopupMode(QToolButton.InstantPopup)
        self.ui.toolButtonFavorites.setMenu(self.favorites_menu)
        self.ui.menuAdd.addMenu(self.favorites_menu)
        
        # set trash menu
        self.trashMenu = QMenu()
        self.ui.trashButton.setPopupMode(QToolButton.InstantPopup)
        self.ui.trashButton.setMenu(self.trashMenu)

        # connect OSC signals from daemon
        sg = self._signaler
        sg.server_progress.connect(self.serverProgress)
        sg.server_status_changed.connect(self.serverChangeServerStatus)
        sg.server_copying.connect(self.serverCopying)
        sg.daemon_url_request.connect(self.showDaemonUrlWindow)
        
        # set spare icons if system icons not avalaible
        dark = isDarkTheme(self)
        
        if self.ui.actionNewSession.icon().isNull():
            self.ui.actionNewSession.setIcon(RayIcon('folder-new', dark))
        if self.ui.actionOpenSession.icon().isNull():
            self.ui.actionOpenSession.setIcon(RayIcon('document-open', dark))
            
        if self.ui.actionControlMenu.icon().isNull():
            self.ui.actionControlMenu.setIcon(
                QIcon.fromTheme('configuration_section'))
            if self.ui.actionControlMenu.icon().isNull():
                self.ui.actionControlMenu.setIcon(RayIcon('configure', dark))
        
        if self.ui.actionOpenSessionFolder.icon().isNull():
            self.ui.actionOpenSessionFolder.setIcon(
                                        RayIcon('system-file-manager', dark))
        
        if self.ui.actionAddApplication.icon().isNull():
            self.ui.actionAddApplication.setIcon(RayIcon('list-add', dark))
        
        if self.ui.actionAddExecutable.icon().isNull():
            self.ui.actionAddExecutable.setIcon(QIcon.fromTheme('system-run'))
            if self.ui.actionAddExecutable.icon().isNull():
                self.ui.actionAddExecutable.setIcon(RayIcon('run-install'))
            
        self.ui.actionReturnToAPreviousState.setIcon(
                                        RayIcon('media-seek-backward', dark))
        
        self.ui.trashButton.setIcon(RayIcon('trash-empty', dark))

        self.ui.actionDuplicateSession.setIcon(
            RayIcon('xml-node-duplicate', dark))
        self.ui.actionSaveTemplateSession.setIcon(
            RayIcon('document-save-as-template', dark))
        self.ui.actionCloseSession.setIcon(RayIcon('window-close', dark))
        self.ui.actionAbortSession.setIcon(RayIcon('list-remove', dark))
        self.ui.actionSaveSession.setIcon(RayIcon('document-save', dark))
        self.ui.toolButtonSaveSession.setIcon(RayIcon('document-save', dark))
        self.ui.actionDesktopsMemory.setIcon(RayIcon('view-list-icons', dark))

        self.setNsmLocked(CommandLineArgs.under_nsm)
        
        self.script_info_dialog = None
        
        # disable "keep focus" if daemon is not on this machine (it takes no
        # sense in this case)
        if not self._daemon_manager.is_local:
            self.ui.actionKeepFocus.setChecked(False)
            self.ui.actionKeepFocus.setEnabled(False)
        
        self.server_progress = 0.0
        self.progress_dialog_visible = False
        
        self.has_git = False

    def createClientWidget(self, client):
        return self.ui.listWidget.createClientWidget(client)

    def reCreateListWidget(self):
        # this function shouldn't exist, 
        # it is a workaround for a bug with python-qt.
        # (when reorder widgets sometimes one widget is totally hidden 
        # until user resize the window)
        # It has to be modified when ui_raysession is modified.

        self.ui.listWidget.clear()
        self.ui.verticalLayout.removeWidget(self.ui.listWidget)
        del self.ui.listWidget
        self.ui.listWidget = list_widget_clients.ListWidgetClients(
            self.ui.frameCurrentSession)
        self.ui.listWidget.setAcceptDrops(True)
        self.ui.listWidget.setStyleSheet("QFrame{border:none}")
        self.ui.listWidget.setDragEnabled(True)
        self.ui.listWidget.setDragDropMode(QAbstractItemView.InternalMove)
        self.ui.listWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ui.listWidget.setUniformItemSizes(True)
        self.ui.listWidget.setBatchSize(80)
        self.ui.listWidget.setObjectName("listWidget")
        self.ui.listWidget.setSession(self._session)
        self.ui.verticalLayout.addWidget(self.ui.listWidget)

    def setNsmLocked(self, nsm_locked):
        self.ui.actionNewSession.setEnabled(not nsm_locked)
        self.ui.actionOpenSession.setEnabled(not nsm_locked)
        self.ui.actionDuplicateSession.setEnabled(not nsm_locked)
        self.ui.actionCloseSession.setEnabled(not nsm_locked)
        self.ui.actionAbortSession.setEnabled(not nsm_locked)

        self.ui.toolBar.setVisible(not nsm_locked)
        self.ui.toolButtonDuplicateSession.setVisible(not nsm_locked)
        self.ui.toolButtonAbortSession.setVisible(not nsm_locked)
        self.ui.closeButton.setVisible(not nsm_locked)
        self.ui.toolButtonControl2.setVisible(nsm_locked)

        self.ui.stackedWidgetSessionName.setEditable(
            nsm_locked and not CommandLineArgs.out_daemon)
        self.ui.actionRenameSession.setEnabled(
            nsm_locked and not CommandLineArgs.out_daemon)

    def setDaemonOptions(self, options):
        self.ui.actionSaveAllFromSavedClient.setChecked(
            bool(options & ray.Option.SAVE_FROM_CLIENT))
        self.ui.actionBookmarkSessionFolder.setChecked(
            bool(options & ray.Option.BOOKMARK_SESSION))
        self.ui.actionDesktopsMemory.setChecked(
            bool(options & ray.Option.DESKTOPS_MEMORY))
        self.ui.actionAutoSnapshot.setChecked(
            bool(options & ray.Option.SNAPSHOTS))

        has_wmctrl = bool(options & ray.Option.HAS_WMCTRL)
        self.ui.actionDesktopsMemory.setEnabled(has_wmctrl)
        if has_wmctrl:
            self.ui.actionDesktopsMemory.setText(
                _translate('actions', 'Desktops Memory'))
            
        has_git = bool(options & ray.Option.HAS_GIT)
        self.ui.actionAutoSnapshot.setEnabled(has_git)
        self.ui.actionReturnToAPreviousState.setVisible(has_git)
        self.ui.toolButtonSnapshots.setVisible(has_git)
        if has_git:
            self.ui.actionAutoSnapshot.setText(
                _translate('actions', 'Auto Snapshot at Save'))
        
        self.has_git = has_git

    def toDaemon(self, *args):
        server = GUIServerThread.instance()
        if server:
            server.toDaemon(*args)

    def hideMessagesDock(self):
        self.ui.dockWidgetMessages.setVisible(False)

    def openFileManager(self):
        self.toDaemon('/ray/session/open_folder')

    def raiseWindow(self):
        if self.mouse_is_inside:
            self.activateWindow()

    def toggleKeepFocus(self, bool):
        self.keep_focus = bool
        if self._daemon_manager.is_local:
            RS.settings.setValue('keepfocus', self.keep_focus)
        if not bool:
            self.timer_raisewin.stop()

    def saveAllFromClientToggled(self, state):
        self.toDaemon('/ray/option/save_from_client', int(state))

    def bookmarkSessionFolderToggled(self, state):
        self.toDaemon('/ray/option/bookmark_session_folder', int(state))

    def desktopsMemoryToggled(self, state):
        self.toDaemon('/ray/option/desktops_memory', int(state))

    def autoSnapshotToggled(self, state):
        self.toDaemon('/ray/option/snapshots', int(state))
        
    def flashOpen(self):
        for client in self._session.client_list:
            if client.status == ray.ClientStatus.OPEN:
                client.widget.flashIfOpen(self.flash_open_bool)

        self.flash_open_bool = not self.flash_open_bool

    def quitApp(self):
        #if (self._daemon_manager.launched_before
                #and not CommandLineArgs.under_nsm):
            #self.quitAppNow()
            #return True

        if self._session.isRunning():
            dialog = child_dialogs.QuitAppDialog(self)
            dialog.exec()
            if not dialog.result():
                return False
            
        self.quitAppNow()
        return True

    def quitAppNow(self):
        self._daemon_manager.stop()

    def updateClientLabel(self, client_id, label):
        client = self._session.getClient(client_id)
        if not client:
            return

        client.updateLabel(label)

    def createNewSession(self):
        self.ui.dockWidgetMessages.setVisible(False)
        dialog = child_dialogs.NewSessionDialog(self)
        dialog.exec()
        if not dialog.result():
            return

        session_name = dialog.getSessionName()
        template_name = dialog.getTemplateName()
        subfolder = dialog.getSubFolder()

        RS.settings.setValue('last_used_template', template_name)
        RS.settings.setValue('last_subfolder', subfolder)
        if self._session.isRunning():
            RS.settings.setValue('last_session', self._session.getShortPath())

        if template_name:
            self.toDaemon('/ray/server/new_session', session_name,
                          template_name)
        else:
            self.toDaemon('/ray/server/new_session', session_name)

    def openSession(self, action):
        dialog = child_dialogs.OpenSessionDialog(self)
        dialog.exec()
        if not dialog.result():
            return

        if self._session.isRunning():
            RS.settings.setValue('last_session', self._session.getShortPath())

        session_name = dialog.getSelectedSession()
        self.toDaemon('/ray/server/open_session', session_name)

    def closeSession(self):
        RS.settings.setValue('last_session', self._session.getShortPath())
        self.toDaemon('/ray/session/close')

    def abortSession(self):
        dialog = child_dialogs.AbortSessionDialog(self)
        dialog.exec()

        if dialog.result():
            RS.settings.setValue('last_session', self._session.getShortPath())
            self.toDaemon('/ray/session/abort')

    def renameSessionAction(self):
        if not self._session.is_renameable:
            QMessageBox.information(
                self,
                _translate("rename_session", "Rename Session"),
                _translate("rename_session",
                           "<p>In order to rename current session,<br>"
                           + "please first stop all clients.<br>"
                           + "then, double click on session name.</p>"))
            return

        self.ui.stackedWidgetSessionName.toggleEdit()

    def duplicateSession(self):
        dialog = child_dialogs.NewSessionDialog(self, True)
        dialog.exec()
        if not dialog.result():
            return

        RS.settings.setValue('last_session', self._session.name)

        session_name = dialog.getSessionName()
        self.toDaemon('/ray/session/duplicate', session_name)

    def saveTemplateSession(self):
        dialog = child_dialogs.SaveTemplateSessionDialog(self)
        dialog.exec()
        if not dialog.result():
            return

        session_template_name = dialog.getTemplateName()
        self.toDaemon('/ray/session/save_as_template', session_template_name)
        
    def returnToAPreviousState(self):
        dialog = snapshots_dialog.SessionSnapshotsDialog(self)
        dialog.exec()
        if not dialog.result():
            return 
        
        snapshot = dialog.getSelectedSnapshot()
        self.toDaemon('/ray/session/open_snapshot', snapshot)
    
    def aboutRaySession(self):
        dialog = child_dialogs.AboutRaySessionDialog(self)
        dialog.exec()

    def donate(self, display_no_again=False):
        dialog = child_dialogs.DonationsDialog(self, display_no_again)
        dialog.exec()
        
    def saveSession(self):
        self.toDaemon('/ray/session/save')

    def addApplication(self):
        if self._session.server_status in (
                ray.ServerStatus.CLOSE,
                ray.ServerStatus.OFF):
            return

        dialog = add_application_dialog.AddApplicationDialog(self)
        dialog.exec()
        dialog.saveCheckBoxes()

        if dialog.result():
            template_name, factory = dialog.getSelectedTemplate()
            #factory = dialog.isTemplateFactory(template_name)
            self.toDaemon(
                '/ray/session/add_client_template',
                int(factory),
                template_name)

    def addExecutable(self):
        if self._session.server_status in (
                ray.ServerStatus.CLOSE,
                ray.ServerStatus.OFF):
            return

        dialog = child_dialogs.NewExecutableDialog(self)
        dialog.exec()
        if not dialog.result():
            return

        #command = dialog.getExecutableSelected()
        #proxy = dialog.runViaProxy()
        
        command, via_proxy, prefix_mode, prefix, client_id = dialog.getSelection()
        
        self.toDaemon('/ray/session/add_executable', command, int(via_proxy),
                      prefix_mode, prefix, client_id)
        
        #if proxy:
            #self.toDaemon('/ray/session/add_proxy', command)
        #else:
            #self.toDaemon('/ray/session/add_executable', command)

    def stopClient(self, client_id):
        client = self._session.getClient(client_id)
        if not client:
            return
        
        if client.no_save_level and client.check_last_save:
            dialog = child_dialogs.StopClientNoSaveDialog(self, client_id)
            dialog.exec()
            if not dialog.result():
                return

        elif (client.status == ray.ClientStatus.READY
              and client.check_last_save):
            if client.has_dirty:
                if client.dirty_state:
                    dialog = child_dialogs.StopClientDialog(self, client_id)
                    dialog.exec()
                    if not dialog.result():
                        return

            # last save (or start) more than 60 seconds ago
            elif (time.time() - client.last_save) >= 10:
                dialog = child_dialogs.StopClientDialog(self, client_id)
                dialog.exec()
                if not dialog.result():
                    return

        self.toDaemon('/ray/client/stop', client_id)

    def statusBarPressed(self):
        status = self._session.server_status
        
        if status not in (
                ray.ServerStatus.PRECOPY,
                ray.ServerStatus.COPY,
                ray.ServerStatus.SNAPSHOT,
                ray.ServerStatus.OUT_SNAPSHOT,
                ray.ServerStatus.WAIT_USER):
            return
        
        if status in (ray.ServerStatus.PRECOPY, ray.ServerStatus.COPY):
            if not self.server_copying:
                return

            dialog = child_dialogs.AbortServerCopyDialog(self)
            dialog.exec()

            if not dialog.result():
                return

            self.toDaemon('/ray/server/abort_copy')
        
        elif status in (ray.ServerStatus.SNAPSHOT,
                        ray.ServerStatus.OUT_SNAPSHOT):
            self.showSnapshotProgressDialog()
            
        elif status == ray.ServerStatus.WAIT_USER:
            dialog = child_dialogs.WaitingCloseUserDialog(self)
            dialog.exec()

    def abortCopyClient(self, client_id):
        if not self.server_copying:
            return

        client = self._session.getClient(client_id)
        if not client or client.status not in (
                ray.ClientStatus.COPY, ray.ClientStatus.PRECOPY):
            return

        dialog = child_dialogs.AbortClientCopyDialog(self, client_id)
        dialog.exec()

        if not dialog.result():
            return

        self.toDaemon('/ray/server/abort_copy')

    def renameSessionConditionnaly(self, new_session_name):
        self.toDaemon('/ray/session/rename', new_session_name)
        
    def addFavorite(self, name, icon_name, factory):
        self._session.addFavorite(name, icon_name, factory, True)
        
    def removeFavorite(self, name, factory):
        self._session.removeFavorite(name, factory, True)

    def showSnapshotProgressDialog(self):
        if self.progress_dialog_visible:
            return
        self.progress_dialog_visible = True
        
        dialog = child_dialogs.SnapShotProgressDialog(self)
        dialog.serverProgress(self.server_progress)
        dialog.exec()
        
        self.progress_dialog_visible = False
        
        if not dialog.result():
            return 
        
        self.toDaemon('/ray/server/abort_snapshot')
        
    def showDaemonUrlWindow(self, err_code, ex_url=''):
        dialog = child_dialogs.DaemonUrlWindow(self, err_code, ex_url)
        dialog.exec()
        if not dialog.result():
            if (CommandLineArgs.under_nsm
                    and self._daemon_manager.launched_before):
                QApplication.quit()
            return

        new_url = dialog.getUrl()

        tried_urls = ray.getListInSettings(RS.settings, 'network/tried_urls')
        if new_url not in tried_urls:
            tried_urls.append(new_url)

        RS.settings.setValue('network/tried_urls', tried_urls)
        RS.settings.setValue('network/last_tried_url', new_url)

        self._signaler.daemon_url_changed.emit(new_url)

    ###FUNCTIONS RELATED TO SIGNALS FROM OSC SERVER#######

    def removeClient(self, client_id):
        self.ui.listWidget.removeClientWidget(client_id)

    def clientStatusChanged(self, client_id, status):
        # launch/stop flashing status if 'open'
        for client in self._session.client_list:
            if client.status == ray.ClientStatus.OPEN:
                if not self.timer_flicker_open.isActive():
                    self.timer_flicker_open.start()
                break
        else:
            self.timer_flicker_open.stop()

        # launch/stop timer_raisewin if keep focus
        if self.keep_focus:
            for client in self._session.client_list:
                if client.status == ray.ClientStatus.OPEN:
                    if not self.timer_raisewin.isActive():
                        self.timer_raisewin.start()
                    break
            else:
                self.timer_raisewin.stop()
                if status == ray.ClientStatus.READY:
                    self.raiseWindow()

    def printMessage(self, message):
        self.ui.textEditMessages.appendPlainText(
            time.strftime("%H:%M:%S") + '  ' + message)

    def renameSession(self, session_name, session_path):
        if session_name:
            self.setWindowTitle('%s - %s' % (ray.APP_TITLE, session_name))
            self.ui.stackedWidgetSessionName.setText(session_name)
        else:
            self.setWindowTitle(ray.APP_TITLE)
            self.ui.stackedWidgetSessionName.setText(
                _translate('main view', 'No Session Loaded'))

    def setSessionNameEditable(self, bool_set_edit):
        self.ui.stackedWidgetSessionName.setEditable(bool_set_edit)
        
    def errorMessage(self, message):
        error_dialog = child_dialogs.ErrorDialog(self, message)
        error_dialog.exec()

    def openingNsmSession(self):
        if not RS.settings.value('OpenNsmSessionInfo', True, type=bool):
            return

        dialog = child_dialogs.OpenNsmSessionInfoDialog(self)
        dialog.exec()

    def serverProgress(self, progress):
        self.server_progress = progress
        self.ui.lineEditServerStatus.setProgress(progress)

    def serverCopying(self, copying):
        self.server_copying = copying
        self.serverChangeServerStatus(self._session.server_status)

    def serverChangeServerStatus(self, server_status):
        self._session.updateServerStatus(server_status)

        self.ui.lineEditServerStatus.setText(
            serverStatusString(server_status))
        self.ui.frameCurrentSession.setEnabled(
            bool(server_status != ray.ServerStatus.OFF))
        
        if server_status in (ray.ServerStatus.SNAPSHOT,
                             ray.ServerStatus.OUT_SNAPSHOT):
            self.timer_snapshot.start()
        elif self.timer_snapshot.isActive():
            self.timer_snapshot.stop()

        if server_status == ray.ServerStatus.COPY:
            self.ui.actionSaveSession.setEnabled(False)
            self.ui.actionCloseSession.setEnabled(False)
            self.ui.actionAbortSession.setEnabled(False)
            self.ui.actionReturnToAPreviousState.setEnabled(False)
            return

        if server_status == ray.ServerStatus.PRECOPY:
            self.ui.actionSaveSession.setEnabled(False)
            self.ui.actionCloseSession.setEnabled(False)
            self.ui.actionAbortSession.setEnabled(True)
            self.ui.actionDuplicateSession.setEnabled(False)
            self.ui.actionSaveTemplateSession.setEnabled(False)
            self.ui.actionReturnToAPreviousState.setEnabled(False)
            self.ui.actionAddApplication.setEnabled(False)
            self.ui.actionAddExecutable.setEnabled(False)
            self.ui.actionOpenSessionFolder.setEnabled(True)
            return

        close_or_off = bool(
            server_status in (
                ray.ServerStatus.CLOSE,
                ray.ServerStatus.WAIT_USER,
                ray.ServerStatus.OUT_SAVE,
                ray.ServerStatus.OUT_SNAPSHOT,
                ray.ServerStatus.OFF))
        ready = bool(server_status == ray.ServerStatus.READY)

        self.ui.actionSaveSession.setEnabled(ready)
        self.ui.actionCloseSession.setEnabled(ready)
        self.ui.actionAbortSession.setEnabled(
            not bool(server_status in (ray.ServerStatus.CLOSE,
                                       ray.ServerStatus.OFF)))
        self.ui.actionDuplicateSession.setEnabled(not close_or_off)
        self.ui.actionReturnToAPreviousState.setEnabled(not close_or_off)
        self.ui.actionRenameSession.setEnabled(ready)
        self.ui.actionSaveTemplateSession.setEnabled(not close_or_off)
        self.ui.actionAddApplication.setEnabled(not close_or_off)
        self.ui.actionAddExecutable.setEnabled(not close_or_off)
        self.ui.toolButtonFavorites.setEnabled(
            bool(self._session.favorite_list and not close_or_off))
        self.favorites_menu.setEnabled(
            bool(self._session.favorite_list and not close_or_off))
        self.ui.actionOpenSessionFolder.setEnabled(
            bool(server_status != ray.ServerStatus.OFF))

        self.ui.stackedWidgetSessionName.setEditable(
            ready and self._session.is_renameable)
        
        self.ui.trashButton.setEnabled(bool(self._session.trashed_clients)
                                       and not close_or_off)
        
        if (CommandLineArgs.under_nsm
                and not CommandLineArgs.out_daemon
                and ready
                and self._session.is_renameable):
            self.ui.stackedWidgetSessionName.setOnEdit()

        if self.server_copying:
            self.ui.actionSaveSession.setEnabled(False)
            self.ui.actionCloseSession.setEnabled(False)

        if CommandLineArgs.under_nsm:
            self.ui.actionNewSession.setEnabled(False)
            self.ui.actionOpenSession.setEnabled(False)
            self.ui.actionDuplicateSession.setEnabled(False)
            self.ui.actionCloseSession.setEnabled(False)
            self.ui.actionAbortSession.setEnabled(False)
        
        if server_status == ray.ServerStatus.OFF:
            if self.terminate_request:
                self._daemon_manager.stop()
                
        if server_status == ray.ServerStatus.WAIT_USER:
            if not RS.settings.value(
                    'hide_wait_close_user_dialog', False, type=bool):
                dialog = child_dialogs.WaitingCloseUserDialog(self)
                dialog.exec()
            

    def trashAdd(self, client_data):
        prettier_name = client_data.name
        if client_data.label:
            prettier_name = client_data.label

        act_x_trashed = self.trashMenu.addAction(
            QIcon.fromTheme(client_data.icon), prettier_name)
        act_x_trashed.setData(client_data.client_id)
        act_x_trashed.triggered.connect(self.showClientTrashDialog)
        
        self.ui.trashButton.setEnabled(
            bool(not self._session.server_status in (
                        ray.ServerStatus.OFF,
                        ray.ServerStatus.OUT_SAVE,
                        ray.ServerStatus.WAIT_USER,
                        ray.ServerStatus.OUT_SNAPSHOT,
                        ray.ServerStatus.CLOSE)))
        
        return act_x_trashed
    
    def trashRemove(self, menu_action):
        self.trashMenu.removeAction(menu_action)
        
        if not self._session.trashed_clients:
            self.ui.trashButton.setEnabled(False)
    
    def trashClear(self):
        self.trashMenu.clear()
        self.ui.trashButton.setEnabled(False)
    
    @pyqtSlot()
    def showClientTrashDialog(self):
        try:
            client_id = str(self.sender().data())
        except BaseException:
            return
        
        for trashed_client in self._session.trashed_clients:
            if trashed_client.data.client_id == client_id:
                break
        else:
            return

        dialog = child_dialogs.ClientTrashDialog(self, trashed_client.data)
        dialog.exec()
        if not dialog.result():
            return

        self.toDaemon('/ray/trash/restore', client_id)
    
    @pyqtSlot()
    def launchFavorite(self):
        template_name, factory = self.sender().data()
        self.toDaemon('/ray/session/add_client_template',
                      int(factory),
                      template_name)
        
    def updateFavoritesMenu(self):
        self.favorites_menu.clear()
        
        enable = bool(self._session.favorite_list
                      and not self._session.server_status in (
                        ray.ServerStatus.OFF,
                        ray.ServerStatus.CLOSE,
                        ray.ServerStatus.OUT_SAVE,
                        ray.ServerStatus.OUT_SNAPSHOT))
        
        self.ui.toolButtonFavorites.setEnabled(enable)
        
        for favorite in self._session.favorite_list:
            act_app = self.favorites_menu.addAction(
                        ray.getAppIcon(favorite.icon, self), favorite.name)
            act_app.setData([favorite.name, favorite.factory])
            act_app.triggered.connect(self.launchFavorite)
    
    def showScriptInfo(self, text):
        if not self.script_info_dialog:
            self.script_info_dialog = child_dialogs.ScriptInfoDialog(self)
            
        self.script_info_dialog.setText(text)
        self.script_info_dialog.show()
        
    def hideScriptInfo(self):
        if self.script_info_dialog:
            self.script_info_dialog.close()
        
        del self.script_info_dialog
        self.script_info_dialog = None
    
    def daemonCrash(self):
        QMessageBox.critical(
            self, _translate(
                'errors', "daemon crash!"), _translate(
                'errors', "ray-daemon crashed, sorry !"))
        QApplication.quit()
        
    def saveWindowSettings(self):
        RS.settings.setValue('MainWindow/geometry', self.saveGeometry())
        RS.settings.setValue('MainWindow/WindowState', self.saveState())
        RS.settings.setValue(
            'MainWindow/ShowMenuBar',
            self.ui.menuBar.isVisible())
        RS.settings.setValue(
            'MainWindow/ShowMessages',
            self.ui.dockWidgetMessages.isVisible())
        RS.settings.sync()

    # Reimplemented Functions
    
    def closeEvent(self, event):
        self.saveWindowSettings()
        
        if self.quitApp():
            QMainWindow.closeEvent(self, event)
        else:
            event.ignore()

    def leaveEvent(self, event):
        if self.isActiveWindow():
            self.mouse_is_inside = False
        QDialog.leaveEvent(self, event)

    def enterEvent(self, event):
        self.mouse_is_inside = True
        QDialog.enterEvent(self, event)
