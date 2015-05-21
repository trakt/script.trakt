"""
    SALTS XBMC Addon
    Copyright (C) 2014 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import xbmcgui
import time
import os
import xbmcaddon
from utilities import notification, setSetting, getString
import traktapi

__addon__ = xbmcaddon.Addon("script.trakt")

def get_pin():
    AUTH_BUTTON = 200
    LATER_BUTTON = 201
    NEVER_BUTTON = 202
    ACTION_PREVIOUS_MENU = 10
    ACTION_BACK = 92
    CENTER_Y = 6
    CENTER_X = 2
    
    class PinAuthDialog(xbmcgui.WindowXMLDialog):
        auth = False
        
        def onInit(self):
            self.pin_edit_control = self.__add_editcontrol(30, 240, 40, 450)
            self.setFocus(self.pin_edit_control)
            auth = self.getControl(AUTH_BUTTON)
            never = self.getControl(NEVER_BUTTON)
            self.pin_edit_control.controlUp(never)
            self.pin_edit_control.controlLeft(never)
            self.pin_edit_control.controlDown(auth)
            self.pin_edit_control.controlRight(auth)
            auth.controlUp(self.pin_edit_control)
            auth.controlLeft(self.pin_edit_control)
            never.controlDown(self.pin_edit_control)
            never.controlRight(self.pin_edit_control)
            
        def onAction(self, action):
            #print 'Action: %s' % (action.getId())
            if action == ACTION_PREVIOUS_MENU or action == ACTION_BACK:
                self.close()

        def onControl(self, control):
            #print 'onControl: %s' % (control)
            pass

        def onFocus(self, control):
            #print 'onFocus: %s' % (control)
            pass

        def onClick(self, control):
            #print 'onClick: %s' % (control)
            if control == AUTH_BUTTON:
                if not self.__get_token():
                    notification(getString(32149), getString(32147), 5000)
                    return
                self.auth = True

            if control == LATER_BUTTON:
                notification(getString(32149), getString(32150), 5000)
                setSetting('last_reminder', str(int(time.time())))

            if control == NEVER_BUTTON:
                notification(getString(32149), getString(32151), 5000)
                setSetting('last_reminder', '-1')

            if control in [AUTH_BUTTON, LATER_BUTTON, NEVER_BUTTON]:
                self.close()
        
        def __get_token(self):
            pin = self.pin_edit_control.getText().strip()
            if pin:
                try:
                    if traktapi.traktAPI().authenticate(pin):
                        return True
                except:
                    return False
            return False
        
        # have to add edit controls programatically because getControl() (hard) crashes XBMC on them
        def __add_editcontrol(self, x, y, height, width):
            media_path = os.path.join(__addon__.getAddonInfo('path'), 'resources', 'skins', 'Default', 'media')
            temp = xbmcgui.ControlEdit(0, 0, 0, 0, '', font='font12', textColor='0xFFFFFFFF', focusTexture=os.path.join(media_path, 'button-focus2.png'),
                                       noFocusTexture=os.path.join(media_path, 'button-nofocus.png'), _alignment=CENTER_Y | CENTER_X)
            temp.setPosition(x, y)
            temp.setHeight(height)
            temp.setWidth(width)
            self.addControl(temp)
            return temp
        
    dialog = PinAuthDialog('TraktPinAuthDialog.xml', __addon__.getAddonInfo('path'))
    dialog.doModal()
    if dialog.auth:
        notification(getString(32149), getString(32152), 3000)
    del dialog
