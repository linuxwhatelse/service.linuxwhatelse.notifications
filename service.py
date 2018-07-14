import os
import threading
import sys

import dbus
import dbus.mainloop.glib
import dbus.service

import gobject
import xbmc
import xbmcaddon
import xbmcgui

gobject.threads_init()

ADDON = xbmcaddon.Addon()
PROFILE_DIR = xbmc.translatePath(ADDON.getAddonInfo('profile'))
CACHE_DIR = os.path.join(PROFILE_DIR, '.icon-cache')

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

ICONS = {}


def log(*args, **kwargs):
    level = kwargs.get('level', xbmc.LOGDEBUG)

    args = (str(arg) for arg in args)

    msg = '[{}] {}'.format(ADDON.getAddonInfo('id'), ' '.join(args))
    xbmc.log(msg, level=level)


def notify(title, body='', icon=None, timeout=5000, sound=True):
    xbmcgui.Dialog().notification(title, body, icon, timeout, sound)


def get_icons(theme_path):
    icons = {}
    for res in ['512x512', '256x256', '96x96', '64x64', '48x48']:
        path_ = os.path.join(theme_path, res)
        if not os.path.exists(path_):
            continue
        for root, dirs, files in os.walk(path_):
            for f in files:
                name = os.path.splitext(f)[0]
                path = os.path.join(root, f)
                if name not in icons:
                    log('Adding "{}" to icons list ({})'.format(name, path))
                    icons[name] = path

    return icons


class Handler(dbus.service.Object):
    _icon_theme = None
    _icons = None

    @dbus.service.method('org.freedesktop.Notifications',
                         in_signature='susssasa{ss}i', out_signature='u')
    def Notify(self, app_name, replaces_id, app_icon, summary, body, actions,
               hints, expire_timeout):
        log('New notification:')
        log('  app={}, title={}, body={}, icon={}, timeout={}'.format(
            app_name, summary, body, app_icon, expire_timeout))

        addon = xbmcaddon.Addon()

        icon_theme = addon.getSetting('icon_theme')
        if self._icon_theme != icon_theme:
            self._icons = get_icons(icon_theme)
            self._icon_theme = icon_theme

        if expire_timeout <= 0:
            expire_timeout = int(addon.getSetting('timeout')) * 1000

        app_icon = self._icons.get(app_icon, app_icon)
        sound = addon.getSetting('sound') == 'true'

        notify(summary, body, app_icon, expire_timeout, sound)

        return 1

    @dbus.service.method('org.freedesktop.Notifications', out_signature='as')
    def GetCapabilities(self):
        return ('body')

    @dbus.service.signal('org.freedesktop.Notifications', signature='uu')
    def NotificationClosed(self, id, reason):
        pass

    @dbus.service.method('org.freedesktop.Notifications', in_signature='u')
    def CloseNotification(self, id):
        pass

    @dbus.service.method('org.freedesktop.Notifications', out_signature='ssss')
    def GetServerInformation(self):
        return (ADDON.getAddonInfo('name'), ADDON.getAddonInfo('author'),
                ADDON.getAddonInfo('version'), '1')


if __name__ == '__main__':
    if not dbus.get_default_main_loop():
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    log('Starting gobject mainloop...')
    loop = gobject.MainLoop()
    loop_thread = threading.Thread(target=loop.run)
    loop_thread.start()

    bus = dbus.SessionBus()
    name = dbus.service.BusName('org.freedesktop.Notifications', bus)
    handler = Handler(bus, '/org/freedesktop/Notifications')

    log('Starting kodi monitor...')
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(3):
            log('Abort requested, exiting...')
            break

    log('Cleaning up...')
    loop.quit()

    log('Waiting for threads to finish...')
    loop_thread.join()

    log('All done!')
